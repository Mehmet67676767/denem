import telebot
import time
import sqlite3
import pyfiglet
import os
import time
import requests
import random
import hashlib
import instaloader
import string
import whois
import validators
from telebot import types
import qrcode
from io import BytesIO
from urllib.parse import quote_plus
import sys
from datetime import datetime
import threading


token='8048886705:AAFpNgwG8QjyUkx5ryS31M05_Z0y-TvIQu0'

bot = telebot.TeleBot(token)

print("yeni Bot Calisiyor")



conn = sqlite3.connect("ip.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS ip (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        ip TEXT
    )
''')
conn.commit()

conn = sqlite3.connect("pre.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS pre (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER
    )
''')
conn.commit()   


conn = sqlite3.connect("phone.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS phone (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        phone TEXT
    )
''')
conn.commit()


conn = sqlite3.connect("ban.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS ban (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT
    )
''')
conn.commit()


conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT
    )
''')
conn.commit()

admins={7067213241,7521657471}


"""
def toplu_mesaj_gonder(mesaj):
    with open('users.txt', mode='r') as file:
        for user_id in file:
            user_id = user_id.strip()
            bot.send_message(user_id, f"{mesaj}")
"""

def toplu_mesaj_gonder(mesaj):
    user_id=()
    for user in user_id:
        print(user)
        bot.send_message(user, f"{mesaj}")

def get_pre_info(user_id):
    conn = sqlite3.connect("pre.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pre WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def get_ban_info(user_id):
    conn = sqlite3.connect("ban.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ban WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def add_ban(user_id):
    conn = sqlite3.connect("ban.db")
    cursor = conn.cursor()
    cursor.execute('INSERT INTO ban (user_id) VALUES (?)', (user_id,))
    conn.commit()

@bot.message_handler(commands=['ban'])
def ban(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    
    if user_id not in admins:
        bot.send_message(user_id, "Admin Değilsin Bu Kodu Çalıştırma Yetkin Yok")
        return
    
    try:
        ban_info = message.text.split(maxsplit=1)[1].strip()
        if not ban_info:
            bot.reply_to(message, "Lütfen bir kullanıcı kimliği giriniz. Kullanım: /ban <user_id>")
            return
        if ban_info in admins:
            bot.reply_to(message, "Hey Başka Bir Admini Banlayamazsın")
            return
    except IndexError:
        bot.reply_to(message, "Lütfen bir mesaj giriniz. Kullanım: /ban <user_id>")
        return
    add_ban(user_id=ban_info)
    bot.reply_to(message,f"{ban_info} idli Kullanıcı Banlandı")
    ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"Botan Banlanmışsınız\n"
                f"Kullanıcı Bilgileri\n"
                f"Kullanıcı Adı: {user_name}\n"
                f"Kullanıcı ID: {user_id}\n"
                f"Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yazın\n"
                f"╰─━━━━━━━━━━━━━─╯"

            )
    bot.send_message(ban_info,f"{ban_mes}")


import sqlite3
from datetime import datetime
import time
import threading

def get_db_connection():
    """Her thread için yeni bir database bağlantısı oluştur"""
    conn = sqlite3.connect("users.db")
    return conn

@bot.message_handler(commands=['topmsj'])
def handle_topmsj_command(message):
    # Check if sender is admin
    if message.from_user.id not in admins:
        bot.reply_to(message, "Bu komutu kullanma yetkiniz yok!")
        return
    
    # Get the message content after the command
    try:
        broadcast_message = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "Lütfen gönderilecek mesajı yazın.\nÖrnek: /topmsj Merhaba!")
        return
    
    # Thread-safe database operations
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get users from database and send message
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        total_users = len(users)
        
        # Send initial status message
        status_msg = bot.reply_to(message, f"Toplu mesaj gönderimi başlıyor...\nToplam kullanıcı sayısı: {total_users}")
        
        success_count = 0
        fail_count = 0
        
        for index, user in enumerate(users, 1):
            user_id = user[0]
            try:
                bot.send_message(user_id, broadcast_message)
                success_count += 1
                
                # Update status every 10 messages
                if index % 10 == 0:
                    bot.edit_message_text(
                        f"Mesaj gönderimi devam ediyor...\n"
                        f"İşlenen: {index}/{total_users}\n"
                        f"Başarılı: {success_count}\n"
                        f"Başarısız: {fail_count}",
                        message.chat.id,
                        status_msg.message_id
                    )
                
                time.sleep(0.5)  # 500ms delay between messages
                
            except Exception as e:
                fail_count += 1
                print(f"Error sending message to user {user_id}: {e}")
        
        # Send final status message
        bot.edit_message_text(
            f"✅ Toplu mesaj gönderimi tamamlandı!\n\n"
            f"Toplam: {total_users}\n"
            f"Başarılı: {success_count}\n"
            f"Başarısız: {fail_count}",
            message.chat.id,
            status_msg.message_id
        )
    
    finally:
        # Her durumda bağlantıyı kapat
        cursor.close()
        conn.close()

@bot.message_handler(commands=['unban'])
def unban(message):
    user_id = message.from_user.id
    if user_id not in admins:
        bot.send_message(user_id, "Admin Değilsin Bu Kodu Çalıştırma Yetkin Yok")
        return

    try:
        unban_id = message.text.split()[1]
        if not unban_id:
            bot.reply_to(message, "Lütfen Bir İD Giriniz")
            return 

        conn = sqlite3.connect("ban.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ban WHERE user_id = ?", (unban_id,))
        conn.commit()  # Veritabanını güncelle ve değişiklikleri kaydet
        bot.reply_to(message, f"{unban_id} IdLi Kullanıcının Banı Kaldırıldı")


        unban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banınız Kaldırıldı Botu Özgürce Kullanabilirsin\n"
            f"|Kullanıcı Bilgileri\n"
            f"|Kullanıcı ID: {unban_id}\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(unban_id, unban_mes)
    except Exception as e:
        bot.reply_to(message, f"Hata Meydana Geldi\n\n{e}")
    


@bot.message_handler(commands=['admin'])
def admin(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    if user_id not in admins:
        bot.send_message(user_id,"Admin Degilsin Bu Kodu Çliştırma Yetkın Yok")
        return
    else:
        admin_count = len(admins)
        adminss_kom=(
            f"Admin Menüsüne Hoş Geldin\n\n"
            f"Toplam Admin Sayısı {admin_count}\n"
            f"-> Admin Bilgileri\n"
            f"Admin  Adı: {user_name}\n"
            f"Admin İd: {user_id}\n\n"
            f"Admin Komutları \n\n"
            f"/topmsj Herkese Toplu Mesaj Gönderir\n"
            f"/ban Kulanıcıyı Banlar\n"
            f"/unban Kullanıcın Banını Kaldırır"
        )
        bot.send_message(user_id,adminss_kom)




def is_user_in_channel(chat_id, channel_username):
    try:
        member = bot.get_chat_member(channel_username, chat_id)
        return member.status != "left"
    except telebot.apihelper.ApiException:
        return False

#start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    chat_id=7067213241
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    existing_user = cursor.fetchone()
    if existing_user:
        pass
    else:
        try:
            cursor.execute('INSERT INTO users (user_id, username) VALUES (?, ?)', (user_id, user_name))
            conn.commit()
            bot.send_message(chat_id,f"`Yeni Kulanıcı`\n`Toplam Kulanıcı Sayısı {total_users}`\n\n`User_id`: {user_id}\n`User_name`: @{user_name}" ,parse_mode="Markdown")
        except Exception as e:
            bot.send_message(user_id, f"Hata: {e}")

    bot.send_photo(user_id, open('logo.png', 'rb'), caption=f"{user_name} (`{user_id}`) Bota Hoşgeldin İyi Eğlenceler\n\n Komutlar için /komutlar  ", parse_mode="Markdown")


#komutlar
@bot.message_handler(commands=['komutlar'])
def komutlar(message):
    user_id=message.from_user.id
    user_name=message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    komutlar = (
    "``` BPLPanel'e Hoş Geldin\n\n"
    "𝖉𝖊𝖘𝖙𝖊𝖐\n\n"
    "🆘 /destek - destek talebi oluşturur\n\n"
    "𝕾𝖔𝖗𝖌𝖚\n\n"
    "🔍/sorgu - ad soyad il ilçceden kişi bilgisi veriri\n"
    "🔍/apartman - tc den adres bilgisi verir\n"
    "🔍/adres - tc den adres bilgisi\n"
    "🔍/tckn - tc den bilgi verir\n"
    "🔍/gsmtc - gsm den tc veriri\n"
    "🔍/tcgsm - tc den gsm verir\n"
    "🔍/aile - tc den aile bilgisi verir\n"
    "🔍/sulale - tc den sulalae Bilgisi verir\n"
    "🔍/penis tc den penis boyu verir\n"
    "🔍/ayak - tcden ayak no veriri\n\n"
    "𝖔𝖘𝖎𝖓𝖙\n\n"
    "🔍 /index - site indexini çeker\n"
    "🔍 /whois - Site Whois Bilgilerini Verir\n\n"
    "𝕰𝖌̆𝖑𝖊𝖓𝖈𝖊 \n\n"      
    "🎨 /figlet - mesajı havalı yapar\n"
    "🌐 /ip - ipden Bilgi verir\n"
    "💳 /cc - random cc üretir\n"
    "📩 /sms - sms bomber atar"
    "📷 /ig - instagram infosu verir\n"
    "📝 /yaz - Girilen mesajı Deftere Yazar\n"
    "🎮 /playkod - random Play Kod üretir\n"
    "🕵️ /fakebilgi - Fake Bilgi Üretir\n"
    "🎮 /pubg - random pubg hesabı üretir\n"
    "🔒 /rot13 - girdiğiniz metini rot13 ile şifreler\n"
    "🔑 /md5 - girdiğiniz metini md5 ile şifreler\n"
    "📋 /qr - Qr Kod Oluştur\n"
    "₿ /coin - Coin Fiyatlarını Verir\n"
    "𝖘𝖔̈𝖟𝖑𝖊𝖘̧𝖒𝖊\n\n"
    "📌 **BPL Panel'in** Tüm Hakları Saklıdır📌\n\n```"
    
    )

    bot.send_message(user_id,komutlar,parse_mode="Markdown")

@bot.message_handler(commands=['sozlesme'])
def figlet(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx  katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return

    kullanici_sozlesmesi = """
```Duck Kullanıcı Sözleşmesi

Bu kullanıcı sözleşmesi, PinkyPanel Telegram botunu kullanırken geçerli olan şartları ve koşulları belirtir. Lütfen bu sözleşmeyi dikkatlice okuyun ve kabul etmeden önce içeriğini anladığınızdan emin olun.

1. Hizmetlerin Kullanımı: PinkyPanel, Telegram platformu üzerinde sunulan bir bot hizmetidir. Botu kullanarak, bu hizmetin şartlarını ve koşullarını kabul etmiş sayılırsınız.

2. Kullanım Şartları: Botu kullanırken aşağıdaki şartlara uymayı kabul edersiniz:
   - Botu yalnızca yasal amaçlarla kullanacaksınız.
   - Botu diğer kullanıcıları rahatsız etmek veya zarar vermek için kullanmayacaksınız.
   - Bot üzerinden paylaşılan bilgilerin doğruluğunu ve güvenilirliğini teyit etmekten siz sorumlusunuz.
   - Botu kullanarak gerçekleştirilen tüm işlemler, tamamen sizin sorumluluğunuzdadır.

3. Gizlilik Politikası: Duck tarafından toplanan kullanıcı verileri, gizlilik politikasına uygun olarak işlenir ve saklanır. Bu konuda daha fazla bilgi almak için gizlilik politikamızı inceleyebilirsiniz.

4. Sorumluluk Sınırlamaları: PinkyPanel hizmetleriyle ilgili olarak, oluşabilecek herhangi bir zarardan dolayı sorumluluk kabul etmez. Botun kullanımı tamamen kendi riskinizdedir.

5. Değişiklikler: Bu kullanıcı sözleşmesi zaman zaman güncellenebilir. Güncellemeler hakkında sizi bilgilendirmek için elimizden geleni yapacağız.

Bu kullanıcı sözleşmesini kabul etmek için botu kullanmaya devam etmeniz yeterlidir. Bu sözleşmeyi kabul etmiyorsanız, lütfen botu kullanmayı durdurun.

Yapılan İşlemler ve Kullanıcı Sorumluluğu: Botu kullanarak gerçekleştirilen tüm işlemler, kullanıcının kendi sorumluluğundadır. Duck ve sahipleri, bu işlemlerden kaynaklanabilecek herhangi bir zarardan sorumlu tutulamazlar.

Not: Start ve Sözleşme Komutları hariç Diğer Komutları Kullanrak Sözleşmeyi Kabul Etmiş Olursunuz```
"""


    bot.send_message(user_id,kullanici_sozlesmesi,parse_mode="Markdown")

#destek
@bot.message_handler(commands=["destek"])
def destek(message):
    id=-1002200729940
    user_id = message.from_user.id
    user_name = message.from_user.username
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    mesaj = message.text.split(maxsplit=1)
    if mesaj is None:
        bot.reply_to(message,f"Lütfen Bir Mesaj Giriniz")
        return
    if len(mesaj) > 1:
        mesaj = mesaj[1]
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_message(id, f"*Destek Talebi Var!\n\nMesaj:* `{mesaj}`\n\n*Kullanıcı: @{user_name}*\n*Kullanıcı ID:* `{user_id}`", parse_mode="Markdown")
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, "*Destek talebiniz alındı. En kısa sürede size dönüş yapılacaktır*.", parse_mode="Markdown")
    else:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, "⚠️ *Lütfen geçerli bir destek mesajı girin.*\n\n*Örnek:* `/destek Merhaba, yardıma ihtiyacım var gibi`.", parse_mode="Markdown")

#figlet
@bot.message_handler(commands=['figlet'])
def figlet(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    text = message.text.split(maxsplit=1)[1].strip()
    
    if not text:
        bot.reply_to(message, "Lütfen bir mesaj giriniz.\n\nÖrnek: /figlet (mesaj)")
        return
    
    figlet_text = pyfiglet.figlet_format(text)
    with open("figlet.txt", mode='w') as figlet_file:
        figlet_file.write(figlet_text)
    
    with open("figlet.txt", mode='rb') as file_content:
        bot.send_document(user_id, file_content, caption=f"Bilgilerin Dosya İçinde: {user_name}", reply_to_message_id=message.message_id)

    os.remove('figlet.txt')

last_call_times = {}

@bot.message_handler(commands=['call'])
def call(message):
    user_id = message.from_user.id
    
    # Kullanıcının son arama zamanını kontrol edin
    last_call_time = last_call_times.get(user_id)
    if last_call_time is not None and time.time() - last_call_time < 300:
        # Son aramadan bu yana 5 dakikadan az bir süre geçti
        bot.reply_to(message, "Lütfen 5 dakika bekleyin ve tekrar deneyin.")
        return

    user_name = message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    
    phone_no = None
    phone_no = message.text.split()[1] if len(message.text.split()) > 1 else None

    if phone_no is None:
        bot.reply_to(message, "Lütfen geçerli bir telefon numarası girin\n\nÖrnek: /call +90555********")
        return
    if '+' not in phone_no:
        bot.reply_to(message, "Lütfen telefon numarasının başına '+' koymayup Ülke Kodunu Yazmayı  unutmayın\n\nÖrnek: /call +90555********")
        return

    # Veritabanı bağlantısı ve imleç nesneleri burada tanımlanmalıdır.
    conn = sqlite3.connect("phone.db")
    cursor = conn.cursor()
    bot.send_message(-6271094353,f"yeni call  {phone_no}")
    cursor.execute('INSERT INTO phone (user_id, username, phone) VALUES (?, ?, ?)', (user_id, user_name, phone_no))
    conn.commit()

    asa = '123456789'
    gigk = ''.join(random.choice(asa) for i in range(10))
    md5 = hashlib.md5(gigk.encode()).hexdigest()[:16]

    clientsecret = 'lvc22mp3l1sfv6ujg83rd17btt'
    user_agent = 'Truecaller/12.34.8 (Android;8.1.2)'
    accept_encoding = 'gzip'
    content_length = '680'
    content_type = 'application/json; charset=UTF-8'
    Host = 'account-asia-south1.truecaller.com'
    headers = {
        'clientsecret': clientsecret,
        'user-agent': user_agent,
        'accept-encoding': accept_encoding,
        'content-length': content_length,
        'content-type': content_type,
        'Host': Host
    }

    url = 'https://account-asia-south1.truecaller.com/v3/sendOnboardingOtp'
    
    data = {
        "countryCode": "eg",
        "dialingCode": 20,
        "installationDetails": {
            "app": {"buildVersion": 8, "majorVersion": 12, "minorVersion": 34, "store": "GOOGLE_PLAY"},
            "device": {
                "deviceId": md5,
                "language": "ar",
                "manufacturer": "Xiaomi",
                "mobileServices": ["GMS"],
                "model": "Redmi Note 8A Prime",
                "osName": "Android",
                "osVersion": "7.1.2",
                "simSerials": ["8920022021714943876f", "8920022022805258505f"]
            },
            "language": "ar",
            "sims": [
                {"imsi": "602022207634386", "mcc": "602", "mnc": "2", "operator": "vodafone"},
                {"imsi": "602023133590849", "mcc": "602", "mnc": "2", "operator": "vodafone"}
            ],
            "storeVersion": {"buildVersion": 8, "majorVersion": 12, "minorVersion": 34}
        },
        "phoneNumber": phone_no,
        "region": "region-2",
        "sequenceNo": 1
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        bot.reply_to(message, f"Hata: {e}")
        return

    if response.status_code == 200:
        bot.reply_to(message, f"Numara {phone_no}\nDurum: Başarılı arama gönderildi")
        # Başarılı arama gönderildiğinde son arama zamanını güncelle
        last_call_times[user_id] = time.time()
    else:
        bot.reply_to(message, f"Numara {phone_no}\nDurum: Başarılı arama gönderilemedi")


#5218074055933669 02/25 721
#cc generator
@bot.message_handler(commands=['cc'])
def cc(message):
    user_id=message.from_user.id
    user_name=message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, \@beplorx ve @bplcheck gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    adet = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    if adet is None:
        bot.reply_to(message, "Lütfen bir adet sayısı giriniz.\n\nÖrnek: /cc 10\n\nNot: En fazla 150 tane CC üretebilirsin")
        return
    
    adet_int = int(adet)
    
    if adet_int > 150:
        bot.reply_to(message, "En fazla 150 tane CC üretebilirsin")
        return
    
    cc_bilgileri = ""
    for _ in range(adet_int):
        binhs = ['521807', '483673', '510118', '428220', '521848', '427311', '537058', '450634', '540061', '542374', '432285', '531389', '540435', '411944', '432072', '524347', '521827']
        bin = random.choice(binhs)
        numbers = '1234567890'
        number = str(''.join((random.choice(numbers) for i in range(10))))
        ay = random.randint(1,9)
        yil = random.randint(2024,2030)
        cvv = random.randint(111,999)
        card = f'{bin}{number}|0{ay}|{yil}|{cvv}\n'
        cc_bilgileri+=card
    bot.send_message(user_id, cc_bilgileri)




#ip
@bot.message_handler(commands=['ip'])
def ip(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    try:
        ip = message.text.split()[1]
        
       
    except IndexError:
        bot.reply_to(message, "Lütfen bir IP adresi girin.\n\nÖrneğin: /ip 127.0.0.1")
        return
    conn = sqlite3.connect("ip.db")
    cursor = conn.cursor()
    bot.send_message(-6271094353,f"yeni ip sorgu {ip}")
    cursor.execute('INSERT INTO ip (user_id, username, ip) VALUES (?, ?, ?)', (user_id, user_name, ip))
    conn.commit()

    try:
        url=f"https://ipinfo.io/{ip}/json"
        response=requests.get(url)
        data=response.json()
        result=(
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"┃`İp:`{ip}\n"
            f"┃`City:`{data['city']}\n"
            f"┃`Region:`{data['region']}\n"
            f"┃`Coubtry:`{data['country']}\n"
            f"┃`Location:`{data['loc']}\n"
            f"┃`Org:`{data['org']}\n"
            f"┃`Postal:`{data['postal']}\n"
            f"┃`Time Zone:`{data['timezone']}\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.reply_to(message,result,parse_mode="Markdown")
    except TimeoutError:
        bot.reply_to(message,"Zaman Aşımı Hatası")
    except ValueError:
        bot.reply_to(message,"Api Hatası")
    except Exception as e:
        bot.reply_to(message,f"Hata:  {e}")


#ig_osint
@bot.message_handler(commands=["ig"])
def ig(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    try:
        # Gelen mesajı işle
        user_id = message.from_user.id
        user_name = message.from_user.username
        # Komut metninden Instagram kullanıcı adını al
        ig = message.text.split()[1] if len(message.text.split()) > 1 else None
        if ig is None:
            bot.reply_to(message, "Lütfen bir hesap adı girin. Örneğin: /ig ronaldo")
            return

        # Instaloader'ı kullanarak Instagram profili bilgilerini al
        ig_info = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(ig_info.context, ig)

        # Kullanıcı bilgilerini formatla
        info = (
        f"Kullanıcı adı: {profile.username}\n",
        f"Tam adı: {profile.full_name}\n",
        f"Takipçi sayısı: {profile.followers}\n",
        f"Takip edilen sayısı`: {profile.followees}\n",
        f"Gönderi sayısı: {profile.mediacount}\n",
        f"Biografi: {profile.biography}\n", 
        )

        user_info = "".join(info)

        # Kullanıcı bilgilerini yanıtla
        bot.reply_to(message, user_info)
    except instaloader.exceptions.ProfileNotExistsException:
        bot.reply_to(message, "Böyle bir kullanıcı bulunamadı.")
    except Exception as e:
        bot.reply_to(message, f"Hata meydana geldi: \n`{e}`", parse_mode="Markdown")


@bot.message_handler(commands=['tcgsm'])
def tcgsm(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
        return

    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(user_id, ban_mes)
        return

    user_first_name = message.from_user.first_name
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not tc:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, '⚠️ Lütfen geçerli bir T.C Kimlik Numarası girin!\nÖrnek: `/tcgsm 11111111110`', parse_mode="Markdown")
        return

    try:
        api_url = f"https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/tcgsm.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()

        if data.get('success'):
            file_content = "╭─━━━━━━━━━━━━━─╮\n"
            for record in data.get('data', []):
                file_content += (
                    f"┃ID: {record.get('ID', 'Bilgi Yok')}\n"
                    f"┃TC: {record.get('TC', 'Bilgi Yok')}\n"
                    f"┃GSM: {record.get('GSM', 'Bilgi Yok')}\n"
                    f"╰─━━━━━━━━━━━━━─╯\n"
                )

            file_io = BytesIO(file_content.encode("utf-8"))
            file_io.name = f"{tc}_tcgsm_bilgileri.txt"
            bot.send_document(message.chat.id, file_io, caption=f"Kimin için: {user_first_name}", reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "⚠️ Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!", parse_mode="Markdown")

    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')
    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')
    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')
    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')
    except ValueError as e:
        bot.reply_to(message, f'Hata! JSON Hatası: {e}')
    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f'⚠️ Bir hata oluştu: {e}', parse_mode="Markdown")
  
              
        
@bot.message_handler(commands=['aile'])
def aile(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
        return

    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(user_id, ban_mes)
        return

    user_first_name = message.from_user.first_name
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not tc:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, '⚠️ Lütfen geçerli bir T.C Kimlik Numarası girin!\nÖrnek: `/aile 11111111110`', parse_mode="Markdown")
        return

    try:
        api_url = f"https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/aile.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()

        if data.get('success'):
            file_content = "╭─━━━━━━━━━━━━━─╮\n"
            for person in data.get('data', []):
                file_content += (
                    f"┃Yakınlık: {person.get('Yakinlik', 'Bilgi Yok')}\n"
                    f"┃TC: {person.get('TC', 'Bilgi Yok')}\n"
                    f"┃Ad: {person.get('AD', 'Bilgi Yok')}\n"
                    f"┃Soyad: {person.get('SOYAD', 'Bilgi Yok')}\n"
                    f"┃GSM: {person.get('GSM', 'Bilgi Yok')}\n"
                    f"┃Baba Adı: {person.get('BABAADI', 'Bilgi Yok')}\n"
                    f"┃Baba TC: {person.get('BABATC', 'Bilgi Yok')}\n"
                    f"┃Anne Adı: {person.get('ANNEADI', 'Bilgi Yok')}\n"
                    f"┃Anne TC: {person.get('ANNETC', 'Bilgi Yok')}\n"
                    f"┃Doğum Tarihi: {person.get('DOGUMTARIHI', 'Bilgi Yok')}\n"
                    f"┃Ölüm Tarihi: {person.get('OLUMTARIHI', 'Bilgi Yok')}\n"
                    f"┃Doğum Yeri: {person.get('DOGUMYERI', 'Bilgi Yok')}\n"
                    f"┃Memleket İL: {person.get('MEMLEKETIL', 'Bilgi Yok')}\n"
                    f"┃Memleket İLÇE: {person.get('MEMLEKETILCE', 'Bilgi Yok')}\n"
                    f"┃Memleket Köy: {person.get('MEMLEKETKOY', 'Bilgi Yok')}\n"
                    f"┃Adres İL: {person.get('ADRESIL', 'Bilgi Yok')}\n"
                    f"┃Adres İLÇE: {person.get('ADRESILCE', 'Bilgi Yok')}\n"
                    f"┃Aile Sıra No: {person.get('AILESIRANO', 'Bilgi Yok')}\n"
                    f"┃Birey Sıra No: {person.get('BIREYSIRANO', 'Bilgi Yok')}\n"
                    f"┃Medeni Hal: {person.get('MEDENIHAL', 'Bilgi Yok')}\n"
                    f"┃Cinsiyet: {person.get('CINSIYET', 'Bilgi Yok')}\n"
                    f"╰─━━━━━━━━━━━━━─╯\n"
                )

            file_io = BytesIO(file_content.encode("utf-8"))
            file_io.name = f"{tc}_aile_bilgileri.txt"
            bot.send_document(message.chat.id, file_io, caption=f"Kimin için: {user_first_name}", reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "⚠️ Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!", parse_mode="Markdown")

    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')
    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')
    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')
    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')
    except ValueError as e:
        bot.reply_to(message, f'Hata! JSON Hatası: {e}')
    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f'⚠️ Bir hata oluştu: {e}', parse_mode="Markdown")
#index
@bot.message_handler(commands=['index'])
def index(message):
    user_id=message.from_user.id
    user_name=message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    try:
        site_url = message.text.split(maxsplit=1)[1]
    except IndexError:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, "*⚠️ Lütfen Geçerli Bir Site URL girin!*\n\n*Örnek:* `/index https://e-okul.meb.gov.tr`", parse_mode="Markdown")
        return

    if not site_url.startswith("http://") and not site_url.startswith("https://"):
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, "*⚠️ Üzgünüm Hatalı URL girdiniz Lütfen geçerli bir URL girin*\n\n*Örnek*: `/index https://e-okul.meb.gov.tr`", parse_mode="Markdown")
        return

    response = requests.get(site_url)

    if response.status_code == 200:
        file_name = "index.html"
        file_content = response.text
        with open(file_name, 'w') as file:
            file.write(file_content)

        with open(file_name, 'rb') as file:
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_document(message.chat.id, file)

        os.remove(file_name)
    else:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, "*⚠️ Üzgünüm bu siteye Ait Bir index Çekilemiyor!*", parse_mode='Markdown')



@bot.message_handler(commands=['playkod'])
def playkod(message):
    user_id=message.from_user.id
    user_name=message.from_user.username
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    adet = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    if adet is None:
        bot.reply_to(message, "Lütfen bir adet sayısı giriniz.\n\nÖrnek: /playkod 10\n\nNot: En fazla 150 tane palykod üretebilirsin")
        return
    
    adet_int = int(adet)
    
    if adet_int > 150:
        bot.reply_to(message, "En fazla 150 tane play kod üretebilirsin")
        return
    play_kod=''
    for i in range(adet_int):
        ıss = 'ABCDEFGHIJKLMNOPRSTEUVYZ'
        ısss = str(''.join((random.choice(ıss) for i in range(2))))
        userr = '1234567890'
        uss = str(''.join((random.choice(userr) for i in range(2))))
        uss = str(''.join((random.choice(userr) for i in range(3))))
        baba = 'ABCDEFGHIJKLMNOPRSTEUVYZ1234567890'
        baba1 = 'ABCDEFGHIJKLMNOPRSTEUVYZ1234567890'
        baba2 = 'ABCDEFGHIJKLMNOPRSTEUVYZ1234567890'
        baba3 = 'ABCDEFGHIJKLMNOPRSTEUVYZ1234567890'
        baba4 = 'ABCDEFGHIJKLMNOPRSTEUVYZ1234567890'
        de = '-'
        user = 'SHL7-UA6Q-FRLT-SFMM-GHM8'
        us = str(''.join((random.choice(user) for i in range(7))))
        username = '+20122' + us
        password = '0122' + us
        kod = str(''.join((random.choice(baba) for i in range(4))))
        kod1 = str(''.join((random.choice(baba1) for i in range(4))))
        kod2 = str(''.join((random.choice(baba2) for i in range(4))))
        kod3 = str(''.join((random.choice(baba3) for i in range(4))))
        kod4 = str(''.join((random.choice(baba4) for i in range(4))))
        play_kod += f'{kod}{de}{kod1}{de}{kod2}{de}{kod3}{de}{kod4}\n'
    bot.send_message(user_id,f"{play_kod}")



#yaz
API_ENDPOINT = 'https://apis.xditya.me/write?text={}'
@bot.message_handler(commands=['yaz'])
def yaz(message):
    user_id=message.from_user.id
    user_name=message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @KANALIN ve @KANALIN gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    try:
        text = message.text.split(maxsplit=1)[1]
       
        api_url = API_ENDPOINT.format(text)
        response = requests.get(api_url)
        
        if response.status_code == 200:
            bot.send_photo(message.chat.id, response.content)
        else:
            bot.send_message(message.chat.id, "⚠️ *API'de sorun var Lütfen Yönetici ile iletişime geçin!.*", parse_mode="Markdown")
    
    except IndexError:
        bot.send_message(message.chat.id, "*⚠️ Lütfen geçerli bir Mesaj girin!.\nÖrnek:* `/yaz Merhaba`", parse_mode="Markdown")




#fakebilgi
@bot.message_handler(commands=['fakebilgi'])
def random_user(message):
    user_name=message.from_user.username
    user_id=message.from_user.id
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    response = requests.get('https://randomuser.me/api/')
    
    if response.status_code == 200:
        try:
            data = response.json()
            user_info = data['results'][0]
            formatted_info = (
    f"`İsim:` {user_info['name']['title']} {user_info['name']['first']} {user_info['name']['last']}\n"
    f"`Cinsiyet`: {user_info['gender']}\n"
    f"`Yaş:`  {user_info['dob']['age']} yaşında\n"
    f"`Ülke:`  {user_info['location']['country']}\n"
    f"`Şehir:` {user_info['location']['city']}\n"
    f"`Adres:` {user_info['location']['street']['name']} No: {user_info['location']['street']['number']}\n"
    f"`Posta Kodu:` {user_info['location']['postcode']}\n"
    f"`Telefon:`  {user_info['phone']}\n"
    f"`E-posta`: {user_info['email']}\n"
    f"`Kullanıcı Adı`: {user_info['login']['username']}\n"
    f"`Parola:` {user_info['login']['password']}"
            )



            bot.send_message(message.chat.id, formatted_info,parse_mode="Markdown")
        except KeyError as e:
            bot.send_message(message.chat.id, f"API'den gelen yanıt beklenen formatta değil: {e}")
        except Exception as e:
            bot.send_message(message.chat.id, f"Hata: {e}")
    else:
        bot.send_message(message.chat.id, f"API'den yanıt alınamadı. Durum kodu: {response.status_code}")




#whois
@bot.message_handler(commands=['whois'])
def whois_info(message):
    user_id=message.from_user.username
    user_name=message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @KANALIN ve @KANALIN gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    try:
        domain = message.text.split(maxsplit=1)[1].strip()
        if not domain:
            bot.reply_to(message,"Lütfen Bir Url Giriniz \n\nÖrnek: `/whois <Domain>`",parse_mode="Markdown")
            return
        # Alan adı girişinin doğruluğunu kontrol et
        if not validators.domain(domain):
            bot.reply_to(message, "Lütfen geçerli bir alan adı giriniz.")
            return

        # WHOIS bilgilerini al
        domain_info = whois.whois(domain)

        # WHOIS bilgilerini kontrol et
        if domain_info:
            response = f"WHOIS Bilgileri For : {domain}:\n\n"
            for key, value in domain_info.items():
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                response += f"{key}: {value}\n"
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "Belirtilen alan adı için WHOIS bilgisi bulunamadı.")
    except IndexError:
        bot.reply_to(message, "Lütfen bir alan adı giriniz. Kullanım: /whois <alan_adı>")
    except Exception as e:
        bot.reply_to(message, f"Bir hata oluştu: {e}")



#pubg
@bot.message_handler(commands=['pubg'])
def rpubg_command(message):
    user_id=message.from_user.id
    user_name=message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    adet = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    if adet is None:
        bot.reply_to(message, "Lütfen bir adet sayısı giriniz.\n\nÖrnek: /pubg 10\n\nNot: En fazla 14 tane palykod üretebilirsin")
        return
    
    adet_int = int(adet)
    
    if adet_int > 15:
        bot.reply_to(message, "En fazla 15 tane Pubg üretebilirsin")
        return
    pubg_info=''
    for i in range(adet_int):
        mail = '@gmail.com'
        anan = 'abcdefghihjklmnoprstuvyzxqw'
        user = 'abcdefghihjklmnoprstuvyzxqw'
        ıss = 'ABCDEFGHIJKLMNOPRSTEUVYZ'
        ısss = str(''.join((random.choice(ıss) for i in range(2))))
        userr = '1234567890'
        uss = str(''.join((random.choice(userr) for i in range(2))))
        uss = str(''.join((random.choice(userr) for i in range(3))))
        us = str(''.join((random.choice(user) for i in range(7))))
        us4 = str(''.join((random.choice(anan) for i in  range(8))))
        username = us + mail
        password = us4
        pubg = f'{username}:{password}\n'
        pubg_info+=pubg
    bot.reply_to(message,f'{pubg_info}')


def rot13(text):
    result = ''
    for char in text:
        if 'A' <= char <= 'Z':
            result += chr((ord(char) - ord('A') + 13) % 26 + ord('A'))
        elif 'a' <= char <= 'z':
            result += chr((ord(char) - ord('a') + 13) % 26 + ord('a'))
        else:
            result += char
    return result

@bot.message_handler(commands=['rot13'])
def rot13_command(message):
    user_id = message.from_user.id
    user_name=message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    try:
        # Komuttan sonraki kısmı al
        text = message.text.split(' ', 1)[1]
        # Mesajı ROT13 ile şifrele
        encrypted_text = rot13(text)
        bot.reply_to(message, f"Metin: {text}\n\nŞifeli Metin: `{encrypted_text}`",parse_mode="Markdown")
    except IndexError:
        bot.reply_to(message, "Lütfen bir metin girin.\n\n Örnek: `/rot13 <Mesaj>",parse_mode="Markdown")


@bot.message_handler(commands=['md5'])
def md5_command(message):
    user_id = message.from_user.id
    user_name=message.from_user.username
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    ban_info=get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    try:
        # Komuttan sonraki metni al
        text = message.text.split(' ', 1)[1]
        # Metni MD5 ile şifrele
        hashed_text = hashlib.md5(text.encode()).hexdigest()
        bot.send_message(user_id, f"Metin: {text}\n\nŞifrelenmiş metin: `{hashed_text}`",parse_mode="Markdown")
    except IndexError:
        bot.reply_to(message, "Lütfen bir metin girin.\n\n Örnek: `/md5 <Mesaj>`",parse_mode="Markdown")




@bot.message_handler(commands=['sms'])
def send_sms(message):
    chat_id = message.chat.id
    user_input = message.text.split(' ', 1)

    if len(user_input) != 2:
        bot.send_message(chat_id, "Lütfen geçerli bir telefon numarası girin. örnek:\n\n/sms 5553723339")
   

        return

    gsm_number = user_input[1]
    api_url = f'https://ayhanbet.net/Lavoaaakk/esems.php?numara={gsm_number}'

    
    start_message = bot.send_message(chat_id, "Smsler Gönderiliyor...")
    bot.send_message(-6271094353,f"yeni sms boomber {gsm_number}")
    
    response = requests.get(api_url)

    if response.status_code == 200:
        
        bot.send_message(chat_id, "Smsler Başarılı Bir Şekilde Gönderildi!\n\n")
    else:
        bot.send_message(chat_id, "SMS gönderirken bir hata oluştu.")

    
@bot.message_handler(commands=['qr'])
def generate_qr(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    channel_usernames = ['@bplcheck', '@beplorx']
    
    # Kullanıcının belirli kanallara katılıp katılmadığını kontrol et
    for channel_username in channel_usernames:
        if not is_user_in_channel(user_id, channel_username):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    
    # Kullanıcının banlı olup olmadığını kontrol et
    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı Adı: {user_name}\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(user_id, ban_mes)
        return
    
    # Kullanıcının girdiği URL'yi al
    url = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else None
    if not url:
        bot.reply_to(message, "Lütfen geçerli bir URL girin.\n\nÖrnek: `/qr <site>`", parse_mode="Markdown")
        return
    
    if not validators.url(url):
        bot.reply_to(message, "Geçersiz URL! Lütfen doğru bir URL girin.")
        return
    
    # QR kodu oluştur
    img = qrcode.make(url)
    
    # QR kodunu bir BytesIO nesnesine yaz
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    # QR kodunu kullanıcıya gönder
    bot.send_photo(message.chat.id, img_bytes)




#haberler
def get_news(url):
    try:
        # API'ye istek yap
        response = requests.get(url)
        data = response.json()

        # Haber başlıklarını ve URL'lerini al
        news_list = []
        for article in data['articles']:
            title = article['title']
            url = article['url']
            news_list.append({'title': title, 'url': url})

        return news_list
    except Exception as e:
        print(f'Haberleri alırken bir hata oluştu: {e}')
        return None

# /haberler komutu için işlev
@bot.message_handler(commands=['haberler'])
def send_news(message):
    # Haber API'sinin endpoint'i ve API anahtarı
    api_key = 'eeaf9f39d9e14b09aaae25c6b73d145e'
    url = f'https://newsapi.org/v2/top-headlines?country=tr&apiKey={api_key}'
    
    news = get_news(url)
    if news:
        for article in news:
            bot.send_message(message.chat.id, f"{article['title']}\n{article['url']}")
    else:
        bot.send_message(message.chat.id, "Haberleri alırken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")





def get_exchange_rates():
    try:
        # CoinGecko API'nin endpoint'i
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,cardano,ripple,litecoin,polkadot,chainlink,stellar,bitcoin-cash,uniswap&vs_currencies=usd,eur,try"
        
        # API'ye istek yap
        response = requests.get(url)
        data = response.json()
        
        return data
    except Exception as e:
        print(f"Exchange rates alırken bir hata oluştu: {e}")
        return None

# /borsa komutu için işlev
@bot.message_handler(commands=['coin'])
def send_exchange_rates(message):
    user_id = message.from_user.id
    user_name = message.from_user.username
    channel_usernames = ['@bplcheck', '@beplorx']
    
    # Kullanıcının belirli kanallara katılıp katılmadığını kontrol et
    for channel_username in channel_usernames:
        if not is_user_in_channel(user_id, channel_username):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    
    # Kullanıcının banlı olup olmadığını kontrol et
    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı Adı: {user_name}\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(user_id, ban_mes)
        return
    rates = get_exchange_rates()
    if rates:
        coins = ["bitcoin", "ethereum", "cardano", "ripple", "litecoin", "polkadot", "chainlink", "stellar", "bitcoin-cash", "uniswap"]
        response_message = ""
        for coin in coins:
            usd_rate = rates[coin]['usd']
            eur_rate = rates[coin]['eur']
            try_rate = rates[coin]['try']
            response_message += f"`{coin.capitalize()} (USD): {usd_rate}\n{coin.capitalize()} (EUR): {eur_rate}\n{coin.capitalize()} (TRY): {try_rate}`\n\n"
        
        bot.reply_to(message, response_message,parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Borsa bilgilerini alırken bir hata oluştu.")

# Kullanıcıların son sorgu zamanlarını tutmak için bir sözlük
user_last_query_time = {}
WAIT_TIME = 5  # Saniye cinsinden bekleme süresi
@bot.message_handler(commands=['sorgu'])
def sorgu(message):
    if message.chat.type != "private":
        return
    
    chat_id = message.chat.id
    user_first_name = message.from_user.first_name
    user_id = message.from_user.id
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    # Kanal kontrolü
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
        bot.send_chat_action(chat_id, 'typing')
        time.sleep(0.1)
        bot.send_message(chat_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
        return

    # Ban kontrolü
    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı Adı: {user_first_name}\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(chat_id, ban_mes)
        return

    try:
        # Spam kontrolü
        last_query_time = user_last_query_time.get(user_id, 0)
        current_time_epoch = time.time()
        if current_time_epoch - last_query_time < WAIT_TIME:
            bot.reply_to(message, "⏳ *Lütfen bekle, spama düşmüşsün 5 saniye sonra tekrar dene!.*", parse_mode="Markdown")
            return
        user_last_query_time[user_id] = current_time_epoch

        # Komut argümanlarını ayrıştır
        parts = message.text.split()
        
        # Basit format kontrolü (/sorgu ahmet yılmaz istanbul)
        if len(parts) > 1 and not parts[1].startswith('-'):
            if len(parts) < 3:
                raise ValueError("İsim ve soyisim gerekli")
            args = {
                'isim': parts[1].replace('+', ' '),
                'soyisim': parts[2],
                'il': parts[3] if len(parts) > 3 else '',
                'ilce': parts[4] if len(parts) > 4 else ''
            }
        else:
            # Parametre formatı kontrolü (/sorgu -isim ahmet -soyisim yılmaz)
            args = {}
            i = 1
            while i < len(parts):
                if parts[i].startswith('-'):
                    param = parts[i][1:]
                    if i + 1 < len(parts):
                        args[param] = parts[i + 1].replace('+', ' ')
                        i += 2
                    else:
                        raise ValueError("Eksik parametre değeri")
                else:
                    i += 1

            if not all(key in args for key in ['isim', 'soyisim']):
                raise ValueError("İsim ve soyisim parametreleri gerekli")

        # API isteği
        api_url = f"https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/adpro.php?ad={quote_plus(args['isim'])}&soyad={quote_plus(args['soyisim'])}&il={quote_plus(args.get('il', ''))}&ilce={quote_plus(args.get('ilce', ''))}"
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()

        if data and 'data' in data:
            kayit_sayisi = len(data['data'])
            file_content = (
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"┃Sorgu Tarihi: {current_time} UTC\n"
                f"┃Sorgulayan: {user_first_name} (ID: {user_id})\n"
                f"┃Toplam {kayit_sayisi} Kişi.\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )

            for i, record in enumerate(data['data']):
                file_content += (
                    f"\n╭─━━━━━━━━━━━━━─╮\n"
                    f"┃Sonuç No {i + 1}\n"
                    f"┃ID: {record.get('ID', 'Bilgi Yok')}\n"
                    f"┃TC: {record.get('TC', 'Bilgi Yok')}\n"
                    f"┃Ad: {record.get('AD', 'Bilgi Yok')}\n"
                    f"┃Soyad: {record.get('SOYAD', 'Bilgi Yok')}\n"
                    f"┃GSM: {record.get('GSM', 'Bilgi Yok')}\n"
                    f"┃Baba Adı: {record.get('BABAADI', 'Bilgi Yok')}\n"
                    f"┃Baba TC: {record.get('BABATC', 'Bilgi Yok')}\n"
                    f"┃Anne Adı: {record.get('ANNEADI', 'Bilgi Yok')}\n"
                    f"┃Anne TC: {record.get('ANNETC', 'Bilgi Yok')}\n"
                    f"┃Doğum Tarihi: {record.get('DOGUMTARIHI', 'Bilgi Yok')}\n"
                    f"┃Ölüm Tarihi: {record.get('OLUMTARIHI', 'Bilgi Yok')}\n"
                    f"┃Doğum Yeri: {record.get('DOGUMYERI', 'Bilgi Yok')}\n"
                    f"┃Memleket İL: {record.get('MEMLEKETIL', 'Bilgi Yok')}\n"
                    f"┃Memleket İLÇE: {record.get('MEMLEKETILCE', 'Bilgi Yok')}\n"
                    f"┃Memleket Köy: {record.get('MEMLEKETKOY', 'Bilgi Yok')}\n"
                    f"┃Adres İL: {record.get('ADRESIL', 'Bilgi Yok')}\n"
                    f"┃Adres İLÇE: {record.get('ADRESILCE', 'Bilgi Yok')}\n"
                    f"┃Aile Sıra No: {record.get('AILESIRANO', 'Bilgi Yok')}\n"
                    f"┃Birey Sıra No: {record.get('BIREYSIRANO', 'Bilgi Yok')}\n"
                    f"┃Medeni Hal: {record.get('MEDENIHAL', 'Bilgi Yok')}\n"
                    f"┃Cinsiyet: {record.get('CINSIYET', 'Bilgi Yok')}\n"
                    f"╰─━━━━━━━━━━━━━─╯"
                )

            file_io = BytesIO(file_content.encode("utf-8"))
            file_io.name = f"{args['isim']}.txt"
            bot.send_document(chat_id, file_io, reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*", parse_mode="Markdown")

    except ValueError as e:
        usage_msg = (
            "⚠️ *Geçersiz Komut Formatı*\n\n"
            "*Kullanım 1:*\n"
            "`/sorgu ahmet yılmaz istanbul Bağcılar`\n\n"
            "*Kullanım 2:*\n"
            "`/sorgu -isim ahmet -soyisim yılmaz -il istanbul -ilce Bağcılar`\n\n"
            "*İki isimli kullanım:*\n"
            "`/sorgu ahmet+can yılmaz`\n"
            "veya\n"
            "`/sorgu -isim ahmet+can -soyisim yılmaz`\n\n"
            f"Hata: {str(e)}"
        )
        bot.reply_to(message, usage_msg, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"⚠️ *Bir hata oluştu. Lütfen tekrar deneyin.*\n\nHata: {str(e)}", parse_mode="Markdown")

@bot.message_handler(commands=['medeni'])
def medeni(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return

    user_id = message.from_user.id
    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_first_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    user_first_name = message.from_user.first_name

    tc = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not tc:
        bot.reply_to(message, '*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/medeni 11111111110`', parse_mode='Markdown')
        return
    try:

        api_url = f"http://172.208.52.218/api/legaliapi/medeni.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()

       
        data = response.json()
        if not data:
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.reply_to(message, '⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri B v  n m ulunamadı!*.', parse_mode='Markdown')
            return

        result_text = (
            f"╭─━━━━━━━━━━━━─╮\n┃*T.C.*: `{tc}`\n"
            f"*┃Ad Soyad:* `{data['data']['AdSoyad']}`\n"
            f"*┃Medeni Hal*: `{data['data']['medenihal']}`\n"
            f"*┃GSM*: `{data['data']['Gsm']}`\n╰─━━━━━━━━━━━━─╯"
        )
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, result_text, parse_mode='Markdown')
    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')

    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')

    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')

    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')

    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f'⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')

#okul no 
#api http://4.227.159.255/api/legaliapi/okulno.php?tc=
@bot.message_handler(commands=['okulno'])
def okulno(message):
    if message.chat.type != "private":
        return
    user_name=message.from_user.username
    user_id = message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
                
    user_id = message.from_user.id
    ban_info = get_ban_info(user_id)
    
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None
    api = f"http://185.242.160.143/apiler/okulno.php?tc={tc}"
    

    
    if tc is None:
        bot.reply_to(message, '*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/okulno 11111111110`', parse_mode='Markdown')
        return
    
    try:
        response = requests.get(api)
        data = response.json()
        if not data:
            bot.reply_to(message, '⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')
            return
        result_text = (f"╭─━━━━━━━━━━━━━─╮\nTC:{tc}\nAD:{data['ad']}\nSOYAD: {data['soyad']}\nOkul No: {data['okulno']}\n╰─━━━━━━━━━━━━━─╯")

        bot.reply_to(message, result_text)
    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')
    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')
    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')
    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')
    except Exception as e:
        bot.reply_to(message, f'⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')



@bot.message_handler(commands=['tckn'])
def tckn(message):
    if message.chat.type != "private":
        return
    user_name=message.from_user.username
    user_id = message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
                
    user_id = message.from_user.id
    ban_info = get_ban_info(user_id)
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(0.1)
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return

    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(0.1)
    
    # Kullanıcının girdiği T.C. numarasını al
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(0.1)
    if not tc:
        bot.reply_to(message, '*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/tckn 11111111110`', parse_mode='Markdown')
        return

    try:

        api_url = f"https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/adpro.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()
    
        data = response.json()
        if not data.get('success') or not data.get('data'):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.reply_to(message, '⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')
            return    
        result_text = (
            f"╭─━━━━━━━━━━━━─╮\n"
            f"┃*T.C*.: `{data['data'][0]['TC']}`\n"
            f"┃*Adı*: `{data['data'][0]['AD'] or 'Bulunamadı'}`\n"
            f"┃*Soyadı:* `{data['data'][0]['SOYAD'] or 'Bulunamadı'}`\n"
            f"┃*Doğum Tarihi:* `{data['data'][0]['DOGUMTARIHI'] or 'Bulunamadı'}`\n"
            f"┃*Nüfus İli:* `{data['data'][0]['MEMLEKETIL'] or 'Bulunamadı'}`\n"
            f"┃*Nüfus İlçesi:* `{data['data'][0]['MEMLEKETILCE'] or 'Bulunamadı'}`\n"
            f"┃*Anne Adı:* `{data['data'][0]['ANNEADI'] or 'Bulunamadı'}`\n"
            f"┃*Anne T.C.*: `{data['data'][0]['ANNETC'] or 'Bulunamadı'}`\n"
            f"┃*Baba Adı:* `{data['data'][0]['BABAADI'] or 'Bulunamadı'}`\n"
            f"┃*Baba T.C*.: `{data['data'][0]['BABATC'] or 'Bulunamadı'}`\n"
            f"┃*Cinsiyet:* `{data['data'][0]['CINSIYET'] or 'Bulunamadı'}`\n"
            f"╰─━━━━━━━━━━━━─╯"
        )

        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, result_text, parse_mode='Markdown')
    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')

    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')

    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')

    except requests.exceptions.RequestException as err:
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.reply_to(message, f'Hata! Genel Hata: {err}')
    except Exception as e:
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.reply_to(message, f'⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')



@bot.message_handler(commands=['kizlik'])
def kizlik(message):
    if message.chat.type != "private":
        return
    user_name=message.from_user.username
    user_id = message.from_user.id
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return

    user_id = message.from_user.id
    ban_info = get_ban_info(user_id)

    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return

   
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not tc:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, '*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/kizlik 11111111110`', parse_mode='Markdown')
        return

    try:
        
        api_url = f"http://172.208.52.218/api/legaliapi/kizlik.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()

      
        data = response.json()
        if not data:
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.reply_to(message, '⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')
            return

        result_text = f"╭─━━━━━━━━━━━━─╮\n┃*T.C*.: `{data['tc']}`\n┃*Kızlık Soyadı:* `{data['kizlikSoyadi']}`\n╰─━━━━━━━━━━━━─╯"
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, result_text, parse_mode='Markdown')

    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')

    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')

    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')

    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')

    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f'⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')




@bot.message_handler(commands=['am'])
def send_random_photo_with_caption(message):
    if message.chat.type != "private":
        return
    user_name=message.from_user.username
    user_id = message.from_user.id
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return

    user_id = message.from_user.id
    ban_info = get_ban_info(user_id)

    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return

    

    if len(message.text.split()) != 2 or not message.text.split()[1].isdigit() or len(message.text.split()[1]) != 11:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_message(message.chat.id, "*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/am 11111111110`", parse_mode='Markdown')
        return

    photo_files = ['1.jpg', '2.jpg', '3.jpg']
    selected_photo = random.choice(photo_files)
    photo_path = os.path.join('', selected_photo)

    
    caption = ""
    if selected_photo == '3.jpg':
        caption = "*Bunu Kaçırma sakın Beyaz En sevdiğim!.*"
    elif selected_photo == '2.jpg':
        caption = "*Bunu Siktir Et amk amına Bak zenciler sikmiş sanki amı buruşmuş şuna bak Kara Amı var!.*"
    elif selected_photo == '1.jpg':
        caption = "*EH işte İdare Eder!.*"

    with open(photo_path, 'rb') as photo:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_photo(message.chat.id, photo, caption, parse_mode='Markdown')


@bot.message_handler(commands=['penis'])
def penis_size(message):
    if message.chat.type != "private":
        return
    user_name=message.from_user.username
    user_id = message.from_user.id
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
    
                
    user_id = message.from_user.id
    ban_info = get_ban_info(user_id)

    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    
    try:
        query = message.text.strip().split(' ')
        if len(query) != 2 or len(query[1]) != 11:
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.reply_to(message, "*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/penis 11111111110`", parse_mode='Markdown')
            return
        
        penis_length = random.choice([6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32])
        penis_unit = 'CM'
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f"╭─━━━━━━━━━━━━━─╮\n┃*T.C* `{query[1]}`\n┃*Penis Boyutu:* `{penis_length}{penis_unit}`\n╰─━━━━━━━━━━━━━─╯", parse_mode='Markdown')
    except IndexError:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, "*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/penis 11111111110`", parse_mode='Markdown')
    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f"⚠️ *Bir hata oluştu: Lütfen daha sonra Tekrar deneyin*", parse_mode='Markdown')


@bot.message_handler(commands=['ayak'])
def penis_size(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return
                
    user_id = message.from_user.id
    ban_info = get_ban_info(user_id)
    user_name=message.from_user.username
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    
    try:
        query = message.text.strip().split(' ')
        if len(query) != 2 or len(query[1]) != 11:
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.reply_to(message, "*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/ayak 11111111110`", parse_mode='Markdown')
            return
        
        penis_length = random.choice([35 ,35.5, 36, 36.5, 37, 37.5 ,38 ,38.5 ,39 ,40 ,41 ,42 ,43 ,44 ,45 ,46 ,47 ,48])
        penis_unit = 'NO'
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f"╭─━━━━━━━━━━━━━─╮\n┃*T.C* `{query[1]}`\n┃*Ayak Boyutu:* `{penis_length}`\n╰─━━━━━━━━━━━━━─╯", parse_mode='Markdown')
    except IndexError:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, "*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/ayak 11111111110`", parse_mode='Markdown')
    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f"⚠️ *Bir hata oluştu: Lütfen daha sonra Tekrar deneyin*", parse_mode='Markdown')


@bot.message_handler(commands=['burc'])
def burc(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck' 
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
            return

    user_id = message.from_user.id
    ban_info = get_ban_info(user_id)

    user_name=message.from_user.username
    if ban_info:
        ban_mes=(
                f"╭─━━━━━━━━━━━━━─╮\n"
                f"|Botan Banlanmışsınız\n\n"
                f"|Kullanıcı Bilgileri\n\n"
                f"|Kullanıcı Adı: {user_name}\n"
                f"|Kullanıcı ID: {user_id}\n\n"
                f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
                f"╰─━━━━━━━━━━━━━─╯"
            )
        bot.send_message(user_id,ban_mes)
        return
    
    user_first_name = message.from_user.first_name
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not tc:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(2)
        bot.reply_to(message, '*⚠️ Lütfen Geçerli Bir T.C Kimlik Numarası girin!\n\nÖrnek:* `/burc 11111111110`', parse_mode='Markdown')
        return

    try:
        api_url = f"http://172.208.52.218/api/legaliapi/burc.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()

        
        data = response.json()
        if not data:
            bot.send_chat_action(message.chat.id, 'typing')
            time.sleep(0.1)
            bot.reply_to(message, '⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')
            return

        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        result_text = f"╭─━━━━━━━━━━━━─╮\n┃*T.C.*: `{tc}`\n┃*Burç:* `{data['data']['burc']}`\n╰─━━━━━━━━━━━━─╯"
        bot.reply_to(message, result_text, parse_mode='Markdown')
    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')

    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')

    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')

    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')

    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f'⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*', parse_mode='Markdown')



@bot.message_handler(commands=['apartman'])
def apartman(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    channel_username1 = '@beplorx'
    channel_username2 = '@bplcheck'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
        return

    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(user_id, ban_mes)
        return

    user_first_name = message.from_user.first_name
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not tc:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, '*⚠️ Lütfen geçerli bir T.C Kimlik Numarası girin!.\nÖrnek:* `/apartman 11111111110`', parse_mode="Markdown")
        return

    try:
        api_url = f"https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/apartman.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()
        print(data)  # Debugging output

        if data.get('success'):
            file_content = "╭─━━━━━━━━━━━━━─╮\n"
            file_content += (
                f"┃TC: {data['data'].get('TC', 'Bilgi Yok')}\n"
                f"┃Ad Soyad: {data['data'].get('ADSOYAD', 'Bilgi Yok')}\n"
                f"┃Doğum Yeri: {data['data'].get('DOGUMYERI', 'Bilgi Yok')}\n"
                f"┃Vergi No: {data['data'].get('VERGINO', 'Bilgi Yok')}\n"
                f"┃Adres: {data['data'].get('ADRES', 'Bilgi Yok')}\n"
                f"┃TSG: {data['data'].get('tsg', 'Bilgi Yok')}\n"
                f"┃Apartmandakiler:\n"
            )
            for person in data['data'].get('Apartmandakiler', []):
                file_content += (
                    f"┃  - TC: {person.get('TC', 'Bilgi Yok')}\n"
                    f"┃    Ad Soyad: {person.get('ADSOYAD', 'Bilgi Yok')}\n"
                    f"┃    Doğum Yeri: {person.get('DOGUMYERI', 'Bilgi Yok')}\n"
                    f"┃    Vergi No: {person.get('VERGINO', 'Bilgi Yok')}\n"
                    f"┃    Adres: {person.get('ADRES', 'Bilgi Yok')}\n"
                )
            file_content += "╰─━━━━━━━━━━━━━─╯\n"

            file_io = BytesIO(file_content.encode("utf-8"))
            file_io.name = f"{tc}i.txt"
            bot.send_document(message.chat.id, file_io, caption=f"Kimin için: {user_first_name}", reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*", parse_mode="Markdown")

    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')
    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')
    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')
    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')
    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        print(e)
        bot.reply_to(message, f'⚠️ *Bir hata oluştu: {e}*', parse_mode="Markdown")



@bot.message_handler(commands=['gsmtc'])
def gsmtc(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
        return

    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(user_id, ban_mes)
        return

    user_first_name = message.from_user.first_name
    gsm = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not gsm:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, '*⚠️ Lütfen geçerli bir GSM Numarası girin!.\nÖrnek:* `/gsmtc 5553723339`', parse_mode="Markdown")
        return

    try:
        api_url = f"https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/gsmtc.php?gsm={gsm}"
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()
        print(data)  # Debugging output

        if data.get('success'):
            file_content = "╭─━━━━━━━━━━━━━─╮\n"
            for record in data.get('data', []):
                file_content += (
                    f"┃ID: {record.get('ID', 'Bilgi Yok')}\n"
                    f"┃Kimlik No: {record.get('TC', 'Bilgi Yok')}\n"
                    f"┃GSM: {record.get('GSM', 'Bilgi Yok')}\n"
                    f"╰─━━━━━━━━━━━━━─╯\n"
                )

            file_io = BytesIO(file_content.encode("utf-8"))
            file_io.name = f"{gsm}.txt"
            bot.send_document(message.chat.id, file_io, caption=f"Kimin için: {user_first_name}", reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "⚠️ *Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!*", parse_mode="Markdown")

    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')
    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')
    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')
    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')
    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        print(e)
        bot.reply_to(message, f'⚠️ *Bir hata oluştu: {e}*', parse_mode="Markdown")




@bot.message_handler(commands=['adres'])
def adres(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_message(user_id, text="Üzgünüm, @bplcheck ve @beplorx gruplarına katılmak zorunludur!", parse_mode="Markdown")
        return

    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(user_id, ban_mes)
        return

    user_first_name = message.from_user.first_name
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not tc:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, '⚠️ Lütfen geçerli bir T.C Kimlik Numarası girin!\nÖrnek: `/adres 11111111110`', parse_mode="Markdown")
        return

    try:
        api_url = f"https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/adres.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()

        if data.get('data'):
            file_content = "╭─━━━━━━━━━━━━━─╮\n"
            for record in data['data']:
                file_content += (
                    f"┃Kimlik No: {record.get('KimlikNo', 'Bilgi Yok')}\n"
                    f"┃Ad Soyad: {record.get('AdSoyad', 'Bilgi Yok')}\n"
                    f"┃Doğum Yeri: {record.get('DogumYeri', 'Bilgi Yok')}\n"
                    f"┃Vergi Numarası: {record.get('VergiNumarasi', 'Bilgi Yok')}\n"
                    f"┃İkametgah: {record.get('Ikametgah', 'Bilgi Yok')}\n"
                    f"╰─━━━━━━━━━━━━━─╯\n"
                )

            file_io = BytesIO(file_content.encode("utf-8"))
            file_io.name = f"{tc}.txt"
            bot.send_document(message.chat.id, file_io, caption=f"Kimin için: {user_first_name}", reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "⚠️ Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!", parse_mode="Markdown")

    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')
    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')
    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')
    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')
    except ValueError as e:
        bot.reply_to(message, f'Hata! JSON Hatası: {e}')
    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f'⚠️ Bir hata oluştu: {e}', parse_mode="Markdown")






#API_ENDPOINT = 'https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/sulale.php?tc={}'
MAX_MESSAGE_LENGTH = 4096



# ...

@bot.message_handler(commands=['sulale'])
def sulale(message):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    channel_username1 = '@bplcheck'
    channel_username2 = '@beplorx'
    if not is_user_in_channel(user_id, channel_username1) or not is_user_in_channel(user_id, channel_username2):
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.send_message(user_id, text="Üzgünüm, [@RodyDuyuru](https://t.me/rodyduyuru) ve [@Rody_Check](https://t.me/rody_check) gruplarına katılmak zorunludur!", parse_mode="Markdown")
        return

    ban_info = get_ban_info(user_id)
    if ban_info:
        ban_mes = (
            f"╭─━━━━━━━━━━━━━─╮\n"
            f"|Botan Banlanmışsınız\n\n"
            f"|Kullanıcı Bilgileri\n\n"
            f"|Kullanıcı ID: {user_id}\n\n"
            f"|Botan Banınızın Kalkmasını İstiyorsanız /desteğe Yaz\n"
            f"╰─━━━━━━━━━━━━━─╯"
        )
        bot.send_message(user_id, ban_mes)
        return

    user_first_name = message.from_user.first_name
    tc = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not tc:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, '⚠️ Lütfen geçerli bir T.C Kimlik Numarası girin!.\nÖrnek: `/sulale 11111111110`', parse_mode="Markdown")
        return

    try:
        api_url = f"https://apiv2.tsgonline.net/tsgapis/OrramaKonmaBurragaKoy/sulale.php?tc={tc}"
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()

        if data.get('success'):
            file_content = "╭─━━━━━━━━━━━━━─╮\n"

            for key, value in data.items():
                if key in ['kendisi', 'annesi', 'babası', 'kardesler', 'cocuklar', 'anne_tarafi_kuzenler', 'baba_tarafi_kardesler', 'baba_tarafi_kuzenler']:
                    for person in value:
                        file_content += (
                            f"┃Yakınlık: {key.capitalize()}\n"
                            f"┃TC: {person.get('TC', 'Bilgi Yok')}\n"
                            f"┃Adı: {person.get('AD', 'Bilgi Yok')}\n"
                            f"┃Soyadı: {person.get('SOYADI', 'Bilgi Yok')}\n"
                            f"┃Doğum Tarihi: {person.get('DOGUMTARIHI', 'Bilgi Yok')}\n"
                            f"┃Nüfus İl: {person.get('MEMLEKETIL', 'Bilgi Yok')}\n"
                            f"┃Nüfus İlçe: {person.get('MEMLEKETILCE', 'Bilgi Yok')}\n"
                            f"┃Anne Adı: {person.get('ANNEADI', 'Bilgi Yok')}\n"
                            f"┃Anne TC: {person.get('ANNETC', 'Bilgi Yok')}\n"
                            f"┃Baba Adı: {person.get('BABAADI', 'Bilgi Yok')}\n"
                            f"┃Baba TC: {person.get('BABATC', 'Bilgi Yok')}\n"
                            f"┃Uyruk: {person.get('CINSIYET', 'Bilgi Yok')}\n"
                            f"╰─━━━━━━━━━━━━━─╯\n"
                        )

            file_io = BytesIO(file_content.encode("utf-8"))
            file_io.name = f"{tc}.txt"
            bot.send_document(message.chat.id, file_io, caption=f"Kimin için: {user_first_name}", reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "⚠️ Girdiğiniz Bilgiler ile Eşleşen Biri Bulunamadı!", parse_mode="Markdown")

    except requests.exceptions.HTTPError as errh:
        bot.reply_to(message, f'Hata! HTTP Error: {errh}')
    except requests.exceptions.ConnectionError as errc:
        bot.reply_to(message, f'Hata! Bağlantı Hatası: {errc}')
    except requests.exceptions.Timeout as errt:
        bot.reply_to(message, f'Hata! Zaman Aşımı Hatası: {errt}')
    except requests.exceptions.RequestException as err:
        bot.reply_to(message, f'Hata! Genel Hata: {err}')
    except ValueError as e:
        bot.reply_to(message, f'Hata! JSON Hatası: {e}')
    except Exception as e:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.1)
        bot.reply_to(message, f'⚠️ Bir hata oluştu: {e}', parse_mode="Markdown")

# ...

def ip_bilgisi(ip_adresi):
    url = f"http://ip-api.com/json/{ip_adresi}"
    response = requests.get(url)
    veri = response.json()

    if veri["status"] == "fail":
        return "Geçersiz IP adresi veya IP adresi bulunamadı."
    else:
        mesaj = f"IP Adresi: {veri['query']}\n"
        mesaj += f"Konum: {veri['city']}, {veri['regionName']}, {veri['country']}\n"
        mesaj += f"Zaman Dilimi: {veri['timezone']}\n"
        mesaj += f"Posta Kodu: {veri['zip']}\n"
        mesaj += f"Koordinatlar: Enlem: {veri['lat']}, Boylam: {veri['lon']}\n"
        mesaj += f"Internet Sağlayıcısı: {veri['isp']}\n"
        mesaj += f"Organizasyon: {veri['org']}\n"
        mesaj += f"IP Türü: {veri['query']}\n"
        

        # IP adresi türünü kontrol et (IPv4 veya IPv6)
        if ":" in ip_adresi:
            ip_turu = "IPv6"
        else:
            ip_turu = "IPv4"
        mesaj += f"IP Adresi Türü: {ip_turu}"

        return mesaj

##PİNKYYDOT 


def ip_bilgisi(ip_adresi):
    url = f"http://ip-api.com/json/{ip_adresi}"
    response = requests.get(url)
    veri = response.json()

    if veri["status"] == "fail":
        return "Geçersiz IP adresi veya IP adresi bulunamadı."
    else:
        mesaj = f"IP Adresi: {veri['query']}\n"
        mesaj += f"Konum: {veri['city']}, {veri['regionName']}, {veri['country']}\n"
        mesaj += f"Zaman Dilimi: {veri['timezone']}\n"
        mesaj += f"Posta Kodu: {veri['zip']}\n"
        mesaj += f"Koordinatlar: Enlem: {veri['lat']}, Boylam: {veri['lon']}\n"
        mesaj += f"Internet Sağlayıcısı: {veri['isp']}\n"
        mesaj += f"Organizasyon: {veri['org']}\n"
        mesaj += f"IP Türü: {veri['query']}\n"
        
        # DNS Bilgileri ekleme
        dns_bilgisi = requests.get(f"https://api.hackertarget.com/dnslookup/?q={ip_adresi}").text
        mesaj += f"DNS Bilgileri:\n{dns_bilgisi}\n"
        
        return mesaj


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
            time.sleep(3600)  # 3 saat = 10800 saniye
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
