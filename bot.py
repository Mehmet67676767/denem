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
    def count_words(self, text: str) -> int:
        """Metindeki kelime sayısını sayar."""
        if not text:
            return 0
        return len(text.split())
    
    def count_emojis(self, text: str) -> int:
        """Metindeki emoji sayısını sayar."""
        if not text:
            return 0
        return sum(1 for c in text if c in emoji.EMOJI_DATA)
    
    def count_abbreviations(self, text: str) -> int:
        """Metindeki kısaltma sayısını sayar."""
        if not text:
            return 0
        words = text.lower().split()
        return sum(1 for word in words if word in TURKISH_ABBREVIATIONS)
    
    def analyze_message(self, chat_id: int, user_id: int, username: str, text: str) -> Dict:
        """Mesajı analiz eder ve veritabanına kaydeder."""
        if not text:
            return {}
            
        hashtags = self.extract_hashtags(text)
        mentions = self.extract_mentions(text)
        letter_count = self.count_letters(text)
        word_count = self.count_words(text)
        emoji_count = self.count_emojis(text)
        abbreviation_count = self.count_abbreviations(text)
        
        # Veritabanına kaydet
        conn = self.connect_db()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO messages (
            chat_id, user_id, username, message_text, hashtags, mentions,
            letter_count, word_count, emoji_count, abbreviation_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            chat_id, user_id, username, text, 
            json.dumps(hashtags), json.dumps(mentions),
            letter_count, word_count, emoji_count, abbreviation_count
        ))
        conn.commit()
        self.close_db()
        
        return {
            "hashtags": hashtags,
            "mentions": mentions,
            "letter_count": letter_count,
            "word_count": word_count,
            "emoji_count": emoji_count,
            "abbreviation_count": abbreviation_count
        }
    
    def process_message_words(self, text: str) -> List[str]:
        """Mesaj metnini işler ve analiz için kelimeleri döndürür."""
        if not text:
            return []
            
        # Küçük harfe çevir
        text = text.lower()
        
        # Hashtag ve mention'ları temizle
        text = re.sub(r'#\w+', '', text)
        text = re.sub(r'@\w+', '', text)
        
        # Emoji ve özel karakterleri temizle
        text = ''.join(c for c in text if c not in emoji.EMOJI_DATA and c.isalnum() or c.isspace())
        
        # Tokenize
        words = word_tokenize(text)
        
        # Durak kelimeleri ve tek harfleri kaldır
        words = [word for word in words if word not in self.stop_words and len(word) > 1]
        
        return words
    
    def update_trends(self, chat_id: int, period: str):
        """Belirli bir zaman periyodu için trend verilerini günceller."""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        # Zaman aralığını belirle
        today = datetime.datetime.now().date()
        if period == "daily":
            start_date = today
        elif period == "weekly":
            start_date = today - datetime.timedelta(days=7)
        elif period == "monthly":
            start_date = today - datetime.timedelta(days=30)
        else:
            self.close_db()
            return
        
        # Eski trendleri sil
        cursor.execute('''
        DELETE FROM trends 
        WHERE chat_id = ? AND time_period = ? AND timestamp = ?
        ''', (chat_id, period, today))
        
        # Zaman aralığındaki mesajları al
        cursor.execute('''
        SELECT message_text, hashtags, mentions FROM messages
        WHERE chat_id = ? AND date(created_at) >= date(?)
        ''', (chat_id, start_date))
        
        messages = cursor.fetchall()
        
        # Kelime, hashtag ve mention sayılarını topla
        word_counter = Counter()
        hashtag_counter = Counter()
        mention_counter = Counter()
        emoji_counter = Counter()
        
        for message_text, hashtags_json, mentions_json in messages:
            # Kelime analizi
            words = self.process_message_words(message_text)
            word_counter.update(words)
            
            # Hashtag analizi
            if hashtags_json:
                hashtags = json.loads(hashtags_json)
                hashtag_counter.update(hashtags)
            
            # Mention analizi
            if mentions_json:
                mentions = json.loads(mentions_json)
                mention_counter.update(mentions)
            
            # Emoji analizi
            if message_text:
                emojis = [c for c in message_text if c in emoji.EMOJI_DATA]
                emoji_counter.update(emojis)
        
        # En popüler 20 kelimeyi veritabanına kaydet
        for word, count in word_counter.most_common(20):
            cursor.execute('''
            INSERT INTO trends (chat_id, trend_type, content, count, time_period, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (chat_id, 'word', word, count, period, today))
        
        # En popüler 10 hashtag'i veritabanına kaydet
        for hashtag, count in hashtag_counter.most_common(10):
            cursor.execute('''
            INSERT INTO trends (chat_id, trend_type, content, count, time_period, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (chat_id, 'hashtag', hashtag, count, period, today))
        
        # En popüler 10 mention'ı veritabanına kaydet
        for mention, count in mention_counter.most_common(10):
            cursor.execute('''
            INSERT INTO trends (chat_id, trend_type, content, count, time_period, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (chat_id, 'mention', mention, count, period, today))
        
        # En popüler 10 emojiyi veritabanına kaydet
        for emoji_char, count in emoji_counter.most_common(10):
            cursor.execute('''
            INSERT INTO trends (chat_id, trend_type, content, count, time_period, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (chat_id, 'emoji', emoji_char, count, period, today))
        
        conn.commit()
        self.close_db()
    
    def get_trending_data(self, chat_id: int, trend_type: str, period: str) -> List[Tuple[str, int]]:
        """Belirli bir trend tipi ve zaman periyodu için trend verilerini getirir."""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT content, count FROM trends
        WHERE chat_id = ? AND trend_type = ? AND time_period = ?
        ORDER BY count DESC
        ''', (chat_id, trend_type, period))
        
        result = cursor.fetchall()
        self.close_db()
        
        return result
    
    def generate_word_cloud(self, chat_id: int, period: str) -> Optional[io.BytesIO]:
        """Kelime bulutu oluşturur ve bir BytesIO nesnesinde döndürür."""
        trending_words = self.get_trending_data(chat_id, 'word', period)
        
        if not trending_words:
            return None
        
        wordcloud_data = {word: count for word, count in trending_words}
        
        # Kelime bulutu oluştur
        wordcloud = WordCloud(
            width=800, 
            height=400, 
            background_color='white',
            colormap='viridis',
            max_words=100,
            contour_width=1,
            contour_color='steelblue'
        ).generate_from_frequencies(wordcloud_data)
        
        # Resim dosyasını oluştur
        img_data = io.BytesIO()
        plt.figure(figsize=(10, 5))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.title(f"{period.capitalize()} Trend Kelime Bulutu")
        plt.tight_layout()
        plt.savefig(img_data, format='png')
        plt.close()
        
        img_data.seek(0)
        return img_data
    
    def generate_bar_chart(self, chat_id: int, trend_type: str, period: str) -> Optional[io.BytesIO]:
        """Çubuk grafik oluşturur ve bir BytesIO nesnesinde döndürür."""
        trending_data = self.get_trending_data(chat_id, trend_type, period)
        
        if not trending_data:
            return None
        
        # En fazla 10 öğe göster
        trending_data = trending_data[:10]
        
        # Veriyi ayrıştır
        labels = [item[0] for item in trending_data]
        values = [item[1] for item in trending_data]
        
        # Türkçe karakterleri düzgün göstermek için
        plt.rcParams['font.family'] = 'DejaVu Sans'
        
        # Grafik oluştur
        plt.figure(figsize=(10, 6))
        bars = plt.bar(labels, values, color='skyblue')
        
        # Her çubuğun üzerine değeri yaz
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                     f'{int(height)}', ha='center', va='bottom')
        
        title_map = {
            'word': 'Kelimeler',
            'hashtag': 'Hashtagler',
            'mention': 'Bahsetmeler',
            'emoji': 'Emojiler'
        }
        
        period_map = {
            'daily': 'Günlük',
            'weekly': 'Haftalık',
            'monthly': 'Aylık'
        }
        
        plt.title(f"{period_map[period]} En Popüler {title_map[trend_type]}")
        plt.xticks(rotation=45, ha='right')
        plt.xlabel('İçerik')
        plt.ylabel('Sayı')
        plt.tight_layout()
        
        # Resim dosyasını oluştur
        img_data = io.BytesIO()
        plt.savefig(img_data, format='png')
        plt.close()
        
        img_data.seek(0)
        return img_data
    
    def register_chat(self, chat_id: int, chat_name: str):
        """Yeni bir chat'i veritabanına kaydeder."""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        # Chat zaten kayıtlı mı kontrol et
        cursor.execute('SELECT 1 FROM chat_settings WHERE chat_id = ?', (chat_id,))
        if not cursor.fetchone():
            cursor.execute('''
            INSERT INTO chat_settings (chat_id, chat_name)
            VALUES (?, ?)
            ''', (chat_id, chat_name))
            conn.commit()
        
        self.close_db()
    
    def update_chat_settings(self, chat_id: int, settings: Dict):
        """Chat ayarlarını günceller."""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        set_clauses = []
        values = []
        
        for key, value in settings.items():
            if key in ['auto_report', 'report_time', 'report_frequency', 'admins', 'track_words', 'custom_stop_words']:
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                set_clauses.append(f"{key} = ?")
                values.append(value)
        
        if not set_clauses:
            self.close_db()
            return False
        
        query = f'''
        UPDATE chat_settings 
        SET {', '.join(set_clauses)}
        WHERE chat_id = ?
        '''
        values.append(chat_id)
        
        cursor.execute(query, values)
        conn.commit()
        self.close_db()
        return True
    
    def get_chat_settings(self, chat_id: int) -> Dict:
        """Chat ayarlarını getirir."""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM chat_settings WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        
        if not result:
            self.close_db()
            return {}
        
        columns = [desc[0] for desc in cursor.description]
        settings = dict(zip(columns, result))
        
        # JSON alanlarını parse et
        for key in ['admins', 'track_words', 'custom_stop_words']:
            if settings.get(key) and isinstance(settings[key], str):
                try:
                    settings[key] = json.loads(settings[key])
                except:
                    settings[key] = []
        
        self.close_db()
        return settings
    
    def get_global_trends(self, trend_type: str, period: str) -> List[Tuple[str, int]]:
        """Tüm gruplardan toplu trend verilerini getirir."""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT content, SUM(count) as total_count FROM trends
        WHERE trend_type = ? AND time_period = ?
        GROUP BY content
        ORDER BY total_count DESC
        LIMIT 20
        ''', (trend_type, period))
        
        result = cursor.fetchall()
        self.close_db()
        
        return result

class TrendBot:
    def __init__(self, token: str):
        self.token = token
        self.analyzer = MessageAnalyzer()
        init_database()  # Veritabanını başlat
        
        # Bot uygulamasını oluştur
        self.application = Application.builder().token(token).build()
        
        # Komut ve mesaj işleyicileri ekle
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("settings", self.settings))
        self.application.add_handler(CommandHandler("trends", self.trends))
        self.application.add_handler(CommandHandler("report", self.report))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("globaltopics", self.global_topics))
        
        # Callback query işleyicisi
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Genel mesaj işleyicisi
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Hata yakalayıcı
        self.application.add_error_handler(self.error_handler)
        
        # Otomatik rapor zamanlayıcıları
        self.scheduler_started = False
    
    async def start_scheduler(self):
        """Otomatik rapor zamanlayıcılarını başlatır."""
        if self.scheduler_started:
            return
        
        self.scheduler_started = True
        
        # Günlük trend güncellemesi
        asyncio.create_task(self.schedule_daily_trend_updates())
        
        # Otomatik raporlar
        asyncio.create_task(self.schedule_automatic_reports())
    
    async def schedule_daily_trend_updates(self):
        """Günlük trend güncellemelerini zamanlar."""
        while True:
            now = datetime.datetime.now()
            # Her gün gece yarısı trend güncellemesi yap
            next_run = (now.replace(hour=0, minute=0, second=0) + 
                        datetime.timedelta(days=1))
            
            # Bir sonraki çalışmaya kadar bekle
            await asyncio.sleep((next_run - now).total_seconds())
            
            # Tüm gruplar için günlük, haftalık ve aylık trendleri güncelle
            conn = self.analyzer.connect_db()
            cursor = conn.cursor()
            cursor.execute('SELECT chat_id FROM chat_settings')
            chats = cursor.fetchall()
            self.analyzer.close_db()
            
            for (chat_id,) in chats:
                self.analyzer.update_trends(chat_id, "daily")
                # Hafta sonuysa haftalık trendleri güncelle
                if now.weekday() == 6:  # Pazar
                    self.analyzer.update_trends(chat_id, "weekly")
                # Ayın son günüyse aylık trendleri güncelle
                if now.day == (now.replace(day=28) + datetime.timedelta(days=4)).day:
                    self.analyzer.update_trends(chat_id, "monthly")
    
    async def schedule_automatic_reports(self):
        """Otomatik raporları zamanlar."""
        while True:
            now = datetime.datetime.now()
            
            # Her 10 dakikada bir kontrol et
            await asyncio.sleep(600)
            
            # Ayarları kontrol et ve gerekirse rapor gönder
            conn = self.analyzer.connect_db()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT chat_id, report_time, report_frequency, auto_report 
            FROM chat_settings
            WHERE auto_report = 1
            ''')
            chats = cursor.fetchall()
            self.analyzer.close_db()
            
            for chat_id, report_time, frequency, auto_report in chats:
                if not auto_report or not report_time:
                    continue
                    
                # Rapor zamanını parse et
                try:
                    hour, minute = map(int, report_time.split(':'))
                    report_datetime = now.replace(hour=hour, minute=minute, second=0)
                except (ValueError, AttributeError):
                    continue
                
                # Şu anki zaman rapor zamanına yakınsa ve henüz rapor gönderilmediyse gönder
                time_diff = abs((now - report_datetime).total_seconds())
                if time_diff <= 300:  # 5 dakika içindeyse
                    # Raporun bugün zaten gönderilip gönderilmediğini kontrol et
                    report_key = f"report_sent_{chat_id}_{now.date()}"
                    # Bu örnekte basit bir kontrol yapıyoruz, gerçek uygulamada
                    # daha karmaşık bir izleme mekanizması kullanılabilir
                    if not hasattr(self, report_key):
                        # Günlük rapor gönder
                        if frequency == "daily":
                            await self.send_daily_report(chat_id)
                        # Haftalık rapor için, eğer bugün pazarsa gönder
                        elif frequency == "weekly" and now.weekday() == 6:
                            await self.send_weekly_report(chat_id)
                        # Aylık rapor için, eğer bugün ayın son günüyse gönder
                        elif frequency == "monthly" and now.day == (now.replace(day=28) + datetime.timedelta(days=4)).day:
                            await self.send_monthly_report(chat_id)
                        
                        # Raporu gönderildi olarak işaretle
                        setattr(self, report_key, True)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Botun başlatma komutu."""
        chat_id = update.effective_chat.id
        chat_name = update.effective_chat.title or str(chat_id)
        
        # Chat'i kaydet veya güncelle
        self.analyzer.register_chat(chat_id, chat_name)
        
        # Zamanlayıcıyı başlat
        if not self.scheduler_started:
            await self.start_scheduler()
        
        # Karşılama mesajı
        message = (
            "👋 *Merhaba! Ben Trend Analiz Botuyum.*\n\n"
            "Grubunuzdaki mesajları analiz eder, en çok kullanılan kelimeleri, "
            "hashtag'leri ve mention'ları izlerim. Günlük, haftalık ve aylık trend "
            "raporları oluşturabilirim.\n\n"
            "Komutlar için /help yazabilirsiniz."
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Günlük Trendler", callback_data="trends_daily"),
                InlineKeyboardButton("📈 Haftalık Trendler", callback_data="trends_weekly")
            ],
            [
                InlineKeyboardButton("📆 Aylık Trendler", callback_data="trends_monthly"),
                InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Yardım komutu."""
        message = (
            "*📚 Kullanılabilir Komutlar:*\n\n"
            "👉 */start* - Botu başlat\n"
            "👉 */help* - Bu yardım mesajını göster\n"
            "👉 */settings* - Bot ayarlarını düzenle\n"
            "👉 */trends* - Trend raporları menüsü\n"
            "👉 */report [daily|weekly|monthly]* - İstediğiniz zaman rapor alın\n"
            "👉 */stats [kelime]* - Belirli bir kelimenin istatistiklerini görün\n"
            "👉 */globaltopics* - Tüm gruplardaki popüler konuları görün\n\n"
            "*Bot Özellikleri:*\n"
            "✅ Grup mesajlarını analiz eder\n"
            "✅ Popüler kelimeleri ve hashtagleri tespit eder\n"
            "✅ Günlük, haftalık ve aylık trendleri raporlar\n"
            "✅ Otomatik raporlamayı destekler\n"
            "✅ Görsel grafikler oluşturur\n"
            "✅ Kısaltma ve emoji kullanımını analiz eder\n"
        )
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ayarlar komutu."""
        chat_id = update.effective_chat.id
        
        # Chat ayarlarını al
        settings = self.analyzer.get_chat_settings(chat_id)
        
        if not settings:
            chat_name = update.effective_chat.title or str(chat_id)
            self.analyzer.register_chat(chat_id, chat_name)
            settings = self.analyzer.get_chat_settings(chat_id)
        
        auto_report = settings.get('auto_report', True)
        report_time = settings.get('report_time', "20:00")
        report_frequency = settings.get('report_frequency', "daily")
        
        message = (
            "*⚙️ Bot Ayarları*\n\n"
            f"*Otomatik Raporlama:* {'Açık ✅' if auto_report else 'Kapalı ❌'}\n"
            f"*Rapor Zamanı:* {report_time}\n"
            f"*Rapor Sıklığı:* {report_frequency.capitalize()}\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'🔴 Otomatik Raporlamayı Kapat' if auto_report else '🟢 Otomatik Raporlamayı Aç'}", 
                    callback_data=f"toggle_report_{0 if auto_report else 1}"
                )
            ],
            [
                InlineKeyboardButton("⏰ Rapor Zamanını Değiştir", callback_data="change_time")
            ],
            [
                InlineKeyboardButton("📊 Günlük", callback_data="freq_daily"),
                InlineKeyboardButton("📈 Haftalık", callback_data="freq_weekly"),
                InlineKeyboardButton("📆 Aylık", callback_data="freq_monthly")
            ],
            [
                InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def trends(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Trendler komutu."""
        keyboard = [
            [
                InlineKeyboardButton("📊 Günlük Kelime Trendleri", callback_data="trends_words_daily"),
                InlineKeyboardButton("📈 Haftalık Kelime Trendleri", callback_data="trends_words_weekly")
            ],
            [
                InlineKeyboardButton("📆 Aylık Kelime Trendleri", callback_data="trends_words_monthly")
            ],
            [
                InlineKeyboardButton("#️⃣ Hashtag Trendleri", callback_data="trends_hashtags_daily"),
                InlineKeyboardButton("👤 Mention Trendleri", callback_data="trends_mentions_daily")
            ],
            [
                InlineKeyboardButton("😀 Emoji Trendleri", callback_data="trends_emojis_daily"),
                InlineKeyboardButton("📊 Görselleştir", callback_data="visualize")
            ],
            [
                InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "*📊 Trend Raporları*\n\n"
            "Grup içindeki mesaj analizlerini görüntülemek için bir seçenek seçin:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Rapor komutu."""
        chat_id = update.effective_chat.id
        args = context.args
        
        period = "daily"  # Varsayılan
        if args and args[0] in ["daily", "weekly", "monthly"]:
            period = args[0]
        
        # Trendleri güncelle
        self.analyzer.update_trends(chat_id, period)
        
        # Raporu gönder
        if period == "daily":
            await self.send_daily_report(chat_id)
        elif period == "weekly":
            await self.send_weekly_report(chat_id)
        elif period == "monthly":
            await self.send_monthly_report(chat_id)
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Belirli bir kelime veya hashtag'in istatistiklerini gösterir."""
        chat_id = update.effective_chat.id
        args = context.args
        
        if not args:
            await update.message.reply_text(
                "Lütfen istatistiklerini görmek istediğiniz kelimeyi veya hashtag'i belirtin.\n"
                "Örnek: `/stats merhaba` veya `/stats #selam`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        search_term = args[0].lower()
        is_hashtag = search_term.startswith('#')
        
        if is_hashtag:
            search_term = search_term[1:]  # # işaretini kaldır
            trend_type = 'hashtag'
        else:
            trend_type = 'word'
        
        conn = self.analyzer.connect_db()
        cursor = conn.cursor()
        
        # Son 30 gündeki kullanım verileri
        cursor.execute('''
        SELECT timestamp, count FROM trends
        WHERE chat_id = ? AND trend_type = ? AND content = ?
        AND timestamp >= date('now', '-30 days')
        ORDER BY timestamp
        ''', (chat_id, trend_type, search_term))
        
        usage_data = cursor.fetchall()
        self.analyzer.close_db()
        
        if not usage_data:
            await update.message.reply_text(
                f"Son 30 günde '{search_term}' {'hashtag\'i' if is_hashtag else 'kelimesi'} "
                f"hiç kullanılmamış veya trend olmamış.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Grafik oluştur
        dates = [item[0] for item in usage_data]
        counts = [item[1] for item in usage_data]
        
        plt.figure(figsize=(10, 6))
        plt.plot(dates, counts, marker='o', linestyle='-', color='blue')
        plt.title(f"'{search_term}' {'Hashtag\'i' if is_hashtag else 'Kelimesi'} Kullanım Grafiği")
        plt.xlabel('Tarih')
        plt.ylabel('Kullanım Sayısı')
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Resim dosyasını oluştur
        img_data = io.BytesIO()
        plt.savefig(img_data, format='png')
        plt.close()
        
        img_data.seek(0)
        
        # İstatistik özeti
        total_usage = sum(counts)
        max_usage = max(counts)
        max_date = dates[counts.index(max_usage)]
        
        message = (
            f"*'{search_term}' {'Hashtag\'i' if is_hashtag else 'Kelimesi'} İstatistikleri:*\n\n"
            f"📊 *Toplam Kullanım:* {total_usage} kez\n"
            f"📈 *En Yüksek Kullanım:* {max_usage} kez ({max_date} tarihinde)\n"
            f"📆 *İncelenen Süre:* Son 30 gün\n\n"
            f"Detaylı kullanım grafiği aşağıda gösterilmiştir."
        )
        
        await update.message.reply_photo(
            photo=img_data,
            caption=message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def global_topics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tüm gruplardaki popüler konuları gösterir."""
        # Tüm gruplardan küresel kelime trendlerini al
        global_word_trends = self.analyzer.get_global_trends('word', 'daily')
        global_hashtag_trends = self.analyzer.get_global_trends('hashtag', 'daily')
        
        if not global_word_trends and not global_hashtag_trends:
            await update.message.reply_text(
                "Henüz yeterli veri toplanmadı. Daha sonra tekrar deneyin.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Mesajı oluştur
        message = "*🌍 Tüm Gruplardaki Popüler Konular (Bugün)*\n\n"
        
        if global_word_trends:
            message += "*En Popüler Kelimeler:*\n"
            for i, (word, count) in enumerate(global_word_trends[:10], 1):
                message += f"{i}. {word} - {count} kez\n"
            message += "\n"
        
        if global_hashtag_trends:
            message += "*En Popüler Hashtagler:*\n"
            for i, (hashtag, count) in enumerate(global_hashtag_trends[:10], 1):
                message += f"{i}. #{hashtag} - {count} kez\n"
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Haftalık Küresel Trendler", callback_data="global_weekly"),
                InlineKeyboardButton("📆 Aylık Küresel Trendler", callback_data="global_monthly")
            ],
            [
                InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback sorgusu işleyici."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        chat_id = update.effective_chat.id
        
        # Ana menü
        if data == "main_menu":
            keyboard = [
                [
                    InlineKeyboardButton("📊 Günlük Trendler", callback_data="trends_daily"),
                    InlineKeyboardButton("📈 Haftalık Trendler", callback_data="trends_weekly")
                ],
                [
                    InlineKeyboardButton("📆 Aylık Trendler", callback_data="trends_monthly"),
                    InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "👋 *Ana Menü*\n\n"
                "Trend Analiz Botuna hoş geldiniz. Lütfen bir seçenek seçin:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Trendleri görüntüleme
        elif data.startswith("trends_"):
            parts = data.split("_")
            if len(parts) == 2:
                period = parts[1]
                await self.show_trend_types(query, chat_id, period)
            elif len(parts) == 3:
                trend_type, period = parts[1], parts[2]
                await self.show_trends(query, chat_id, trend_type, period)
        
        # Görselleştirme menüsü
        elif data == "visualize":
            keyboard = [
                [
                    InlineKeyboardButton("📊 Kelime Bulutu (Günlük)", callback_data="viz_wordcloud_daily"),
                    InlineKeyboardButton("📊 Kelime Bulutu (Haftalık)", callback_data="viz_wordcloud_weekly")
                ],
                [
                    InlineKeyboardButton("📊 Kelime Grafiği", callback_data="viz_wordbar_daily"),
                    InlineKeyboardButton("📊 Hashtag Grafiği", callback_data="viz_hashtagbar_daily")
                ],
                [
                    InlineKeyboardButton("🔙 Trendler Menüsü", callback_data="trends")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "*📊 Görselleştirme Menüsü*\n\n"
                "Trend verilerini görselleştirmek için bir seçenek seçin:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN

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
        ],
        [
            InlineKeyboardButton("⬅️ Ana Menüye Dön", callback_data="main_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"⚙️ *{update.effective_chat.title} Grup Ayarları*\n\n"
        "Aşağıdaki ayarları değiştirmek için ilgili düğmeye tıklayın.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    conn.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mesaj işleyici"""
    # Mesajı veritabanına kaydet
    save_message(update)

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ana menü callback handler"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Trend Raporu", callback_data="trend"),
            InlineKeyboardButton("☁️ Kelime Bulutu", callback_data="wordcloud")
        ],
        [
            InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🤖 *TrendBot Ana Menü*\n\n"
        "Lütfen bir seçenek seçin:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def auto_report(context: ContextTypes.DEFAULT_TYPE):
    """Otomatik rapor zamanlayıcı"""
    job = context.job
    chat_id = job.chat_id
    
    # Güncel ayarları kontrol et
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT auto_report FROM chat_settings WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    
    # Otomatik rapor kapatılmışsa işlem yapma
    if not result or not result[0]:
        return
    
    # Günlük trend raporunu gönder
    trend_data = get_trend_data(chat_id, 'daily')
    
    # Trend grafiği oluştur
    img_buffer = generate_trend_image(
        trend_data, 
        "Günlük Otomatik Trend Raporu",
        context.bot_data.get(f"chat_title_{chat_id}", "Grup")
    )
    
    # Grafiği gönder
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=img_buffer,
        caption=f"📊 *Günlük Otomatik Trend Raporu*\n"
               f"📅 {datetime.datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )

def main():
    """Bot başlatma fonksiyonu"""
    # Veritabanını oluştur
    init_database()
    
    # Download NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')
    
    # Bot uygulamasını oluştur
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Komut işleyicileri ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("trend", trend_command))
    application.add_handler(CommandHandler("trend_daily", lambda update, context: trend_callback(update, context, report_type="daily")))
    application.add_handler(CommandHandler("trend_weekly", lambda update, context: trend_callback(update, context, report_type="weekly")))
    application.add_handler(CommandHandler("trend_monthly", lambda update, context: trend_callback(update, context, report_type="monthly")))
    application.add_handler(CommandHandler("trend_total", lambda update, context: trend_callback(update, context, report_type="total")))
    
    application.add_handler(CommandHandler("wordcloud", wordcloud_command))
    application.add_handler(CommandHandler("wordcloud_daily", lambda update, context: wordcloud_callback(update, context, cloud_type="daily")))
    application.add_handler(CommandHandler("wordcloud_weekly", lambda update, context: wordcloud_callback(update, context, cloud_type="weekly")))
    application.add_handler(CommandHandler("wordcloud_monthly", lambda update, context: wordcloud_callback(update, context, cloud_type="monthly")))
    application.add_handler(CommandHandler("wordcloud_total", lambda update, context: wordcloud_callback(update, context, cloud_type="total")))
    
    application.add_handler(CommandHandler("settings", settings_command))
    
    # Callback query işleyicileri ekle
    application.add_handler(CallbackQueryHandler(trend_callback, pattern="^trend_"))
    application.add_handler(CallbackQueryHandler(wordcloud_callback, pattern="^wordcloud_"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^settings_"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    
    # Mesaj işleyicisini ekle
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Botu başlat
    logger.info("Bot başlatılıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
