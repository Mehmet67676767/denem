#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import json
import logging
import datetime
import sqlite3
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Set, Optional, Union, Any
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np
from io import BytesIO
import schedule
import time
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, CallbackContext,
    Filters, CallbackQueryHandler, ConversationHandler
)

# Temel yapılandırma
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token'ınızı buraya ekleyin
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# Veritabanı kurulumu
DB_NAME = "trendbot.db"

# Menü durumları
MAIN_MENU, REPORTS_MENU, TRACK_MENU, SETTINGS_MENU = range(4)

# Stopwords - Analize dahil edilmeyecek yaygın Türkçe kelimeler
TURKISH_STOPWORDS = {
    "acaba", "ama", "aslında", "az", "bazı", "belki", "biri", "birkaç", "birşey", 
    "biz", "bu", "çok", "çünkü", "da", "daha", "de", "defa", "diye", "eğer", 
    "en", "gibi", "her", "için", "ile", "ise", "kez", "ki", "kim", "mı", "mu", 
    "mü", "nasıl", "ne", "neden", "nerde", "nerede", "nereye", "niçin", "niye", 
    "o", "sanki", "şey", "siz", "şu", "tüm", "ve", "veya", "ya", "yani"
}

class Database:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self._create_tables()
    
    def _create_tables(self):
        """Gerekli veritabanı tablolarını oluşturur."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Grup tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY,
            group_id INTEGER UNIQUE,
            group_name TEXT,
            joined_date TEXT
        )
        ''')
        
        # Kelime kullanımı tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS word_usage (
            id INTEGER PRIMARY KEY,
            group_id INTEGER,
            word TEXT,
            date TEXT,
            count INTEGER,
            UNIQUE(group_id, word, date)
        )
        ''')
        
        # Hashtag kullanımı tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS hashtag_usage (
            id INTEGER PRIMARY KEY,
            group_id INTEGER,
            hashtag TEXT,
            date TEXT,
            count INTEGER,
            UNIQUE(group_id, hashtag, date)
        )
        ''')
        
        # Mention kullanımı tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mention_usage (
            id INTEGER PRIMARY KEY,
            group_id INTEGER,
            mention TEXT,
            date TEXT,
            count INTEGER,
            UNIQUE(group_id, mention, date)
        )
        ''')
        
        # Kullanıcı takip tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tracks (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            track_type TEXT,
            track_value TEXT,
            UNIQUE(user_id, track_type, track_value)
        )
        ''')
        
        # Otomatik raporlama tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto_reports (
            id INTEGER PRIMARY KEY,
            group_id INTEGER,
            report_type TEXT,
            enabled INTEGER DEFAULT 1,
            time TEXT,
            UNIQUE(group_id, report_type)
        )
        ''')
        
        # Grup ayarları tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_settings (
            id INTEGER PRIMARY KEY,
            group_id INTEGER UNIQUE,
            min_word_length INTEGER DEFAULT 3,
            max_words_in_report INTEGER DEFAULT 10,
            exclude_common_words INTEGER DEFAULT 1
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_group(self, group_id: int, group_name: str) -> bool:
        """Yeni bir grup ekler."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            joined_date = datetime.datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute(
                "INSERT OR IGNORE INTO groups (group_id, group_name, joined_date) VALUES (?, ?, ?)",
                (group_id, group_name, joined_date)
            )
            
            # Varsayılan grup ayarlarını ekle
            cursor.execute(
                "INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)",
                (group_id,)
            )
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Grup eklenirken hata oluştu: {e}")
            return False
        finally:
            conn.close()
    
    def add_word_usage(self, group_id: int, word: str, date: str, count: int = 1):
        """Kelime kullanımını kaydeder veya günceller."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO word_usage (group_id, word, date, count) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(group_id, word, date) DO UPDATE SET count = count + ?",
                (group_id, word.lower(), date, count, count)
            )
            
            conn.commit()
        except Exception as e:
            logger.error(f"Kelime kullanımı eklenirken hata oluştu: {e}")
        finally:
            conn.close()
    
    def add_hashtag_usage(self, group_id: int, hashtag: str, date: str, count: int = 1):
        """Hashtag kullanımını kaydeder veya günceller."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO hashtag_usage (group_id, hashtag, date, count) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(group_id, hashtag, date) DO UPDATE SET count = count + ?",
                (group_id, hashtag.lower(), date, count, count)
            )
            
            conn.commit()
        except Exception as e:
            logger.error(f"Hashtag kullanımı eklenirken hata oluştu: {e}")
        finally:
            conn.close()
    
    def add_mention_usage(self, group_id: int, mention: str, date: str, count: int = 1):
        """Mention kullanımını kaydeder veya günceller."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO mention_usage (group_id, mention, date, count) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(group_id, mention, date) DO UPDATE SET count = count + ?",
                (group_id, mention.lower(), date, count, count)
            )
            
            conn.commit()
        except Exception as e:
            logger.error(f"Mention kullanımı eklenirken hata oluştu: {e}")
        finally:
            conn.close()
    
    def get_top_words(self, group_id: Optional[int], start_date: str, end_date: str, limit: int = 10) -> List[Tuple[str, int]]:
        """Belirli bir tarih aralığındaki en popüler kelimeleri döndürür."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            if group_id:
                cursor.execute(
                    "SELECT word, SUM(count) as total FROM word_usage "
                    "WHERE group_id = ? AND date BETWEEN ? AND ? "
                    "GROUP BY word ORDER BY total DESC LIMIT ?",
                    (group_id, start_date, end_date, limit)
                )
            else:
                cursor.execute(
                    "SELECT word, SUM(count) as total FROM word_usage "
                    "WHERE date BETWEEN ? AND ? "
                    "GROUP BY word ORDER BY total DESC LIMIT ?",
                    (start_date, end_date, limit)
                )
            
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"En popüler kelimeler getirilirken hata oluştu: {e}")
            return []
        finally:
            conn.close()
    
    def get_top_hashtags(self, group_id: Optional[int], start_date: str, end_date: str, limit: int = 10) -> List[Tuple[str, int]]:
        """Belirli bir tarih aralığındaki en popüler hashtag'leri döndürür."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            if group_id:
                cursor.execute(
                    "SELECT hashtag, SUM(count) as total FROM hashtag_usage "
                    "WHERE group_id = ? AND date BETWEEN ? AND ? "
                    "GROUP BY hashtag ORDER BY total DESC LIMIT ?",
                    (group_id, start_date, end_date, limit)
                )
            else:
                cursor.execute(
                    "SELECT hashtag, SUM(count) as total FROM hashtag_usage "
                    "WHERE date BETWEEN ? AND ? "
                    "GROUP BY hashtag ORDER BY total DESC LIMIT ?",
                    (start_date, end_date, limit)
                )
            
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"En popüler hashtag'ler getirilirken hata oluştu: {e}")
            return []
        finally:
            conn.close()
    
    def get_top_mentions(self, group_id: Optional[int], start_date: str, end_date: str, limit: int = 10) -> List[Tuple[str, int]]:
        """Belirli bir tarih aralığındaki en popüler mention'ları döndürür."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            if group_id:
                cursor.execute(
                    "SELECT mention, SUM(count) as total FROM mention_usage "
                    "WHERE group_id = ? AND date BETWEEN ? AND ? "
                    "GROUP BY mention ORDER BY total DESC LIMIT ?",
                    (group_id, start_date, end_date, limit)
                )
            else:
                cursor.execute(
                    "SELECT mention, SUM(count) as total FROM mention_usage "
                    "WHERE date BETWEEN ? AND ? "
                    "GROUP BY mention ORDER BY total DESC LIMIT ?",
                    (start_date, end_date, limit)
                )
            
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"En popüler mention'lar getirilirken hata oluştu: {e}")
            return []
        finally:
            conn.close()
    
    def get_trend_change(self, group_id: Optional[int], item_type: str, prev_start: str, 
                          prev_end: str, curr_start: str, curr_end: str, limit: int = 10) -> List[Dict[str, Any]]:
        """İki farklı tarih aralığı arasındaki trend değişimini hesaplar."""
        table_map = {
            'word': 'word_usage',
            'hashtag': 'hashtag_usage',
            'mention': 'mention_usage'
        }
        
        item_col = item_type
        table = table_map.get(item_type)
        
        if not table:
            logger.error(f"Geçersiz öğe türü: {item_type}")
            return []
        
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Önceki dönem için sorgu
            if group_id:
                cursor.execute(
                    f"SELECT {item_col}, SUM(count) as total FROM {table} "
                    f"WHERE group_id = ? AND date BETWEEN ? AND ? "
                    f"GROUP BY {item_col}",
                    (group_id, prev_start, prev_end)
                )
            else:
                cursor.execute(
                    f"SELECT {item_col}, SUM(count) as total FROM {table} "
                    f"WHERE date BETWEEN ? AND ? "
                    f"GROUP BY {item_col}",
                    (prev_start, prev_end)
                )
            
            prev_data = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Şimdiki dönem için sorgu
            if group_id:
                cursor.execute(
                    f"SELECT {item_col}, SUM(count) as total FROM {table} "
                    f"WHERE group_id = ? AND date BETWEEN ? AND ? "
                    f"GROUP BY {item_col}",
                    (group_id, curr_start, curr_end)
                )
            else:
                cursor.execute(
                    f"SELECT {item_col}, SUM(count) as total FROM {table} "
                    f"WHERE date BETWEEN ? AND ? "
                    f"GROUP BY {item_col}",
                    (curr_start, curr_end)
                )
            
            curr_data = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Tüm benzersiz öğeleri topla
            all_items = set(prev_data.keys()) | set(curr_data.keys())
            
            # Trend değişimini hesapla
            trend_changes = []
            for item in all_items:
                prev_count = prev_data.get(item, 0)
                curr_count = curr_data.get(item, 0)
                
                # Değişim yüzdesi (önceki dönemde hiç yoksa yüzde değişim 100 olarak kabul edilir)
                if prev_count == 0:
                    percent_change = 100 if curr_count > 0 else 0
                else:
                    percent_change = ((curr_count - prev_count) / prev_count) * 100
                
                # Mutlak değişim
                abs_change = curr_count - prev_count
                
                trend_changes.append({
                    'item': item,
                    'prev_count': prev_count,
                    'curr_count': curr_count,
                    'abs_change': abs_change,
                    'percent_change': percent_change
                })
            
            # En büyük değişime göre sırala
            trend_changes.sort(key=lambda x: abs(x['percent_change']), reverse=True)
            
            return trend_changes[:limit]
        except Exception as e:
            logger.error(f"Trend değişimi hesaplanırken hata oluştu: {e}")
            return []
        finally:
            conn.close()
    
    def add_user_track(self, user_id: int, track_type: str, track_value: str) -> bool:
        """Kullanıcının takip etmek istediği kelime/hashtag'i ekler."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT OR IGNORE INTO user_tracks (user_id, track_type, track_value) VALUES (?, ?, ?)",
                (user_id, track_type, track_value.lower())
            )
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Kullanıcı takibi eklenirken hata oluştu: {e}")
            return False
        finally:
            conn.close()
    
    def remove_user_track(self, user_id: int, track_type: str, track_value: str) -> bool:
        """Kullanıcının takip ettiği kelime/hashtag'i kaldırır."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM user_tracks WHERE user_id = ? AND track_type = ? AND track_value = ?",
                (user_id, track_type, track_value.lower())
            )
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Kullanıcı takibi kaldırılırken hata oluştu: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_tracks(self, user_id: int) -> List[Dict[str, str]]:
        """Kullanıcının takip ettiği kelime/hashtag'leri döndürür."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT track_type, track_value FROM user_tracks WHERE user_id = ?",
                (user_id,)
            )
            
            return [{'type': row[0], 'value': row[1]} for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Kullanıcı takipleri getirilirken hata oluştu: {e}")
            return []
        finally:
            conn.close()
    
    def set_auto_report(self, group_id: int, report_type: str, enabled: bool, time: str) -> bool:
        """Grup için otomatik rapor ayarı yapar."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO auto_reports (group_id, report_type, enabled, time) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(group_id, report_type) DO UPDATE SET enabled = ?, time = ?",
                (group_id, report_type, 1 if enabled else 0, time, 1 if enabled else 0, time)
            )
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Otomatik rapor ayarlanırken hata oluştu: {e}")
            return False
        finally:
            conn.close()
    
    def get_auto_reports(self, time_now: str = None) -> List[Dict[str, Any]]:
        """Aktif otomatik raporları döndürür. Eğer time_now belirtilirse, o saatteki raporları getirir."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            if time_now:
                cursor.execute(
                    "SELECT ar.group_id, g.group_name, ar.report_type, ar.time FROM auto_reports ar "
                    "JOIN groups g ON ar.group_id = g.group_id "
                    "WHERE ar.enabled = 1 AND ar.time = ?",
                    (time_now,)
                )
            else:
                cursor.execute(
                    "SELECT ar.group_id, g.group_name, ar.report_type, ar.time FROM auto_reports ar "
                    "JOIN groups g ON ar.group_id = g.group_id "
                    "WHERE ar.enabled = 1"
                )
            
            return [
                {
                    'group_id': row[0],
                    'group_name': row[1],
                    'report_type': row[2],
                    'time': row[3]
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"Otomatik raporlar getirilirken hata oluştu: {e}")
            return []
        finally:
            conn.close()
    
    def update_group_settings(self, group_id: int, settings: Dict[str, Any]) -> bool:
        """Grup ayarlarını günceller."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Güncellenecek alanları ve değerlerini hazırla
            update_fields = []
            params = []
            
            for key, value in settings.items():
                update_fields.append(f"{key} = ?")
                params.append(value)
            
            if not update_fields:
                return False
            
            params.append(group_id)
            
            # Güncelleme sorgusunu oluştur
            query = f"UPDATE group_settings SET {', '.join(update_fields)} WHERE group_id = ?"
            
            cursor.execute(query, params)
            conn.commit()
            
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Grup ayarları güncellenirken hata oluştu: {e}")
            return False
        finally:
            conn.close()

   def get_group_settings(self, group_id: int) -> Dict[str, Any]:
        """Grup ayarlarını döndürür."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT min_word_length, max_words_in_report, exclude_common_words "
                "FROM group_settings WHERE group_id = ?",
                (group_id,)
            )
            
            row = cursor.fetchone()
            
            if row:
                return {
                    'min_word_length': row[0],
                    'max_words_in_report': row[1],
                    'exclude_common_words': row[2]
                }
            else:
                return {
                    'min_word_length': 3,
                    'max_words_in_report': 10,
                    'exclude_common_words': 1
                }
        except Exception as e:
            logger.error(f"Grup ayarları getirilirken hata oluştu: {e}")
            return {
                'min_word_length': 3,
                'max_words_in_report': 10,
                'exclude_common_words': 1
            }
        finally:
            conn.close()
    
    def get_groups(self) -> List[Dict[str, Any]]:
        """Tüm grupları döndürür."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute("SELECT group_id, group_name, joined_date FROM groups")
            
            return [
                {
                    'id': row[0],
                    'name': row[1],
                    'joined_date': row[2]
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"Gruplar getirilirken hata oluştu: {e}")
            return []
        finally:
            conn.close()


class TrendBot:
    def __init__(self, token: str):
        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher
        self.db = Database(DB_NAME)
        self.report_scheduler = None
        
        # Komut işleyicilerini ayarla
        self.setup_handlers()
        
        # Zamanlayıcı başlat
        self.start_scheduler()
    
    def setup_handlers(self):
        """Bot komut işleyicilerini ayarlar."""
        # Temel komutlar
        self.dispatcher.add_handler(CommandHandler("start", self.command_start))
        self.dispatcher.add_handler(CommandHandler("help", self.command_help))
        self.dispatcher.add_handler(CommandHandler("menu", self.command_menu))
        
        # Rapora özel komutlar
        self.dispatcher.add_handler(CommandHandler("gunluk", self.command_daily_report))
        self.dispatcher.add_handler(CommandHandler("haftalik", self.command_weekly_report))
        self.dispatcher.add_handler(CommandHandler("aylik", self.command_monthly_report))
        self.dispatcher.add_handler(CommandHandler("tum_zamanlar", self.command_all_time_report))
        
        # Takip komutları
        self.dispatcher.add_handler(CommandHandler("takip", self.command_track))
        self.dispatcher.add_handler(CommandHandler("takiplerim", self.command_my_tracks))
        
        # Ayar komutları
        self.dispatcher.add_handler(CommandHandler("ayarlar", self.command_settings))
        
        # Özel kelime/hashtag sorguları
        self.dispatcher.add_handler(CommandHandler("kelime", self.command_word_info))
        self.dispatcher.add_handler(CommandHandler("hashtag", self.command_hashtag_info))
        self.dispatcher.add_handler(CommandHandler("mention", self.command_mention_info))
        
        # Otomatik raporlama
        self.dispatcher.add_handler(CommandHandler("oto_rapor", self.command_auto_report))
        
        # Callback sorguları
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Mesaj işleyici
        self.dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command, self.handle_message
        ))
        
        # Hata işleyici
        self.dispatcher.add_error_handler(self.error_handler)
    
    def start_scheduler(self):
        """Zamanlayıcıyı başlatır ve otomatik raporlama için zamanlanmış görevleri ayarlar."""
        # Her saat başı kontrol et
        for hour in range(24):
            for minute in [0, 15, 30, 45]:
                time_str = f"{hour:02d}:{minute:02d}"
                schedule.every().day.at(time_str).do(self.send_scheduled_reports, time_str)
        
        # Zamanlayıcıyı ayrı bir thread'de çalıştır
        self.report_scheduler = threading.Thread(target=self.run_scheduler)
        self.report_scheduler.daemon = True
        self.report_scheduler.start()
    
    def run_scheduler(self):
        """Zamanlayıcı thread'i."""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Her dakika kontrol et
    
    def send_scheduled_reports(self, time_str: str):
        """Zamanlanmış raporları gönderir."""
        logger.info(f"Zamanlanmış raporlar kontrol ediliyor: {time_str}")
        
        reports = self.db.get_auto_reports(time_str)
        
        for report in reports:
            group_id = report['group_id']
            report_type = report['report_type']
            
            try:
                if report_type == 'daily':
                    self.send_daily_report(group_id)
                elif report_type == 'weekly':
                    self.send_weekly_report(group_id)
                elif report_type == 'monthly':
                    self.send_monthly_report(group_id)
                
                logger.info(f"Zamanlanmış rapor gönderildi: {report_type} - Grup ID: {group_id}")
            except Exception as e:
                logger.error(f"Zamanlanmış rapor gönderilirken hata oluştu: {e}")
    
    async def is_admin(self, update: Update, context: CallbackContext) -> bool:
        """Kullanıcının grup admini olup olmadığını kontrol eder."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Özel sohbetlerde herkes "admin" olarak kabul edilir
        if update.effective_chat.type == 'private':
            return True
        
        try:
            # Kullanıcının grup içindeki bilgilerini al
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            
            # Admin veya creator ise True döndür
            return chat_member.status in ('administrator', 'creator')
        except Exception as e:
            logger.error(f"Admin kontrolü sırasında hata: {e}")
            return False
    
    def command_start(self, update: Update, context: CallbackContext):
        """Start komutunu işler."""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Grup sohbeti ise
        if update.effective_chat.type in ['group', 'supergroup']:
            group_name = update.effective_chat.title
            
            # Grubu veritabanına ekle
            self.db.add_group(chat_id, group_name)
            
            message = (
                f"Merhaba! Ben TrendBot, mesaj trendlerini analiz eden bir botum. 🤖\n\n"
                f"Bu gruptaki mesajları analiz ederek popüler kelimeler, hashtag'ler ve mention'lar hakkında "
                f"günlük, haftalık ve aylık raporlar oluşturacağım.\n\n"
                f"Komutlarımı görmek için /help yazabilirsiniz."
            )
        else:  # Özel sohbet ise
            message = (
                f"Merhaba {user.first_name}! Ben TrendBot, mesaj trendlerini analiz eden bir botum. 🤖\n\n"
                f"Beni bir gruba ekleyerek, o gruptaki mesajları analiz edebilir ve "
                f"popüler kelimeler, hashtag'ler ve mention'lar hakkında raporlar alabilirsiniz.\n\n"
                f"Komutlarımı görmek için /help yazabilirsiniz.\n"
                f"Ana menüyü açmak için /menu yazabilirsiniz."
            )
        
        context.bot.send_message(chat_id=chat_id, text=message)
    
    def command_help(self, update: Update, context: CallbackContext):
        """Help komutunu işler."""
        chat_id = update.effective_chat.id
        
        help_text = (
            "📊 *TrendBot Komutları* 📊\n\n"
            "*Temel Komutlar:*\n"
            "/start - Botu başlat\n"
            "/help - Bu yardım mesajını göster\n"
            "/menu - Ana menüyü aç\n\n"
            
            "*Rapor Komutları:*\n"
            "/gunluk - Günlük trend raporu\n"
            "/haftalik - Haftalık trend raporu\n"
            "/aylik - Aylık trend raporu\n"
            "/tum_zamanlar - Tüm zamanların trend raporu\n\n"
            
            "*Takip Komutları:*\n"
            "/takip <kelime/hashtag/mention> <değer> - Belirli bir kelime/hashtag/mention'ı takip et\n"
            "/takiplerim - Takip ettiğiniz öğeleri listele\n\n"
            
            "*Sorgu Komutları:*\n"
            "/kelime <kelime> - Belirli bir kelimenin istatistiklerini göster\n"
            "/hashtag <hashtag> - Belirli bir hashtag'in istatistiklerini göster\n"
            "/mention <mention> - Belirli bir mention'ın istatistiklerini göster\n\n"
            
            "*Ayarlar (Sadece Grup Adminleri):*\n"
            "/ayarlar - Grup ayarlarını düzenle\n"
            "/oto_rapor <daily/weekly/monthly> <saat> - Otomatik rapor zamanlaması ayarla\n"
        )
        
        context.bot.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    def command_menu(self, update: Update, context: CallbackContext):
        """Ana menüyü gösterir."""
        chat_id = update.effective_chat.id
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Raporlar", callback_data="menu_reports"),
                InlineKeyboardButton("🔍 Takip Et", callback_data="menu_track")
            ],
            [
                InlineKeyboardButton("⚙️ Ayarlar", callback_data="menu_settings"),
                InlineKeyboardButton("❓ Yardım", callback_data="menu_help")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.bot.send_message(
            chat_id=chat_id,
            text="📱 *TrendBot Ana Menü* 📱\n\nLütfen bir seçenek seçin:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return MAIN_MENU
    
    def button_callback(self, update: Update, context: CallbackContext):
        """Buton callback'lerini işler."""
        query = update.callback_query
        query.answer()
        
        data = query.data
        chat_id = query.message.chat_id
        
        # Ana menü callbacks
        if data == "menu_reports":
            self.show_reports_menu(update, context)
        elif data == "menu_track":
            self.show_track_menu(update, context)
        elif data == "menu_settings":
            self.show_settings_menu(update, context)
        elif data == "menu_help":
            self.command_help(update, context)
        
        # Rapor menüsü callbacks
        elif data == "report_daily":
            self.command_daily_report(update, context)
        elif data == "report_weekly":
            self.command_weekly_report(update, context)
        elif data == "report_monthly":
            self.command_monthly_report(update, context)
        elif data == "report_alltime":
            self.command_all_time_report(update, context)
        elif data == "report_back":
            self.command_menu(update, context)
        
        # Takip menüsü callbacks
        elif data.startswith("track_"):
            track_type = data.split("_")[1]
            context.user_data["track_type"] = track_type
            
            query.edit_message_text(
                text=f"Takip etmek istediğiniz {track_type} değerini yazın:",
                parse_mode=ParseMode.MARKDOWN
            )
        elif data == "track_list":
            self.command_my_tracks(update, context)
        elif data == "track_back":
            self.command_menu(update, context)
        
        # Ayarlar menüsü callbacks
        elif data.startswith("settings_"):
            if data == "settings_back":
                self.command_menu(update, context)
            elif data == "settings_auto_report":
                self.show_auto_report_menu(update, context)
            elif data == "settings_word_length":
                self.show_word_length_menu(update, context)
            elif data == "settings_max_words":
                self.show_max_words_menu(update, context)
            elif data == "settings_exclude_common":
                self.toggle_exclude_common(update, context)
        
        # Otomatik rapor menüsü callbacks
        elif data.startswith("auto_report_"):
            parts = data.split("_")
            if len(parts) >= 3:
                report_type = parts[2]
                self.setup_auto_report(update, context, report_type)
    
    def show_reports_menu(self, update: Update, context: CallbackContext):
        """Rapor menüsünü gösterir."""
        query = update.callback_query
        
        keyboard = [
            [
                InlineKeyboardButton("📅 Günlük Rapor", callback_data="report_daily"),
                InlineKeyboardButton("📆 Haftalık Rapor", callback_data="report_weekly")
            ],
            [
                InlineKeyboardButton("📈 Aylık Rapor", callback_data="report_monthly"),
                InlineKeyboardButton("📊 Tüm Zamanlar", callback_data="report_alltime")
            ],
            [
                InlineKeyboardButton("⬅️ Geri", callback_data="report_back")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            text="📊 *Rapor Menüsü* 📊\n\nLütfen bir rapor türü seçin:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return REPORTS_MENU
    
    def show_track_menu(self, update: Update, context: CallbackContext):
        """Takip menüsünü gösterir."""
        query = update.callback_query
        
        keyboard = [
            [
                InlineKeyboardButton("🔤 Kelime Takip Et", callback_data="track_word"),
                InlineKeyboardButton("#️⃣ Hashtag Takip Et", callback_data="track_hashtag")
            ],
            [
                InlineKeyboardButton("👤 Mention Takip Et", callback_data="track_mention"),
                InlineKeyboardButton("📋 Takip Listem", callback_data="track_list")
            ],
            [
                InlineKeyboardButton("⬅️ Geri", callback_data="track_back")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            text="🔍 *Takip Menüsü* 🔍\n\nNeyi takip etmek istersiniz?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return TRACK_MENU

async def show_settings_menu(update: Update, context: CallbackContext) -> int:
    """Ayarlar menüsünü gösterir."""
    query = update.callback_query
    if query:
        await query.answer()
    
    chat_id = update.effective_chat.id
    
    # Grup ayarlarını getir
    settings = db.get_group_settings(chat_id)
    
    # Otomatik raporlamaları getir
    auto_reports = db.get_auto_reports(chat_id)
    
    daily_report_status = "Aktif ✅" if any(r[0] == "daily" and r[1] for r in auto_reports) else "Pasif ❌"
    weekly_report_status = "Aktif ✅" if any(r[0] == "weekly" and r[1] for r in auto_reports) else "Pasif ❌"
    monthly_report_status = "Aktif ✅" if any(r[0] == "monthly" and r[1] for r in auto_reports) else "Pasif ❌"
    
    keyboard = [
        [InlineKeyboardButton(f"Min. Kelime Uzunluğu: {settings['min_word_length']}", callback_data="settings_min_length")],
        [InlineKeyboardButton(f"Rapor Kelime Sayısı: {settings['max_words_in_report']}", callback_data="settings_max_words")],
        [InlineKeyboardButton(
            f"Yaygın Kelimeleri Filtrele: {'Açık ✅' if settings['exclude_common_words'] else 'Kapalı ❌'}", 
            callback_data="settings_toggle_common"
        )],
        [InlineKeyboardButton(f"Günlük Rapor: {daily_report_status}", callback_data="settings_toggle_daily")],
        [InlineKeyboardButton(f"Haftalık Rapor: {weekly_report_status}", callback_data="settings_toggle_weekly")],
        [InlineKeyboardButton(f"Aylık Rapor: {monthly_report_status}", callback_data="settings_toggle_monthly")],
        [InlineKeyboardButton("🔙 Geri", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.edit_text(
        "📊 *TrendBot Ayarları*\n\n"
        "Aşağıdaki ayarları değiştirmek için ilgili butona tıklayın:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return SETTINGS_MENU

async def toggle_setting(update: Update, context: CallbackContext) -> int:
    """Ayarları değiştirir."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    data = query.data
    
    # Grubun admin kontrolü
    user_id = update.effective_user.id
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        is_admin = chat_member.status in ["creator", "administrator"]
        
        if not is_admin:
            await query.message.reply_text("Bu komutu kullanabilmek için grup yöneticisi olmanız gerekiyor.")
            return SETTINGS_MENU
    except Exception as e:
        logger.error(f"Admin kontrolü yapılırken hata oluştu: {e}")
        # Özel mesajlarda devam et
        if chat_id == user_id:
            is_admin = True
        else:
            return SETTINGS_MENU
    
    if data == "settings_toggle_common":
        settings = db.get_group_settings(chat_id)
        db.update_group_settings(chat_id, exclude_common_words=not settings["exclude_common_words"])
    
    elif data == "settings_toggle_daily":
        reports = db.get_auto_reports(chat_id)
        is_enabled = any(r[0] == "daily" and r[1] for r in reports)
        db.set_auto_report(chat_id, "daily", not is_enabled)
    
    elif data == "settings_toggle_weekly":
        reports = db.get_auto_reports(chat_id)
        is_enabled = any(r[0] == "weekly" and r[1] for r in reports)
        db.set_auto_report(chat_id, "weekly", not is_enabled)
    
    elif data == "settings_toggle_monthly":
        reports = db.get_auto_reports(chat_id)
        is_enabled = any(r[0] == "monthly" and r[1] for r in reports)
        db.set_auto_report(chat_id, "monthly", not is_enabled)
    
    elif data == "settings_min_length":
        await update.effective_message.edit_text(
            "Minimum kelime uzunluğunu değiştirmek için 2-10 arasında bir sayı girin:\n"
            "(Sadece bu uzunluktan daha uzun kelimeler analize dahil edilecektir)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="cancel_input")]])
        )
        context.user_data["waiting_for"] = "min_length"
        return SETTINGS_MENU
    
    elif data == "settings_max_words":
        await update.effective_message.edit_text(
            "Raporda gösterilecek maksimum kelime sayısını değiştirmek için 5-50 arasında bir sayı girin:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="cancel_input")]])
        )
        context.user_data["waiting_for"] = "max_words"
        return SETTINGS_MENU
    
    # Ayarlar menüsünü tekrar göster
    return await show_settings_menu(update, context)

async def handle_settings_input(update: Update, context: CallbackContext) -> int:
    """Ayarlar için girilen değerleri işler."""
    user_input = update.message.text
    chat_id = update.effective_chat.id
    waiting_for = context.user_data.get("waiting_for")
    
    if waiting_for == "min_length":
        try:
            value = int(user_input)
            if 2 <= value <= 10:
                db.update_group_settings(chat_id, min_word_length=value)
                await update.message.reply_text(f"Minimum kelime uzunluğu {value} olarak ayarlandı.")
            else:
                await update.message.reply_text("Lütfen 2-10 arasında bir değer girin.")
        except ValueError:
            await update.message.reply_text("Lütfen geçerli bir sayı girin.")
    
    elif waiting_for == "max_words":
        try:
            value = int(user_input)
            if 5 <= value <= 50:
                db.update_group_settings(chat_id, max_words_in_report=value)
                await update.message.reply_text(f"Raporda gösterilecek maksimum kelime sayısı {value} olarak ayarlandı.")
            else:
                await update.message.reply_text("Lütfen 5-50 arasında bir değer girin.")
        except ValueError:
            await update.message.reply_text("Lütfen geçerli bir sayı girin.")
    
    context.user_data.pop("waiting_for", None)
    
    # Ayarlar menüsünü tekrar göster (özel mesaj olarak)
    keyboard = [
        [InlineKeyboardButton("📊 Ayarlar Menüsüne Dön", callback_data="show_settings")]
    ]
    await update.message.reply_text(
        "Ayarlar güncellendi. Menüye dönmek için aşağıdaki butona tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SETTINGS_MENU

async def show_track_menu(update: Update, context: CallbackContext) -> int:
    """Takip menüsünü gösterir."""
    query = update.callback_query
    if query:
        await query.answer()
    
    user_id = update.effective_user.id
    
    # Kullanıcının takip ettiği öğeleri getir
    tracks = db.get_user_tracks(user_id)
    
    words = [t[1] for t in tracks if t[0] == "word"]
    hashtags = [t[1] for t in tracks if t[0] == "hashtag"]
    mentions = [t[1] for t in tracks if t[0] == "mention"]
    
    keyboard = [
        [InlineKeyboardButton("➕ Kelime Takip Et", callback_data="track_add_word")],
        [InlineKeyboardButton("➕ Hashtag Takip Et", callback_data="track_add_hashtag")],
        [InlineKeyboardButton("➕ Kullanıcı Takip Et", callback_data="track_add_mention")],
        [InlineKeyboardButton("❌ Takibi Kaldır", callback_data="track_remove")],
        [InlineKeyboardButton("📊 Takip Raporunu Gör", callback_data="track_report")],
        [InlineKeyboardButton("🔙 Geri", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "📈 *Takip Menüsü*\n\n"
    
    if words:
        message += "*Takip Ettiğiniz Kelimeler:*\n"
        for word in words:
            message += f"• {word}\n"
        message += "\n"
    
    if hashtags:
        message += "*Takip Ettiğiniz Hashtag'ler:*\n"
        for hashtag in hashtags:
            message += f"• #{hashtag}\n"
        message += "\n"
    
    if mentions:
        message += "*Takip Ettiğiniz Kullanıcılar:*\n"
        for mention in mentions:
            message += f"• @{mention}\n"
        message += "\n"
    
    if not words and not hashtags and not mentions:
        message += "_Henüz takip ettiğiniz bir kelime, hashtag veya kullanıcı bulunmamaktadır._\n\n"
    
    message += "Takip işlemleri için aşağıdaki menüyü kullanabilirsiniz:"
    
    await update.effective_message.edit_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return TRACK_MENU

async def add_track(update: Update, context: CallbackContext) -> int:
    """Takip eklemek için girdi ister."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "track_add_word":
        await update.effective_message.edit_text(
            "Takip etmek istediğiniz kelimeyi yazın:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="cancel_input")]])
        )
        context.user_data["waiting_for"] = "track_word"
    
    elif data == "track_add_hashtag":
        await update.effective_message.edit_text(
            "Takip etmek istediğiniz hashtag'i yazın (# işareti olmadan):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="cancel_input")]])
        )
        context.user_data["waiting_for"] = "track_hashtag"
    
    elif data == "track_add_mention":
        await update.effective_message.edit_text(
            "Takip etmek istediğiniz kullanıcı adını yazın (@ işareti olmadan):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="cancel_input")]])
        )
        context.user_data["waiting_for"] = "track_mention"
    
    return TRACK_MENU

async def handle_track_input(update: Update, context: CallbackContext) -> int:
    """Takip için girilen değerleri işler."""
    user_input = update.message.text.strip()
    user_id = update.effective_user.id
    waiting_for = context.user_data.get("waiting_for")
    
    if waiting_for == "track_word":
        # Kelime kontrolü
        if len(user_input) < 2:
            await update.message.reply_text("Kelime en az 2 karakter olmalıdır. Lütfen tekrar deneyin.")
            return TRACK_MENU
        
        if db.add_user_track(user_id, "word", user_input):
            await update.message.reply_text(f"'{user_input}' kelimesi takip listenize eklendi.")
        else:
            await update.message.reply_text("Bu kelime zaten takip listenizde bulunuyor.")
    
    elif waiting_for == "track_hashtag":
        # Hashtag kontrolü - # işaretini kaldır
        hashtag = user_input.replace("#", "")
        
        if len(hashtag) < 2:
            await update.message.reply_text("Hashtag en az 2 karakter olmalıdır. Lütfen tekrar deneyin.")
            return TRACK_MENU
        
        if db.add_user_track(user_id, "hashtag", hashtag):
            await update.message.reply_text(f"'#{hashtag}' hashtag'i takip listenize eklendi.")
        else:
            await update.message.reply_text("Bu hashtag zaten takip listenizde bulunuyor.")
    
    elif waiting_for == "track_mention":
        # Mention kontrolü - @ işaretini kaldır
        mention = user_input.replace("@", "")
        
        if len(mention) < 2:
            await update.message.reply_text("Kullanıcı adı en az 2 karakter olmalıdır. Lütfen tekrar deneyin.")
            return TRACK_MENU
        
        if db.add_user_track(user_id, "mention", mention):
            await update.message.reply_text(f"'@{mention}' kullanıcısı takip listenize eklendi.")
        else:
            await update.message.reply_text("Bu kullanıcı zaten takip listenizde bulunuyor.")
    
    context.user_data.pop("waiting_for", None)
    
    # Takip menüsüne dön butonu
    keyboard = [
        [InlineKeyboardButton("📊 Takip Menüsüne Dön", callback_data="show_track")]
    ]
    await update.message.reply_text(
        "Takip listesi güncellendi. Menüye dönmek için aşağıdaki butona tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return TRACK_MENU

async def remove_track(update: Update, context: CallbackContext) -> int:
    """Takip kaldırmak için listeyi gösterir."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Kullanıcının takip ettiği öğeleri getir
    tracks = db.get_user_tracks(user_id)
    
    if not tracks:
        await update.effective_message.edit_text(
            "Takip listenizde hiç öğe bulunmuyor.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="show_track")]])
        )
        return TRACK_MENU
    
    keyboard = []
    
    for track_type, track_value in tracks:
        display_value = track_value
        if track_type == "hashtag":
            display_value = f"#{track_value}"
        elif track_type == "mention":
            display_value = f"@{track_value}"
        
        keyboard.append([InlineKeyboardButton(
            f"❌ {display_value}", 
            callback_data=f"remove_{track_type}_{track_value}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Geri", callback_data="show_track")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.edit_text(
        "Kaldırmak istediğiniz takibi seçin:",
        reply_markup=reply_markup
    )
    
    return TRACK_MENU

async def handle_remove_track(update: Update, context: CallbackContext) -> int:
    """Takip kaldırma işlemini gerçekleştirir."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("remove_"):
        parts = data.split("_", 2)
        if len(parts) == 3:
            track_type = parts[1]
            track_value = parts[2]
            
            if db.remove_user_track(user_id, track_type, track_value):
                if track_type == "hashtag":
                    display_value = f"#{track_value}"
                elif track_type == "mention":
                    display_value = f"@{track_value}"
                else:
                    display_value = track_value
                
                await query.message.reply_text(f"'{display_value}' takipten kaldırıldı.")
    
    # Takip menüsünü tekrar göster
    return await show_track_menu(update, context)

async def show_track_report(update: Update, context: CallbackContext) -> int:
    """Kullanıcının takip ettiği öğelerin raporunu gösterir."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Kullanıcının takip ettiği öğeleri getir
    tracks = db.get_user_tracks(user_id)
    
    if not tracks:
        await update.effective_message.edit_text(
            "Takip listenizde hiç öğe bulunmuyor.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="show_track")]])
        )
        return TRACK_MENU
    
    message = "📊 *Takip Raporu*\n\n"
    
    # Takip edilen kelimelerin son 7 gündeki kullanımını getir
    for track_type, track_value in tracks:
        if track_type == "word":
            trend_data = db.get_word_trend(track_value, chat_id, 7)
            
            if trend_data:
                total_count = sum(count for _, count in trend_data)
                message += f"*'{track_value}' Kelimesi:* {total_count} kullanım (son 7 gün)\n"
            else:
                message += f"*'{track_value}' Kelimesi:* Henüz kullanım yok\n"
        
        elif track_type == "hashtag":
            # Hashtag trend verilerini getir
            trend_data = db.get_word_trend(f"#{track_value}", chat_id, 7)
            
            if trend_data:
                total_count = sum(count for _, count in trend_data)
                message += f"*'#{track_value}' Hashtag'i:* {total_count} kullanım (son 7 gün)\n"
            else:
                message += f"*'#{track_value}' Hashtag'i:* Henüz kullanım yok\n"
        
        elif track_type == "mention":
            # Mention trend verilerini getir
            trend_data = db.get_word_trend(f"@{track_value}", chat_id, 7)
            
            if trend_data:
                total_count = sum(count for _, count in trend_data)
                message += f"*'@{track_value}' Kullanıcısı:* {total_count} bahsedilme (son 7 gün)\n"
            else:
                message += f"*'@{track_value}' Kullanıcısı:* Henüz bahsedilme yok\n"
    
    # Graf oluştur
    filename = f"track_report_{user_id}.png"
    generate_track_graph(tracks, chat_id, filename)
    
    with open(filename, 'rb') as photo:
        await update.effective_message.reply_photo(
            photo,
            caption=message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Dosyayı temizle
    if os.path.exists(filename):
        os.remove(filename)
    
    # Takip menüsüne dön butonu
    keyboard = [
        [InlineKeyboardButton("🔙 Takip Menüsüne Dön", callback_data="show_track")]
    ]
    
    await update.effective_message.reply_text(
        "Takip raporu oluşturuldu. Menüye dönmek için aşağıdaki butona tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return TRACK_MENU

async def show_reports_menu(update: Update, context: CallbackContext) -> int:
    """Raporlar menüsünü gösterir."""
    query = update.callback_query
    if query:
        await query.answer()
    
    chat_id = update.effective_chat.id
    
    keyboard = [
        [InlineKeyboardButton("📊 Günlük Rapor", callback_data="report_daily")],
        [InlineKeyboardButton("📈 Haftalık Rapor", callback_data="report_weekly")],
        [InlineKeyboardButton("📉 Aylık Rapor", callback_data="report_monthly")],
        [InlineKeyboardButton("🔍 Özel Rapor", callback_data="report_custom")],
        [InlineKeyboardButton("📱 En Çok Mention'lar", callback_data="report_mentions")],
        [InlineKeyboardButton("🚀 Yükselen Trendler", callback_data="report_rising")],
        [InlineKeyboardButton("🔙 Geri", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.edit_text(
        "📊 *TrendBot Raporlar*\n\n"
        "Görüntülemek istediğiniz rapor türünü seçin:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return REPORTS_MENU

async def generate_report(update: Update, context: CallbackContext) -> int:
    """Seçilen raporu oluşturur ve gönderir."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = update.effective_chat.id
    
    report_type = data.split("_")[1]
    
    if report_type == "daily":
        days = 1
        title = "Günlük Trend Raporu"
    elif report_type == "weekly":
        days = 7
        title = "Haftalık Trend Raporu"
    elif report_type == "monthly":
        days = 30
        title = "Aylık Trend Raporu"
    elif report_type == "mentions":
        # Mention raporu özel işlenir
        await generate_mentions_report(update, context)
        return REPORTS_MENU
    elif report_type == "rising":
        # Yükselen trendler raporu özel işlenir
        await generate_rising_trends_report(update, context)
        return REPORTS_MENU
    elif report_type == "custom":
        # Özel rapor için tarih seçimi iste
        await update.effective_message.edit_text(
            "Özel rapor için kaç günlük bir süre istiyorsunuz? (1-90 arası bir sayı girin):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 İptal", callback_data="cancel_input")]])
        )
        context.user_data["waiting_for"] = "custom_report_days"
        return REPORTS_MENU
    else:
        return REPORTS_MENU
    
    # Raporu oluştur ve gönder
    await create_and_send_report(update.effective_message, chat_id, days, title)
    
    # Raporlar menüsüne dön buto
    keyboard = [
        [InlineKeyboardButton("🔙 Raporlar Menüsüne Dön", callback_data="show_reports")]
    ]
    
    await update.effective_message.reply_text(
        "Rapor oluşturuldu. Menüye dönmek için aşağıdaki butona tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return REPORTS_MENU

async def handle_custom_report_input(update: Update, context: CallbackContext) -> int:
    """Özel rapor için girilen gün sayısını işler."""
    user_input = update.message.text
    chat_id = update.effective_chat.id
    waiting_for = context.user_data.get("waiting_for")
    
    if waiting_for == "custom_report_days":
        try:
            days = int(user_input)
            if 1 <= days <= 90:
                # Raporu oluştur ve gönder
                await create_and_send_report(update.message, chat_id, days, f"Özel {days} Günlük Rapor")
            else:
                await update.message.reply_text("Lütfen 1-90 arasında bir değer girin.")
        except ValueError:
            await update.message.reply_text("Lütfen geçerli bir sayı girin.")
    
    context.user_data.pop("waiting_for", None)
    
    # Raporlar menüsüne dön butonu
    keyboard = [
        [InlineKeyboardButton("🔙 Raporlar Menüsüne Dön", callback_data="show_reports")]
    ]
    
    await update.message.reply_text(
        "Rapor oluşturuldu. Menüye dönmek için aşağıdaki butona tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return REPORTS_MENU

async def create_and_send_report(message, chat_id: int, days: int, title: str):
    """Trend raporunu oluşturur ve gönderir."""
    settings = db.get_group_settings(chat_id)
    limit = settings["max_words_in_report"]
    
    # En çok kullanılan kelimeleri getir
    top_words = db.get_top_words(chat_id, days, limit)
    
    # En çok kullanılan hashtag'leri getir
    top_hashtags = db.get_top_hashtags(chat_id, days, limit)
    
    # Rapor mesajını oluştur
    report_message = f"📊 *{title}*\n\n"
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if days == 1:
        time_period = "bugün"
    else:
        time_period = f"son {days} gün"
    
    report_message += f"*Rapor Tarihi:* {current_time}\n"
    report_message += f"*Kapsanan Süre:* {time_period}\n\n"
    
    if top_words:
        report_message += "*En Çok Kullanılan Kelimeler:*\n"
        for i, (word, count) in enumerate(top_words, 1):
            report_message += f"{i}. {word}: {count} kullanım\n"
        report_message += "\n"
    else:
        report_message += "*En Çok Kullanılan Kelimeler:* Veri yok\n\n"
    
    if top_hashtags:
        report_message += "*En Çok Kullanılan Hashtag'ler:*\n"
        for i, (hashtag, count) in enumerate(top_hashtags, 1):
            report_message += f"{i}. #{hashtag}: {count} kullanım\n"
        report_message += "\n"
    else:
        report_message += "*En Çok Kullanılan Hashtag'ler:* Veri yok\n\n"
    
    # Graf oluştur
    filename = f"trend_report_{chat_id}_{days}.png"
    generate_trend_graph(top_words, top_hashtags, filename)
    
    with open(filename, 'rb') as photo:
        await message.reply_photo(
            photo,
            caption=report_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Dosyayı temizle
    if os.path.exists(filename):
        os.remove(filename)

async def generate_mentions_report(update: Update, context: CallbackContext):
    """Mention raporunu oluşturur ve gönderir."""
    chat_id = update.effective_chat.id
    settings = db.get_group_settings(chat_id)
    limit = settings["max_words_in_report"]
    
    # En çok kullanılan mention'ları getir (son 7 gün)
    top_mentions = db.get_top_mentions(chat_id, 7, limit)
    
    # Rapor mesajını oluştur
    report_message = "📱 *En Çok Bahsedilen Kullanıcılar*\n\n"
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    report_message += f"*Rapor Tarihi:* {current_time}\n"
    report_message += "*Kapsanan Süre:* son 7 gün\n\n"
    
    if top_mentions:
        for i, (mention, count) in enumerate(top_mentions, 1):
            report_message += f"{i}. {mention}: {count} kez bahsedildi\n"
    else:
        report_message += "Bu süre içinde henüz bir mention bulunmuyor.\n"
    
    # Graf oluştur
    filename = f"mentions_report_{chat_id}.png"
    generate_mentions_graph(top_mentions, filename)
    
    with open(filename, 'rb') as photo:
        await update.effective_message.reply_photo(
            photo,
            caption=report_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Dosyayı temizle
    if os.path.exists(filename):
        os.remove(filename)
    
    # Raporlar menüsüne dön butonu
    keyboard = [
        [InlineKeyboardButton("🔙 Raporlar Menüsüne Dön", callback_data="show_reports")]
    ]
    
    await update.effective_message.reply_text(
        "Mention raporu oluşturuldu. Menüye dönmek için aşağıdaki butona tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def generate_rising_trends_report(update: Update, context: CallbackContext):
    """Yükselen trendler raporunu oluşturur ve gönderir."""
    chat_id = update.effective_chat.id
    
    # Hızla yükselen kelimeleri getir
    rising_trends = db.get_rising_trends(chat_id, 7, 10)
    
    # Rapor mesajını oluştur
    report_message = "🚀 *Hızla Yükselen Trendler*\n\n"
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    report_message += f"*Rapor Tarihi:* {current_time}\n"
    report_message += "*Kapsanan Süre:* son 7 gün\n\n"
    
    if rising_trends:
        for i, (word, growth_rate) in enumerate(rising_trends, 1):
            report_message += f"{i}. {word}: {growth_rate:.1f}x büyüme\n"
    else:
        report_message += "Bu süre içinde henüz yükselen trend bulunmuyor.\n"
    
    # Graf oluştur
    filename = f"rising_trends_{chat_id}.png"
    generate_rising_trends_graph(rising_trends, filename)
    
    with open(filename, 'rb') as photo:
        await update.effective_message.reply_photo(
            photo,
            caption=report_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Dosyayı temizle
    if os.path.exists(filename):
        os.remove(filename)
    
    # Raporlar menüsüne dön butonu
    keyboard = [
        [InlineKeyboardButton("🔙 Raporlar Menüsüne Dön", callback_data="show_reports")]
    ]
    
    await update.effective_message.reply_text(
        "Yükselen trendler raporu oluşturuldu. Menüye dönmek için aşağıdaki butona tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def generate_track_graph(tracks, chat_id, filename):
    """Takip edilen kelime/hashtag/mention için grafik oluşturur."""
    plt.figure(figsize=(10, 6))
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    legend_items = []
    
    for i, (track_type, track_value, data) in enumerate(tracks):
        if not data:
            continue
            
        dates = [d[0] for d in data]
        counts = [d[1] for d in data]
        
        # Tarihleri datetime nesnelerine dönüştür
        x_values = [datetime.datetime.strptime(d, "%Y-%m-%d") for d in dates]
        
        color = colors[i % len(colors)]
        line, = plt.plot(x_values, counts, marker='o', linestyle='-', color=color)
        
        if track_type == "word":
            label = f"Kelime: {track_value}"
        elif track_type == "hashtag":
            label = f"Hashtag: #{track_value}"
        else:
            label = f"Mention: @{track_value}"
            
        legend_items.append((line, label))
    
    if not legend_items:
        plt.close()
        return None
    
    plt.title('Takip Edilen Öğelerin Kullanım Trendi', fontsize=14)
    plt.xlabel('Tarih', fontsize=12)
    plt.ylabel('Kullanım Sayısı', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Efsaneyi ekle
    lines, labels = zip(*legend_items)
    plt.legend(lines, labels, loc='upper left')
    
    # Tarih formatını ayarla
    plt.gcf().autofmt_xdate()
    
    # Eksenleri düzenle
    plt.tight_layout()
    
    # Dosyayı kaydet
    full_path = f"{filename}.png"
    plt.savefig(full_path)
    plt.close()
    
    return full_path

async def generate_word_cloud(words, filename):
    """Kelime bulutu oluşturur."""
    try:
        from wordcloud import WordCloud
        
        # Kelime frekanslarını sözlüğe dönüştür
        word_freq = {word: count for word, count in words}
        
        # Kelime bulutu oluştur
        wc = WordCloud(width=800, height=400, background_color="white", 
                       max_words=100, colormap="viridis", 
                       contour_width=1, contour_color='steelblue')
        
        wc.generate_from_frequencies(word_freq)
        
        # Kaydet
        full_path = f"{filename}.png"
        wc.to_file(full_path)
        
        return full_path
    except ImportError:
        logger.warning("WordCloud kütüphanesi bulunamadı. Kelime bulutu oluşturulamıyor.")
        return None
    except Exception as e:
        logger.error(f"Kelime bulutu oluşturulurken hata: {e}")
        return None

async def generate_report(update: Update, context: CallbackContext, report_type="daily", group_id=None):
    """Rapor oluşturur ve gönderir."""
    chat_id = group_id if group_id else update.effective_chat.id
    
    # Rapor türüne göre gün sayısını belirle
    if report_type == "daily":
        days = 1
        title = "Günlük Trend Raporu"
    elif report_type == "weekly":
        days = 7
        title = "Haftalık Trend Raporu"
    elif report_type == "monthly":
        days = 30
        title = "Aylık Trend Raporu"
    else:
        days = 1
        title = "Trend Raporu"
    
    # Grup ayarlarını getir
    settings = db.get_group_settings(chat_id)
    limit = settings["max_words_in_report"]
    
    # Verileri getir
    top_words = db.get_top_words(chat_id, days, limit)
    top_hashtags = db.get_top_hashtags(chat_id, days, limit)
    top_mentions = db.get_top_mentions(chat_id, days, limit)
    rising_trends = db.get_rising_trends(chat_id, days, min(limit, 5))
    
    # Rapor metni oluştur
    message = f"📊 *{title}*\n\n"
    
    if top_words:
        message += "*En Çok Kullanılan Kelimeler:*\n"
        for i, (word, count) in enumerate(top_words, 1):
            message += f"{i}. {word}: {count} kez\n"
        message += "\n"
    
    if top_hashtags:
        message += "*En Popüler Hashtag'ler:*\n"
        for i, (hashtag, count) in enumerate(top_hashtags, 1):
            message += f"{i}. #{hashtag}: {count} kez\n"
        message += "\n"
    
    if top_mentions:
        message += "*En Çok Bahsedilen Kullanıcılar:*\n"
        for i, (mention, count) in enumerate(top_mentions, 1):
            message += f"{i}. @{mention}: {count} kez\n"
        message += "\n"
    
    if rising_trends:
        message += "*🔥 Yükselen Trendler:*\n"
        for i, (word, growth) in enumerate(rising_trends, 1):
            growth_percent = (growth - 1) * 100
            message += f"{i}. {word}: %{growth_percent:.1f} artış\n"
        message += "\n"
    
    message += f"_{datetime.datetime.now().strftime('%d.%m.%Y %H:%M')} itibarıyla_"
    
    # Kelime bulutu oluştur
    if top_words and len(top_words) >= 10:
        cloud_path = await generate_word_cloud(top_words, f"wordcloud_{chat_id}")
        if cloud_path:
            with open(cloud_path, 'rb') as img:
                await context.bot.send_photo(chat_id=chat_id, photo=img, caption=f"📊 {title} - Kelime Bulutu")
                os.remove(cloud_path)  # Dosyayı temizle
    
    # Grafikler
    if report_type in ["weekly", "monthly"]:
        # Top 5 kelime için trend grafiği
        top5_words = top_words[:5]
        if top5_words:
            plt.figure(figsize=(10, 6))
            
            for word, _ in top5_words:
                trend_data = db.get_word_trend(word, chat_id, days)
                if trend_data:
                    dates = [d[0] for d in trend_data]
                    counts = [d[1] for d in trend_data]
                    
                    # Tarihleri datetime nesnelerine dönüştür
                    x_values = [datetime.datetime.strptime(d, "%Y-%m-%d") for d in dates]
                    
                    plt.plot(x_values, counts, marker='o', linestyle='-', label=word)
            
            plt.title(f'En Popüler 5 Kelimenin {days} Günlük Trendi', fontsize=14)
            plt.xlabel('Tarih', fontsize=12)
            plt.ylabel('Kullanım Sayısı', fontsize=12)
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.legend(loc='upper left')
            plt.gcf().autofmt_xdate()
            plt.tight_layout()
            
            graph_path = f"trend_graph_{chat_id}.png"
            plt.savefig(graph_path)
            plt.close()
            
            with open(graph_path, 'rb') as img:
                await context.bot.send_photo(chat_id=chat_id, photo=img, caption=f"📈 {title} - Trend Grafiği")
                os.remove(graph_path)  # Dosyayı temizle
    
    # Mesajı gönder
    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode=ParseMode.MARKDOWN
    )

async def get_track_report(update: Update, context: CallbackContext) -> int:
    """Takip raporu oluşturur ve gönderir."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Kullanıcının takip ettiği öğeleri getir
    tracks = db.get_user_tracks(user_id)
    
    if not tracks:
        await update.effective_message.edit_text(
            "Takip listenizde hiç öğe bulunmuyor.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="show_track")]])
        )
        return TRACK_MENU
    
    # Son 30 günlük verileri al
    days = 30
    track_data = []
    
    for track_type, track_value in tracks:
        if track_type == "word":
            data = db.get_word_trend(track_value, days=days)
            track_data.append((track_type, track_value, data))
        elif track_type == "hashtag":
            # Hashtag trendini getir (yapmak gerekirse burada)
            pass
        elif track_type == "mention":
            # Mention trendini getir (yapmak gerekirse burada)
            pass
    
    # Grafik oluştur
    graph_path = generate_track_graph(track_data, user_id, f"track_graph_{user_id}")
    
    message = "📊 *Takip Raporu*\n\n"
    
    for track_type, track_value, data in track_data:
        if data:
            total_count = sum(count for _, count in data)
            current_count = data[-1][1] if data else 0
            
            if track_type == "word":
                message += f"*Kelime:* {track_value}\n"
            elif track_type == "hashtag":
                message += f"*Hashtag:* #{track_value}\n"
            else:
                message += f"*Mention:* @{track_value}\n"
                
            message += f"Son 30 günde toplam: {total_count} kez\n"
            message += f"Bugün: {current_count} kez\n\n"
    
    # Grafiği gönder
    if graph_path:
        with open(graph_path, 'rb') as img:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=img,
                caption="📈 Takip ettiğiniz öğelerin son 30 günlük trendi"
            )
            os.remove(graph_path)  # Dosyayı temizle
    
    keyboard = [
        [InlineKeyboardButton("🔙 Geri", callback_data="show_track")]
    ]
    
    await update.effective_message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return TRACK_MENU

async def start(update: Update, context: CallbackContext) -> int:
    """Bot başlangıç komutunu işler."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    if chat_type in ["group", "supergroup"]:
        # Grupta başlatıldıysa
        group_name = update.effective_chat.title
        db.add_group(chat_id, group_name)
        
        keyboard = [
            [InlineKeyboardButton("📊 Ana Menü", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            f"Merhaba {user.first_name}! Ben TrendBot, grup mesajlarınızı analiz ederek "
            f"trend raporları oluşturmak için buradayım.\n\n"
            f"Bu grubu izlemeye başladım! Artık buradaki mesajları analiz ederek "
            f"günlük, haftalık ve aylık raporlar oluşturabilirim.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Özel mesajda başlatıldıysa
        keyboard = [
            [InlineKeyboardButton("📊 Ana Menü", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            f"Merhaba {user.first_name}! Ben TrendBot, grup mesajlarınızı analiz ederek "
            f"trend raporları oluşturmak için buradayım.\n\n"
            f"Beni bir gruba ekleyerek çalışmamı izleyebilirsiniz. Mesajlarınızı analiz ederek "
            f"en popüler kelimeleri, hashtag'leri ve mention'ları raporlayacağım.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    return MAIN_MENU

async def help_command(update: Update, context: CallbackContext) -> int:
    """Yardım komutunu işler."""
    keyboard = [
        [InlineKeyboardButton("📊 Ana Menü", callback_data="main_menu")]
    ]
    
    help_text = (
        "*TrendBot Yardım*\n\n"
        "TrendBot, grup mesajlarınızı analiz ederek trend raporları oluşturan bir bottur.\n\n"
        "*Ana Komutlar:*\n"
        "/start - Botu başlatır\n"
        "/help - Bu yardım mesajını gösterir\n"
        "/menu - Ana menüyü açar\n"
        "/report - Günlük trend raporu oluşturur\n"
        "/weekly - Haftalık trend raporu oluşturur\n"
        "/monthly - Aylık trend raporu oluşturur\n\n"
        "*Özellikler:*\n"
        "• Günlük, haftalık ve aylık trend raporları\n"
        "• Kelime, hashtag ve mention analizleri\n"
        "• Özel kelime/hashtag/mention takibi\n"
        "• Yükselen trendlerin tespiti\n"
        "• Görsel grafikler ve kelime bulutu\n"
        "• Otomatik raporlama ayarları\n\n"
        "Ana menüden tüm özelliklere erişebilirsiniz."
    )
    
    await update.message.reply_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return MAIN_MENU

async def show_main_menu(update: Update, context: CallbackContext) -> int:
    """Ana menüyü gösterir."""
    query = update.callback_query
    if query:
        await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📈 Günlük Rapor", callback_data="report_daily")],
        [InlineKeyboardButton("📊 Haftalık Rapor", callback_data="report_weekly")],
        [InlineKeyboardButton("📋 Aylık Rapor", callback_data="report_monthly")],
        [InlineKeyboardButton("🔍 Kelimeleri Takip Et", callback_data="show_track")],
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="show_settings")],
        [InlineKeyboardButton("❓ Yardım", callback_data="help")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.message.edit_text(
            "📊 *TrendBot Ana Menü*\n\n"
            "Trend analizi için aşağıdaki seçeneklerden birini seçin:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "📊 *TrendBot Ana Menü*\n\n"
            "Trend analizi için aşağıdaki seçeneklerden birini seçin:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return MAIN_MENU

async def handle_buttons(update: Update, context: CallbackContext) -> int:
    """Buton tıklamalarını işler."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Ana menü butonları
    if data == "main_menu":
        return await show_main_menu(update, context)
    
    elif data == "help":
        help_text = (
            "*TrendBot Yardım*\n\n"
            "TrendBot, grup mesajlarınızı analiz ederek trend raporları oluşturan bir bottur.\n\n"
            "*Ana Komutlar:*\n"
            "/start - Botu başlatır\n"
            "/help - Bu yardım mesajını gösterir\n"
            "/menu - Ana menüyü açar\n"
            "/report - Günlük trend raporu oluşturur\n"
            "/weekly - Haftalık trend raporu oluşturur\n"
            "/monthly - Aylık trend raporu oluşturur\n\n"
            "*Özellikler:*\n"
            "• Günlük, haftalık ve aylık trend raporları\n"
            "• Kelime, hashtag ve mention analizleri\n"
            "• Özel kelime/hashtag/mention takibi\n"
            "• Yükselen trendlerin tespiti\n"
            "• Görsel grafikler ve kelime bulutu\n"
            "• Otomatik raporlama ayarları\n\n"
            "Ana menüden tüm özelliklere erişebilirsiniz."
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]
        ]
        
        await query.message.edit_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return MAIN_MENU
    
    # Rapor butonları
    elif data.startswith("report_"):
        report_type = data.split("_")[1]
        await generate_report(update, context, report_type)
        
        # Rapor sonrası ana menüye dönme butonu
        keyboard = [
            [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]
        ]
        
        await query.message.edit_text(
            "Rapor oluşturuldu! Ana menüye dönmek için butona tıklayın:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return MAIN_MENU
    
    # Takip menüsü
    elif data == "show_track":
        return await show_track_menu(update, context)
    
    elif data == "track_report":
        return await get_track_report(update, context)
    
    elif data.startswith("track_add_"):
        return await add_track(update, context)
    
    elif data == "track_remove":
        # Takip kaldırma menüsü
        user_id = update.effective_user.id
        tracks = db.get_user_tracks(user_id)
        
        if not tracks:
            await query.message.edit_text(
                "Takip listenizde hiç öğe bulunmuyor.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="show_track")]])
            )
            return TRACK_MENU
        
        keyboard = []
        
        for track_type, track_value in tracks:
            if track_type == "word":
                display = f"❌ Kelime: {track_value}"
            elif track_type == "hashtag":
                display = f"❌ Hashtag: #{track_value}"
            else:
                display = f"❌ Mention: @{track_value}"
                
            keyboard.append([InlineKeyboardButton(display, callback_data=f"remove_{track_type}_{track_value}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Geri", callback_data="show_track")])
        
        await query.message.edit_text(
            "Kaldırmak istediğiniz takibi seçin:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return TRACK_MENU
    
    elif data.startswith("remove_"):
        # Takip kaldırma işlemi
        parts = data.split("_", 2)
        if len(parts) == 3:
            track_type = parts[1]
            track_value = parts[2]
            
            user_id = update.effective_user.id
            
            if db.remove_user_track(user_id, track_type, track_value):
                if track_type == "word":
                    message = f"'{track_value}' kelimesi takip listenizden kaldırıldı."
                elif track_type == "hashtag":
                    message = f"'#{track_value}' hashtag'i takip listenizden kaldırıldı."
                else:
                    message = f"'@{track_value}' kullanıcısı takip listenizden kaldırıldı."
            else:
                message = "Takip kaldırılırken bir hata oluştu."
            
            await query.message.edit_text(
                message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Takip Menüsüne Dön", callback_data="show_track")]])
            )
        
        return TRACK_MENU
    
    # Ayarlar menüsü
    elif data == "show_settings":
        return await show_settings_menu(update, context)
    
    elif data.startswith("settings_"):
        return await toggle_setting(update, context)
    
    elif data == "cancel_input":
        # İptal butonu
        if "waiting_for" in context.user_data:
            context.user_data.pop("waiting_for")
        
        # Önceki menüye geri dön
        if context.user_data.get("last_menu") == "track":
            return await show_track_menu(update, context)
        else:
            return await show_settings_menu(update, context)
    
    elif data == "back_to_main":
        return await show_main_menu(update, context)
    
    return MAIN_MENU

async def analyze_message(update: Update, context: CallbackContext):
    """Gelen mesajları analiz eder."""
    # Sadece grup mesajlarını analiz et
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    
    message_text = update.message.text
    if not message_text:
        return
    
    group_id = update.effective_chat.id
    group_name = update.effective_chat.title
    
    # Grubu veritabanına ekle (eğer yoksa)
    db.add_group(group_id, group_name)
    
    # Mesajı analiz et
    analyzer = TrendAnalyzer(db)
    analyzer.process_message(message_text, group_id)

async def schedule_handler(context: CallbackContext):
    """Zamanlanan görevleri çalıştırır."""
    now = datetime.datetime.now()
    
    # Günlük raporları kontrol et
        if now.hour == 0 and now.minute == 0:  # Gece yarısı
        # Otomatik raporlaması aktif olan grupları getir
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT g.group_id, g.group_name, ar.report_type FROM groups g "
            "INNER JOIN auto_reports ar ON g.group_id = ar.group_id "
            "WHERE ar.enabled = 1"
        )
        
        for group_id, group_name, report_type in cursor.fetchall():
            # Rapor türüne göre gönderme kararı
            if report_type == "daily":
                # Her gün gönder
                await generate_report(None, context, "daily", group_id)
            
            elif report_type == "weekly" and now.weekday() == 6:  # Pazar günü
                # Haftada bir gönder
                await generate_report(None, context, "weekly", group_id)
            
            elif report_type == "monthly" and now.day == 1:  # Ayın ilk günü
                # Ayda bir gönder
                await generate_report(None, context, "monthly", group_id)
        
        conn.close()

def run_schedule():
    """Arka planda zamanlayıcı çalıştırır."""
    while True:
        schedule.run_pending()
        time.sleep(60)

def main():
    """Botun ana fonksiyonu."""
    # Updater ve dispatcher oluştur
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    
    # Veritabanı bağlantısı
    global db
    db = Database(DB_NAME)
    
    # Konuşma işleyicisi
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", show_main_menu),
            CommandHandler("help", help_command),
            CommandHandler("report", lambda update, context: generate_report(update, context, "daily")),
            CommandHandler("weekly", lambda update, context: generate_report(update, context, "weekly")),
            CommandHandler("monthly", lambda update, context: generate_report(update, context, "monthly"))
        ],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(handle_buttons)
            ],
            REPORTS_MENU: [
                CallbackQueryHandler(handle_buttons)
            ],
            TRACK_MENU: [
                CallbackQueryHandler(handle_buttons),
                MessageHandler(Filters.text & ~Filters.command, handle_track_input)
            ],
            SETTINGS_MENU: [
                CallbackQueryHandler(handle_buttons),
                MessageHandler(Filters.text & ~Filters.command, handle_settings_input)
            ]
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("menu", show_main_menu),
            CommandHandler("help", help_command)
        ],
        name="trend_bot_conversation",
        persistent=False
    )
    
    dispatcher.add_handler(conv_handler)
    
    # Mesaj analiz işleyicisi
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, analyze_message))
    
    # Zamanlayıcı
    schedule.every().day.at("00:00").do(lambda: asyncio.run(schedule_handler(updater.dispatcher)))
    
    # Zamanlayıcıyı arka planda başlat
    scheduler_thread = threading.Thread(target=run_schedule)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Botu başlat
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
