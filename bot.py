import os
import re
import logging
import datetime
import time
import json
import sqlite3
import asyncio
import io
from collections import Counter
from typing import Dict, List, Tuple, Optional, Union

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import emoji
import pytz
from wordcloud import WordCloud
from nltk.tokenize import word_tokenize
import nltk

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode

# =================== TEMEL AYARLAR ===================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
DB_PATH = "trend_analysis.db"
TZ = pytz.timezone('Europe/Istanbul')  # Türkiye zaman dilimi
VERSION = "1.0.0"

# Loglama ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =================== YARDIMCI FONKSİYONLAR ===================

def load_turkish_stop_words():
    """Türkçe durak kelimeleri yükle veya oluştur"""
    try:
        with open('turkish_stop_words.txt', 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        # Temel Türkçe durak kelimeler
        stop_words = {
            "ve", "ile", "bu", "bir", "da", "de", "için", "ama", "olarak", "çok", 
            "daha", "böyle", "şöyle", "ancak", "fakat", "ki", "ya", "mi", "mı", 
            "mu", "mü", "ne", "nasıl", "kadar", "gibi", "her", "biz", "ben", "sen", 
            "o", "onlar", "siz", "bizim", "benim", "senin", "onun", "sizin", "onların",
            "şey", "şu", "şunlar", "bunlar", "evet", "hayır", "tamam", "yok", 
            "var", "değil", "olur", "olmaz", "olmak", "yapmak", "etmek", "birşey",
            "bir", "şey", "ise", "veya"
        }
        with open('turkish_stop_words.txt', 'w', encoding='utf-8') as f:
            for word in sorted(stop_words):
                f.write(f"{word}\n")
        return stop_words

# Veritabanı yardımcı fonksiyonları
def init_database():
    """Veritabanını ve gerekli tabloları oluştur"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Mesajlar tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        username TEXT,
        first_name TEXT,
        message_text TEXT,
        message_date TIMESTAMP,
        has_hashtags INTEGER DEFAULT 0,
        has_mentions INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Hashtag tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hashtags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        chat_id INTEGER NOT NULL,
        hashtag TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (message_id) REFERENCES messages (id)
    )
    ''')
    
    # Mention tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mentions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        chat_id INTEGER NOT NULL,
        mentioned_username TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (message_id) REFERENCES messages (id)
    )
    ''')
    
    # Kelime tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        chat_id INTEGER NOT NULL,
        word TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (message_id) REFERENCES messages (id)
    )
    ''')
    
    # Grup ayarları tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id INTEGER PRIMARY KEY,
        chat_title TEXT,
        auto_report INTEGER DEFAULT 0,
        report_time TEXT DEFAULT "20:00",
        tracking_enabled INTEGER DEFAULT 1,
        admin_user_ids TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Veritabanı başarıyla oluşturuldu")

def save_message(update: Update):
    """Mesajı veritabanına kaydet ve hashtag/mention bilgilerini çıkar"""
    message = update.message
    
    if not message or not message.text:
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Mesaj tarihini Türkiye saati olarak ayarla
    message_date = datetime.datetime.fromtimestamp(message.date.timestamp(), TZ)
    
    # Mesajı kaydet
    cursor.execute('''
    INSERT INTO messages (chat_id, user_id, username, first_name, message_text, message_date, 
                         has_hashtags, has_mentions)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        message.chat_id, 
        message.from_user.id, 
        message.from_user.username, 
        message.from_user.first_name,
        message.text, 
        message_date.strftime('%Y-%m-%d %H:%M:%S'),
        1 if '#' in message.text else 0,
        1 if '@' in message.text else 0
    ))
    
    message_id = cursor.lastrowid
    
    # Hashtag'leri çıkar ve kaydet
    hashtags = re.findall(r'#(\w+)', message.text)
    for hashtag in hashtags:
        cursor.execute('''
        INSERT INTO hashtags (message_id, chat_id, hashtag)
        VALUES (?, ?, ?)
        ''', (message_id, message.chat_id, hashtag.lower()))
    
    # Mention'ları çıkar ve kaydet
    mentions = re.findall(r'@(\w+)', message.text)
    for mention in mentions:
        cursor.execute('''
        INSERT INTO mentions (message_id, chat_id, mentioned_username)
        VALUES (?, ?, ?)
        ''', (message_id, message.chat_id, mention.lower()))
    
    # Kelimeleri çıkar ve kaydet
    stop_words = load_turkish_stop_words()
    
    # Emoji ve özel karakterleri temizle
    text = emoji.replace_emoji(message.text, replace='')
    text = re.sub(r'[^\w\s]', '', text)
    
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')
    
    words = word_tokenize(text.lower(), language='turkish')
    for word in words:
        if (len(word) > 2 and  # Çok kısa kelimeleri atla
            word not in stop_words and  # Durak kelimeleri atla
            not word.isdigit() and  # Sayıları atla
            not re.match(r'^[0-9]+$', word)):  # Sadece sayılardan oluşan kelimeleri atla
            cursor.execute('''
            INSERT INTO words (message_id, chat_id, word)
            VALUES (?, ?, ?)
            ''', (message_id, message.chat_id, word.lower()))
    
    conn.commit()
    conn.close()

def update_chat_settings(chat_id: int, chat_title: str, admin_ids: List[int] = None):
    """Grup ayarlarını güncelle veya oluştur"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT chat_id FROM chat_settings WHERE chat_id = ?', (chat_id,))
    exists = cursor.fetchone()
    
    if exists:
        if admin_ids:
            cursor.execute('''
            UPDATE chat_settings 
            SET chat_title = ?, admin_user_ids = ?, updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = ?
            ''', (chat_title, json.dumps(admin_ids), chat_id))
        else:
            cursor.execute('''
            UPDATE chat_settings 
            SET chat_title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = ?
            ''', (chat_title, chat_id))
    else:
        admin_ids_json = json.dumps(admin_ids) if admin_ids else '[]'
        cursor.execute('''
        INSERT INTO chat_settings (chat_id, chat_title, admin_user_ids)
        VALUES (?, ?, ?)
        ''', (chat_id, chat_title, admin_ids_json))
    
    conn.commit()
    conn.close()

# =================== TREND ANALİZİ FONKSİYONLARI ===================

def get_trend_data(chat_id: Optional[int] = None, period: str = 'daily', limit: int = 10):
    """Belirli bir dönem için trend verilerini al"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.datetime.now(TZ).date()
    
    if period == 'daily':
        start_date = today
    elif period == 'weekly':
        start_date = today - datetime.timedelta(days=7)
    elif period == 'monthly':
        start_date = today - datetime.timedelta(days=30)
    elif period == 'total':
        start_date = None
    else:
        start_date = today  # Varsayılan olarak günlük
    
    # Trend verilerini topla
    trend_data = {
        'words': [],
        'hashtags': [],
        'mentions': [],
        'active_users': [],
        'message_count': 0
    }
    
    # Tarih filtresi oluştur
    date_filter = ''
    params = []
    
    if chat_id:
        date_filter += 'chat_id = ?'
        params.append(chat_id)
    
    if start_date:
        if params:
            date_filter += ' AND '
        date_filter += 'DATE(message_date) >= ?'
        params.append(start_date.strftime('%Y-%m-%d'))
    
    if date_filter:
        date_filter = 'WHERE ' + date_filter
    
    # Toplam mesaj sayısı
    cursor.execute(f'SELECT COUNT(*) FROM messages {date_filter}', params)
    trend_data['message_count'] = cursor.fetchone()[0]
    
    # En çok kullanılan kelimeler
    cursor.execute(f'''
    SELECT word, COUNT(*) as count 
    FROM words 
    {date_filter} 
    GROUP BY word 
    ORDER BY count DESC 
    LIMIT ?
    ''', params + [limit])
    trend_data['words'] = [{'word': row[0], 'count': row[1]} for row in cursor.fetchall()]
    
    # En çok kullanılan hashtag'ler
    cursor.execute(f'''
    SELECT hashtag, COUNT(*) as count 
    FROM hashtags 
    {date_filter} 
    GROUP BY hashtag 
    ORDER BY count DESC 
    LIMIT ?
    ''', params + [limit])
    trend_data['hashtags'] = [{'hashtag': row[0], 'count': row[1]} for row in cursor.fetchall()]
    
    # En çok mention edilen kullanıcılar
    cursor.execute(f'''
    SELECT mentioned_username, COUNT(*) as count 
    FROM mentions 
    {date_filter} 
    GROUP BY mentioned_username 
    ORDER BY count DESC 
    LIMIT ?
    ''', params + [limit])
    trend_data['mentions'] = [{'username': row[0], 'count': row[1]} for row in cursor.fetchall()]
    
    # En aktif kullanıcılar
    cursor.execute(f'''
    SELECT username, first_name, COUNT(*) as count 
    FROM messages 
    {date_filter} 
    GROUP BY user_id 
    ORDER BY count DESC 
    LIMIT ?
    ''', params + [limit])
    trend_data['active_users'] = [
        {'username': row[0] or row[1], 'count': row[2]} 
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return trend_data

def generate_trend_image(trend_data: Dict, title: str, chat_title: str = None):
    """Trend verilerinden görsel oluştur"""
    # Matplotlib Türkçe karakter desteği
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"{title}{' - ' + chat_title if chat_title else ''}", fontsize=16)
    
    # En çok kullanılan kelimeler grafiği
    if trend_data['words']:
        words = [item['word'] for item in trend_data['words']]
        word_counts = [item['count'] for item in trend_data['words']]
        axs[0, 0].barh(words, word_counts, color='skyblue')
        axs[0, 0].set_title('En Çok Kullanılan Kelimeler')
        axs[0, 0].set_xlabel('Kullanım Sayısı')
        # Y ekseni etiketlerini tersine çevir (en popüler en üstte)
        axs[0, 0].invert_yaxis()
    else:
        axs[0, 0].text(0.5, 0.5, 'Veri Bulunamadı', ha='center', va='center')
        axs[0, 0].set_title('En Çok Kullanılan Kelimeler')
    
    # En çok kullanılan hashtag'ler grafiği
    if trend_data['hashtags']:
        hashtags = [f"#{item['hashtag']}" for item in trend_data['hashtags']]
        hashtag_counts = [item['count'] for item in trend_data['hashtags']]
        axs[0, 1].barh(hashtags, hashtag_counts, color='lightgreen')
        axs[0, 1].set_title('En Çok Kullanılan Hashtag\'ler')
        axs[0, 1].set_xlabel('Kullanım Sayısı')
        axs[0, 1].invert_yaxis()
    else:
        axs[0, 1].text(0.5, 0.5, 'Veri Bulunamadı', ha='center', va='center')
        axs[0, 1].set_title('En Çok Kullanılan Hashtag\'ler')
    
    # En çok mention edilen kullanıcılar grafiği
    if trend_data['mentions']:
        mentions = [f"@{item['username']}" for item in trend_data['mentions']]
        mention_counts = [item['count'] for item in trend_data['mentions']]
        axs[1, 0].barh(mentions, mention_counts, color='salmon')
        axs[1, 0].set_title('En Çok Mention Edilen Kullanıcılar')
        axs[1, 0].set_xlabel('Mention Sayısı')
        axs[1, 0].invert_yaxis()
    else:
        axs[1, 0].text(0.5, 0.5, 'Veri Bulunamadı', ha='center', va='center')
        axs[1, 0].set_title('En Çok Mention Edilen Kullanıcılar')
    
    # En aktif kullanıcılar grafiği
    if trend_data['active_users']:
        users = [item['username'] for item in trend_data['active_users']]
        user_counts = [item['count'] for item in trend_data['active_users']]
        axs[1, 1].barh(users, user_counts, color='mediumpurple')
        axs[1, 1].set_title('En Aktif Kullanıcılar')
        axs[1, 1].set_xlabel('Mesaj Sayısı')
        axs[1, 1].invert_yaxis()
    else:
        axs[1, 1].text(0.5, 0.5, 'Veri Bulunamadı', ha='center', va='center')
        axs[1, 1].set_title('En Aktif Kullanıcılar')
    
    # Alt bilgi olarak toplam mesaj sayısını ekle
    plt.figtext(
        0.5, 0.01, 
        f"Toplam Mesaj: {trend_data['message_count']} | Oluşturulma: {datetime.datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}", 
        ha="center", fontsize=10
    )
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # Grafiği bir byte buffer'a kaydet
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close(fig)
    
    return buf

def generate_wordcloud(chat_id: Optional[int] = None, period: str = 'daily'):
    """Kelime bulutu oluştur"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.datetime.now(TZ).date()
    
    if period == 'daily':
        start_date = today
    elif period == 'weekly':
        start_date = today - datetime.timedelta(days=7)
    elif period == 'monthly':
        start_date = today - datetime.timedelta(days=30)
    elif period == 'total':
        start_date = None
    else:
        start_date = today
    
    # Filtreleri hazırla
    date_filter = ''
    params = []
    
    if chat_id:
        date_filter += 'chat_id = ?'
        params.append(chat_id)
    
    if start_date:
        if params:
            date_filter += ' AND '
        date_filter += 'DATE(message_date) >= ?'
        params.append(start_date.strftime('%Y-%m-%d'))
    
    if date_filter:
        date_filter = 'WHERE ' + date_filter
    
    # Kelime frekanslarını al
    cursor.execute(f'''
    SELECT word, COUNT(*) as count 
    FROM words 
    {date_filter} 
    GROUP BY word
    ''', params)
    
    word_freq = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    
    if not word_freq:
        return None
    
    # Wordcloud oluştur
    wc = WordCloud(
        width=800, height=400,
        background_color='white',
        max_words=200,
        colormap='viridis',
        collocations=False
    ).generate_from_frequencies(word_freq)
    
    # Grafiği kaydet
    plt.figure(figsize=(10, 5))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    
    # Grafiği bir byte buffer'a kaydet
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    
    return buf

# =================== BOT KOMUTLARI ===================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlatma komutu"""
    user = update.effective_user
    chat_type = update.effective_chat.type
    
    welcome_message = (
        f"👋 Merhaba {user.first_name}!\n\n"
        f"🤖 *TrendBot* sürüm {VERSION} başarıyla başlatıldı.\n\n"
        "Bu bot grup mesajlarında en çok kullanılan kelimeleri, hashtag'leri ve mention'ları analiz ederek "
        "günlük, haftalık ve aylık trend raporları oluşturur.\n\n"
    )
    
    # Eğer özel sohbette ise, daha detaylı mesaj gönder
    if chat_type == 'private':
        welcome_message += (
            "*Komutlar:*\n"
            "/help - Komut listesini görüntüle\n"
            "/trend - Trend raporlarını görüntüle\n"
            "/stats - Detaylı istatistikleri görüntüle\n"
            "/wordcloud - Kelime bulutu oluştur\n\n"
            "Botu gruplara ekleyerek grup konuşmalarını analiz edebilirsiniz."
        )
    else:
        # Grup ise bilgileri kaydet
        admin_ids = []
        try:
            admins = await context.bot.get_chat_administrators(chat_id=update.effective_chat.id)
            admin_ids = [admin.user.id for admin in admins]
        except Exception as e:
            logger.error(f"Admin listesi alınamadı: {e}")
        
        update_chat_settings(
            update.effective_chat.id, 
            update.effective_chat.title,
            admin_ids
        )
        
        welcome_message += (
            "Bot bu grupta mesajları analiz etmeye başladı.\n"
            "Komutlar için /help yazabilirsiniz."
        )
    
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardım komutu"""
    chat_type = update.effective_chat.type
    
    help_text = (
        "*📊 TrendBot Komutları 📊*\n\n"
        "*Temel Komutlar:*\n"
        "/start - Botu başlat\n"
        "/help - Bu yardım mesajını görüntüle\n\n"
        
        "*Trend Raporları:*\n"
        "/trend - Trend menüsünü göster\n"
        "/trend_daily - Günlük trend raporu\n"
        "/trend_weekly - Haftalık trend raporu\n"
        "/trend_monthly - Aylık trend raporu\n"
        "/trend_total - Genel toplam trend raporu\n\n"
        
        "*Kelime Bulutu:*\n"
        "/wordcloud - Kelime bulutu menüsü\n"
        "/wordcloud_daily - Günlük kelime bulutu\n"
        "/wordcloud_weekly - Haftalık kelime bulutu\n"
        "/wordcloud_monthly - Aylık kelime bulutu\n\n"
    )
    
    if chat_type == 'private':
        help_text += (
            "*İstatistikler:*\n"
            "/stats - İstatistik menüsünü göster\n"
            "/groups - Analiz edilen grupları listele\n\n"
            
            "*Arama:*\n"
            "/search <kelime> - Belirli bir kelimeyi ara\n"
            "/hashtag <hashtag> - Belirli bir hashtag'i ara\n"
            "/mention <kullanıcı> - Belirli bir kullanıcıya yapılan mention'ları ara\n\n"
        )
    
    if chat_type == 'group' or chat_type == 'supergroup':
        help_text += (
            "*Grup Ayarları:*\n"
            "/settings - Grup ayarlarını görüntüle\n"
            "/auto_report - Otomatik rapor ayarlarını değiştir\n\n"
            
            "*Not:* Tüm komut ve ayarlar grup yöneticileri tarafından kontrol edilebilir."
        )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def trend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trend menüsü"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Günlük", callback_data="trend_daily"),
            InlineKeyboardButton("📈 Haftalık", callback_data="trend_weekly")
        ],
        [
            InlineKeyboardButton("📉 Aylık", callback_data="trend_monthly"),
            InlineKeyboardButton("🔍 Genel Toplam", callback_data="trend_total")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📊 *Trend Raporu Seçin:*", 
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def trend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trend callback handler"""
    query = update.callback_query
    await query.answer()
    
    # Callback verilerini parçala
    data = query.data.split('_')
    report_type = data[1] if len(data) > 1 else 'daily'
    
    # Rapor başlıklarını hazırla
    titles = {
        'daily': 'Günlük Trend Raporu',
        'weekly': 'Haftalık Trend Raporu',
        'monthly': 'Aylık Trend Raporu',
        'total': 'Genel Toplam Trend Raporu'
    }
    
    # İşlem mesajı gönder
    message = await query.edit_message_text(
        f"🔄 {titles[report_type]} hazırlanıyor...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Trend verilerini al
    chat_id = update.effective_chat.id
    trend_data = get_trend_data(chat_id, report_type)
    
    # Trend grafiği oluştur
    img_buffer = generate_trend_image(
        trend_data, 
        titles[report_type],
        update.effective_chat.title
    )
    
    # Grafiği gönder
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=img_buffer,
        caption=f"📊 *{titles[report_type]}*\n"
               f"📅 {datetime.datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # İşlem mesajını sil
    await message.delete()

async def wordcloud_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kelime bulutu menüsü"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Günlük", callback_data="wordcloud_daily"),
            InlineKeyboardButton("📈 Haftalık", callback_data="wordcloud_weekly")
        ],
        [
            InlineKeyboardButton("📉 Aylık", callback_data="wordcloud_monthly"),
            InlineKeyboardButton("🔍 Genel Toplam", callback_data="wordcloud_total")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "☁️ *Kelime Bulutu Seçin:*", 
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def wordcloud_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kelime bulutu callback handler"""
    query = update.callback_query
    await query.answer()
    
    # Callback verilerini parçala
    data = query.data.split('_')
    cloud_type = data[1] if len(data) > 1 else 'daily'
    
    # Başlıkları hazırla
    titles = {
        'daily': 'Günlük Kelime Bulutu',
        'weekly': 'Haftalık Kelime Bulutu',
        'monthly': 'Aylık Kelime Bulutu',
        'total': 'Genel Toplam Kelime Bulutu'
    }
    
    # İşlem mesajı gönder
    message = await query.edit_message_text(
        f"🔄 {titles[cloud_type]} hazırlanıyor...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Kelime bulutu oluştur
    chat_id = update.effective_chat.id
    img_buffer = generate_wordcloud(chat_id, cloud_type)
    
    if img_buffer:
        # Kelime bulutunu gönder
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=img_buffer,
            caption=f"☁️ *{titles[cloud_type]}*\n"
                   f"📅 {datetime.datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Veri yoksa bilgi mesajı gönder
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ {titles[cloud_type]} için yeterli veri bulunamadı.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # İşlem mesajını sil
    await message.delete()

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grup ayarları komutu"""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    
    # Sadece grup sohbetlerinde çalışır
    if chat_type not in ['group', 'supergroup']:
        await update.message.reply_text(
            "Bu komut sadece gruplarda kullanılabilir.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Kullanıcının grup yöneticisi olup olmadığını kontrol et
    is_admin = False
    try:
        admins = await context.bot.get_chat_administrators(chat_id=chat_id)
        admin_ids = [admin.user.id for admin in admins]
        is_admin = user_id in admin_ids
    except Exception as e:
        logger.error(f"Admin listesi alınamadı: {e}")
    
    if not is_admin:
        await update.message.reply_text(
            "❌ Bu komutu kullanabilmek için grup yöneticisi olmalısınız.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Grup ayarlarını al
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM chat_settings WHERE chat_id = ?', (chat_id,))
    settings = cursor.fetchone()
    
    if not settings:
        # Eğer ayarlar yoksa oluştur
        admin_ids = [admin.user.id for admin in admins]
        update_chat_settings(chat_id, update.effective_chat.title, admin_ids)
        
        cursor.execute('SELECT * FROM chat_settings WHERE chat_id = ?', (chat_id,))
        settings = cursor.fetchone()
    
    # Ayarları göster
    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 Otomatik Rapor: " + ("Açık ✅" if settings[2] else "Kapalı ❌"), 
                callback_data="settings_toggle_auto_report"
            )
        ],
        [
            InlineKeyboardButton(
                "⏰ Rapor Saati: " + settings[3], 
                callback_data="settings_change_time"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Takip: " + ("Açık ✅" if settings[4] else "Kapalı ❌"), 
                callback_data="settings_toggle_tracking"
            )
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"⚙️ *{update.effective_chat.title} Grup Ayarları*\n\n"
        "Aşağıdaki ayarları değiştirmek için ilgili düğmeye tıklayın.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    conn.close()

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ayarlar callback handler"""
    query = update.callback_query
    await query.answer()
    
    # Callback verilerini parçala
    data = query.data.split('_')
    action = data[1] if len(data) > 1 else ''
    sub_action = data[2] if len(data) > 2 else ''
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Kullanıcının grup yöneticisi olup olmadığını kontrol et
    is_admin = False
    try:
        admins = await context.bot.get_chat_administrators(chat_id=chat_id)
        admin_ids = [admin.user.id for admin in admins]
        is_admin = user_id in admin_ids
    except Exception as e:
        logger.error(f"Admin listesi alınamadı: {e}")
    
    if not is_admin:
        await query.edit_message_text(
            "❌ Bu ayarları değiştirmek için grup yöneticisi olmalısınız.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if action == 'toggle':
        if sub_action == 'auto_report':
            # Otomatik raporu aç/kapat
            cursor.execute('SELECT auto_report FROM chat_settings WHERE chat_id = ?', (chat_id,))
            current_setting = cursor.fetchone()[0]
            new_setting = 0 if current_setting else 1
            
            cursor.execute(
                'UPDATE chat_settings SET auto_report = ?, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?', 
                (new_setting, chat_id)
            )
            conn.commit()
            
        elif sub_action == 'tracking':
            # Takibi aç/kapat
            cursor.execute('SELECT tracking_enabled FROM chat_settings WHERE chat_id = ?', (chat_id,))
            current_setting = cursor.fetchone()[0]
            new_setting = 0 if current_setting else 1
            
            cursor.execute(
                'UPDATE chat_settings SET tracking_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?', 
                (new_setting, chat_id)
            )
            conn.commit()
    
    elif action == 'change' and sub_action == 'time':
        # Rapor saati değiştirme UI'ı göster
        time_options = ["08:00", "12:00", "16:00", "20:00", "00:00"]
        keyboard = []
        row = []
        
        for i, time in enumerate(time_options):
            row.append(InlineKeyboardButton(time, callback_data=f"settings_set_time_{time}"))
            if (i + 1) % 3 == 0 or i == len(time_options) - 1:
                keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("⬅️ Geri", callback_data="settings_back")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⏰ *Günlük Rapor Saati*\n\n"
            "Otomatik raporların gönderileceği saati seçin:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        conn.close()
        return
    
    elif action == 'set' and sub_action == 'time':
        # Rapor saatini ayarla
        new_time = data[3] if len(data) > 3 else "20:00"
        
        cursor.execute(
            'UPDATE chat_settings SET report_time = ?, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?', 
            (new_time, chat_id)
        )
        conn.commit()
    
    elif action == 'back':
        # Ana ayarlar menüsüne dön
        pass
    
    # Güncel ayarları göster
    cursor.execute('SELECT * FROM chat_settings WHERE chat_id = ?', (chat_id,))
    settings = cursor.fetchone()
    
    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 Otomatik Rapor: " + ("Açık ✅" if settings[2] else "Kapalı ❌"), 
                callback_data="settings_toggle_auto_report"
            )
        ],
        [
