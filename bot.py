import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # GPU kullanımını devre dışı bırak

import telebot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from opennsfw2 import predict_image
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
import requests
import tempfile
import logging
from datetime import datetime
import time
from collections import defaultdict
import threading

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s UTC - User: theburakct2 - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='nsfw_bot.log'
)
logger = logging.getLogger(__name__)

# Bot yapılandırması
TOKEN = '7209534643:AAEVFa1MeiZ-qKG2dj9eJ0skJKOjsNqnAhI'
NSFW_THRESHOLD = 0.89
VIDEO_FRAME_THRESHOLD = 0.80
FRAME_SKIP = 24

# Bot oluşturma
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

# Admin listesi
ADMIN_IDS = [7067213241]

# Kullanıcı medya takibi için global sözlük
user_media_tracker = defaultdict(list)
# Format: {user_id: [(message_id, timestamp, chat_id), ...]}

class AdminStates(StatesGroup):
    setting_threshold = State()

def is_admin(user_id):
    return user_id in ADMIN_IDS

def check_and_delete_user_media(user_id, chat_id):
    """Kullanıcının son mesajlarını kontrol et ve gerekirse toplu sil"""
    current_time = time.time()
    deletion_window = 30  # Son 30 saniye içindeki mesajları kontrol et
    
    # Kullanıcının son mesajlarını al
    user_messages = user_media_tracker[user_id]
    recent_messages = [
        msg for msg in user_messages 
        if current_time - msg[1] <= deletion_window and msg[2] == chat_id
    ]
    
    # Eğer kullanıcı kısa sürede çok fazla uygunsuz içerik gönderdiyse
    if len(recent_messages) >= 3:  # 30 saniye içinde 3 veya daha fazla uygunsuz içerik
        try:
            # Kullanıcının son 100 mesajını getir ve kontrol et
            messages = bot.get_chat_history(chat_id, limit=100)
            deleted_count = 0
            
            for message in messages:
                if message.from_user.id == user_id:
                    try:
                        bot.delete_message(chat_id, message.message_id)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Toplu mesaj silme hatası: {e}")
            
            # Kullanıcıyı uyar
            warning_text = (
                f"⚠️ @{message.from_user.username} çok sayıda uygunsuz içerik tespit edildi!\n"
                f"🚫 Son mesajları toplu olarak silindi.\n"
                f"📊 Silinen mesaj sayısı: {deleted_count}"
            )
            bot.send_message(chat_id, warning_text)
            
            # Kullanıcının takip listesini temizle
            user_media_tracker[user_id].clear()
            
            # Log kaydı
            current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            logger.warning(
                f"Toplu içerik silindi - "
                f"Tarih: {current_time} UTC - "
                f"Kullanıcı: {message.from_user.username} (ID: {user_id}), "
                f"Silinen Mesaj Sayısı: {deleted_count}, "
                f"Grup: {message.chat.title}"
            )
            
        except Exception as e:
            logger.error(f"Toplu silme işlemi hatası: {e}")

def process_image(image_data):
    """Görüntüyü işle ve NSFW skorunu hesapla"""
    try:
        image = Image.open(BytesIO(image_data)).convert('RGB')
        nsfw_score = predict_image(image)
        return float(nsfw_score)
    except Exception as e:
        logger.error(f"Görüntü işleme hatası: {e}")
        return 0.0

def process_sticker(sticker_file_id):
    """Çıkartmaları işle ve NSFW skorunu hesapla"""
    try:
        file_info = bot.get_file(sticker_file_id)
        file_path = file_info.file_path
        
        if file_path.endswith('.webm'):
            downloaded_file = bot.download_file(file_path)
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_file:
                temp_file.write(downloaded_file)
                temp_path = temp_file.name
            
            nsfw_score = predict_video(temp_path)
            os.unlink(temp_path)
            return float(nsfw_score)
        else:
            downloaded_file = bot.download_file(file_path)
            nparr = np.frombuffer(downloaded_file, np.uint8)
            img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img_np is None:
                logger.error("Çıkartma numpy array'e dönüştürülemedi")
                return 0.0
            
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(img_rgb)
            nsfw_score = predict_image(pil_image)
            return float(nsfw_score)
            
    except Exception as e:
        logger.error(f"Çıkartma işleme hatası: {e}")
        return 0.0

def predict_video(video_path):
    """Video dosyasını frame frame işle"""
    try:
        cap = cv2.VideoCapture(video_path)
        max_nsfw_score = 0.0
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            if frame_count % FRAME_SKIP != 0:
                continue
                
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)
            score = float(predict_image(frame_pil))
            max_nsfw_score = max(max_nsfw_score, score)
            
            if max_nsfw_score > VIDEO_FRAME_THRESHOLD:
                break
                
        cap.release()
        return max_nsfw_score
    except Exception as e:
        logger.error(f"Video işleme hatası: {e}")
        return 0.0

def delete_message_with_delay(chat_id, message_id):
    """Mesajı 2 dakika sonra sil"""
    try:
        time.sleep(120)  # 120 saniye = 2 dakika bekle
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.error(f"Mesaj silme hatası: {e}")

def delayed_delete(chat_id, message_id):
    """Mesaj silme işlemini ayrı bir thread'de başlat"""
    thread = threading.Thread(target=delete_message_with_delay, args=(chat_id, message_id))
    thread.start()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.type == 'private':
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        add_group = telebot.types.InlineKeyboardButton(
            "➕ Gruba Ekle", 
            url=f"https://t.me/{bot.get_me().username}?startgroup=true"
        )
        markup.add(add_group)
        
        bot.reply_to(
            message,
            "🤖 *NSFW Kontrol Botu*'na Hoş Geldiniz!\n\n"
            "Görevlerim:\n"
            "• Fotoğraf, video ve çıkartmaları kontrol ederim\n"
            "• Düzenlenen mesajları anında kontrol ederim\n"
            "• Uygunsuz içerikleri tespit eder ve silerim\n"
            "• Admin mesajları dahil tüm içerikleri kontrol ederim\n"
            "• 7/24 aktif çalışırım\n\n"
            "🛡 _Grubunuzun güvenliği için yönetici izinlerini vermeyi unutmayın_",
            parse_mode='Markdown',
            reply_markup=markup
        )

@bot.message_handler(commands=['status'])
def send_status(message):
    if is_admin(message.from_user.id):
        bot.reply_to(message, 
            f"Bot durumu:\n"
            f"NSFW Eşiği: {NSFW_THRESHOLD}\n"
            f"Video Kare Eşiği: {VIDEO_FRAME_THRESHOLD}\n"
            f"Kare Atlama: her {FRAME_SKIP} karede bir")

@bot.message_handler(commands=['set_threshold'])
def set_threshold(message):
    if is_admin(message.from_user.id):
        bot.reply_to(message, 
            "Yeni NSFW eşik değerini gönderin (0.0 - 1.0 arası):")
        bot.set_state(message.from_user.id, AdminStates.setting_threshold)

@bot.message_handler(state=AdminStates.setting_threshold)
def process_threshold(message):
    if is_admin(message.from_user.id):
        try:
            new_threshold = float(message.text)
            if 0 <= new_threshold <= 1:
                global NSFW_THRESHOLD
                NSFW_THRESHOLD = new_threshold
                bot.reply_to(message, f"NSFW eşiği {new_threshold} olarak ayarlandı.")
            else:
                bot.reply_to(message, "Lütfen 0 ile 1 arasında bir değer girin.")
        except ValueError:
            bot.reply_to(message, "Geçersiz değer. Lütfen bir sayı girin.")
        bot.delete_state(message.from_user.id)

def handle_media(message, media_type):
    """Medya dosyalarını işle ve kontrol et"""
    try:
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        if media_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            nsfw_score = process_image(downloaded_file)
        elif media_type == 'sticker':
            nsfw_score = process_sticker(message.sticker.file_id)
        elif media_type in ['video', 'animation']:
            file_info = bot.get_file(message.video.file_id if media_type == 'video' else message.animation.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_file.write(downloaded_file)
                temp_file_path = temp_file.name
            nsfw_score = predict_video(temp_file_path)
            os.unlink(temp_file_path)
        else:
            return

        if nsfw_score > NSFW_THRESHOLD:
            bot.delete_message(message.chat.id, message.message_id)
            
            # Kullanıcının medya geçmişine ekle
            user_media_tracker[message.from_user.id].append(
                (message.message_id, time.time(), message.chat.id)
            )
            
            # Kullanıcının son aktivitelerini kontrol et
            check_and_delete_user_media(message.from_user.id, message.chat.id)
            
            logger.info(
                f"NSFW içerik silindi - "
                f"Tarih: {current_time} UTC - "
                f"Skor: {nsfw_score:.2f}, "
                f"Tip: {media_type}, "
                f"Kullanıcı: {message.from_user.username}, "
                f"Grup: {message.chat.title}"
            )
            
            try:
                warning_msg = bot.send_message(
                    message.chat.id,
                    f"⚠️ @{message.from_user.username} uygunsuz içerik tespit edildi ve silindi."
                )
                delayed_delete(warning_msg.chat.id, warning_msg.message_id)
            except Exception as e:
                logger.error(f"Uyarı mesajı hatası: {e}")

            # Eski mesajları temizle (1 saat önceki kayıtları sil)
            current_time = time.time()
            user_media_tracker[message.from_user.id] = [
                msg for msg in user_media_tracker[message.from_user.id]
                if current_time - msg[1] <= 3600  # 1 saat
            ]

    except Exception as e:
        logger.error(f"Medya işleme hatası: {e} - Tarih: {current_time}")

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    handle_media(message, 'photo')

@bot.message_handler(content_types=['video'])
def handle_videos(message):
    handle_media(message, 'video')

@bot.message_handler(content_types=['animation'])
def handle_gifs(message):
    handle_media(message, 'animation')

@bot.message_handler(content_types=['sticker'])
def handle_stickers(message):
    handle_media(message, 'sticker')

@bot.edited_message_handler(content_types=['photo', 'video', 'animation', 'sticker'])
def handle_edited_media(message):
    """Düzenlenen medya mesajlarını kontrol et"""
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(
        f"Düzenlenen mesaj algılandı - "
        f"Tarih: {current_time} UTC - "
        f"Kullanıcı: {message.from_user.username}"
    )
    handle_media(message, message.content_type)
    # Önceki kodun devamı...

if __name__ == "__main__":
    def restart_program():
        """Botu yeniden başlatır"""
        print("Bot yeniden başlatılıyor...")
        time.sleep(3)
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def scheduled_restart():
        """Her 3 saatte bir botu yeniden başlatır"""
        while True:
            time.sleep(10800)  # 3 saat = 10800 saniye
            print(f"Zamanlanmış yeniden başlatma: {datetime.now()}")
            restart_program()

     # Yeniden başlatma thread'ini başlat
    restart_thread = threading.Thread(target=scheduled_restart)
    restart_thread.daemon = True
    restart_thread.start()

    # Ana bot döngüsü
    while True:
        try:
            print(f"Bot başlatıldı: {datetime.now()}")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Hata oluştu: {e}")
            time.sleep(10)
            continue
            
