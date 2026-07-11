#!/usr/bin/env python3
# Aadhaar PDF Bot - With Auto Retry & Polling Thread
# Powered by Click 2 Hack

import requests
import json
import os
import time
import telebot
import re
import threading
from flask import Flask, request
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = "8635537345:AAHy2OCc2Fh40eMcPSy3VV5aZXf6x2vL_JQ"
API_KEY = "demo"
DOMAIN = "https://antifiednullxosint.com"
ADMIN_ID = 8475582345

# 📢 Force join channels (optional)
CHANNELS = ["@Click2Hackk", "@c2hget"]

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

bot_running = True
last_activity = datetime.now()
user_sessions = {}

# ==========================================
# CHECK JOIN (optional)
# ==========================================
def is_joined(user_id):
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            print(f"Error checking channel {ch}: {e}")
            return False
    return True

# ==========================================
# CORE API CLIENT
# ==========================================
class AntifiedNullClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json', 'accept': 'application/json'})

    def init_phase1(self, mobile):
        url = f"{self.base_url}/api/v1/init-phase1?key={self.api_key}"
        try:
            return self.session.post(url, json={"mobile_number": mobile}).json()
        except Exception as e:
            return {"detail": f"Request Failed: {str(e)}"}

    def verify_phase1(self, process_id, otp1):
        url = f"{self.base_url}/api/v1/verify-phase1?key={self.api_key}"
        try:
            return self.session.post(url, json={"process_id": process_id, "otp1": otp1}).json()
        except Exception as e:
            return {"detail": f"Request Failed: {str(e)}"}

    def verify_phase2(self, process_id, otp2, output_filename):
        url = f"{self.base_url}/api/v1/verify-phase2?key={self.api_key}"
        try:
            response = self.session.post(url, json={"process_id": process_id, "otp2": otp2})
            if response.status_code == 200:
                with open(output_filename, "wb") as f:
                    f.write(response.content)
                return {"status": "success", "file": output_filename}
            return response.json()
        except Exception as e:
            return {"detail": f"Request Failed: {str(e)}"}

client = AntifiedNullClient(DOMAIN, API_KEY)

# ==========================================
# BOT COMMAND HANDLERS
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def start(message):
    user_id = message.from_user.id
    if not is_joined(user_id):
        text = "🚫 कृपया पहले हमारे दोनों चैनल जॉइन करें:\n\n"
        for ch in CHANNELS:
            text += f"👉 https://t.me/{ch.replace('@','')}\n"
        text += "\n✅ दोनों चैनल जॉइन करने के बाद /start दोबारा भेजें।"
        return bot.reply_to(message, text)
    
    bot.reply_to(message, 
        "👋 *Aadhaar PDF Generator Bot*\n\n"
        "📱 बस 10 अंकों का मोबाइल नंबर भेजें (जैसे: `9876543210`)\n\n"
        "⚡ फिर OTP भेजकर PDF प्राप्त करें",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip().isdigit() and len(msg.text.strip()) == 10)
def handle_mobile(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not is_joined(user_id):
        text = "🚫 कृपया पहले हमारे दोनों चैनल जॉइन करें:\n\n"
        for ch in CHANNELS:
            text += f"👉 https://t.me/{ch.replace('@','')}\n"
        text += "\n✅ जॉइन करने के बाद दोबारा नंबर भेजें।"
        return bot.reply_to(message, text)
    
    mobile = message.text.strip()
    
    bot.send_chat_action(chat_id, 'typing')
    status_msg = bot.reply_to(message, f"⏳ `{mobile}` पर कार्य हो रहा है...", parse_mode='Markdown')
    
    res = client.init_phase1(mobile)
    
    if "process_id" not in res:
        bot.edit_message_text(
            f"❌ Error: {res.get('detail', 'Unknown error')}",
            chat_id, status_msg.message_id
        )
        return
    
    process_id = res['process_id']
    user_sessions[chat_id] = {
        'process_id': process_id,
        'mobile': mobile,
        'step': 'otp1'
    }
    
    bot.edit_message_text(
        f"✅ OTP भेज दिया गया है!\n\n"
        f"📌 Process ID: `{process_id}`\n"
        f"📌 Status: {res.get('message', 'OTP sent')}\n\n"
        f"✉️ अब **OTP 1 (EID OTP)** भेजें",
        chat_id, status_msg.message_id,
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda msg: msg.chat.id in user_sessions and user_sessions[msg.chat.id]['step'] == 'otp1')
def handle_otp1(message):
    chat_id = message.chat.id
    otp1 = message.text.strip()
    session = user_sessions[chat_id]
    process_id = session['process_id']
    
    bot.send_chat_action(chat_id, 'typing')
    status_msg = bot.reply_to(message, "⏳ OTP 1 वेरिफाई हो रहा है...")
    
    res = client.verify_phase1(process_id, otp1)
    
    if "original_name" not in res:
        bot.edit_message_text(
            f"❌ Error: {res.get('detail', 'Invalid OTP')}",
            chat_id, status_msg.message_id
        )
        return
    
    name = res['original_name']
    eid = res['eid_number']
    
    session['step'] = 'otp2'
    session['name'] = name
    session['eid'] = eid
    
    bot.edit_message_text(
        f"✅ OTP 1 वेरिफाई हो गया!\n\n"
        f"👤 नाम: `{name}`\n"
        f"🆔 EID: `{eid}`\n"
        f"📌 Status: {res.get('message', 'Verified')}\n\n"
        f"✉️ अब **OTP 2 (Download OTP)** भेजें",
        chat_id, status_msg.message_id,
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda msg: msg.chat.id in user_sessions and user_sessions[msg.chat.id]['step'] == 'otp2')
def handle_otp2(message):
    chat_id = message.chat.id
    otp2 = message.text.strip()
    session = user_sessions[chat_id]
    process_id = session['process_id']
    name = session['name']
    
    bot.send_chat_action(chat_id, 'upload_document')
    status_msg = bot.reply_to(message, "⏳ PDF जनरेट हो रहा है...")
    
    safe_name = "".join(c for c in name if c.isalnum())
    pdf_name = f"{safe_name}_Unlocked_Aadhaar.pdf"
    
    res = client.verify_phase2(process_id, otp2, pdf_name)
    
    if res.get("status") == "success":
        with open(pdf_name, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✅ PDF जनरेट हो गया!\n👤 नाम: {name}\n📁 File: {pdf_name}")
        
        bot.delete_message(chat_id, status_msg.message_id)
        os.remove(pdf_name)
        del user_sessions[chat_id]
    else:
        bot.edit_message_text(
            f"❌ Error: {res.get('detail', 'Failed to generate PDF')}",
            chat_id, status_msg.message_id
        )

@bot.message_handler(func=lambda msg: True)
def fallback(message):
    bot.reply_to(message, 
        "⚠️ Invalid input.\n"
        "10 अंकों का मोबाइल नंबर भेजें (जैसे: `9876543210`)\n"
        "या /help देखें।",
        parse_mode='Markdown'
    )

# ==========================================
# FLASK ROUTES (Render Health Check)
# ==========================================
@app.route('/')
def home():
    return {
        "status": "Aadhaar PDF Bot is running",
        "api": DOMAIN,
        "features": ["Mobile number lookup", "OTP verification", "PDF generation"]
    }, 200

@app.route('/health')
def health():
    return {"status": "healthy", "bot_running": bot_running}, 200

# ==========================================
# POLLING THREAD (Exactly like your other bot)
# ==========================================
def run_bot_polling():
    global bot_running
    while bot_running:
        try:
            print("🔄 Bot polling started with AUTO DETECT...")
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"❌ Polling error: {e}")
            if bot_running:
                print("🔄 Restarting in 10 seconds...")
                time.sleep(10)

# ==========================================
# MAIN ENTRY
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    
    print("="*50)
    print("🤖 AADHAAR PDF BOT - AUTO DETECT")
    print("="*50)
    print(f"✅ Domain: {DOMAIN}")
    print(f"✅ API Key: {API_KEY}")
    print(f"✅ Auto Phone Detect: सीधा नंबर भेजो")
    print(f"✅ Force Join: {CHANNELS}")
    print("="*50)
    
    # Polling thread start karo (exactly like your other bot)
    polling_thread = threading.Thread(target=run_bot_polling)
    polling_thread.daemon = True
    polling_thread.start()
    
    # Flask server start - port 5000 pe
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
