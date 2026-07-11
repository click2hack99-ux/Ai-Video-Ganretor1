import requests
import json
import os
import time
import telebot
from flask import Flask, request
import threading

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = "8635537345:AAHy2OCc2Fh40eMcPSy3VV5aZXf6x2vL_JQ"
API_KEY = "demo"
DOMAIN = "https://antifiednullxosint.com"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ==========================================
# SESSION STORAGE
# ==========================================
user_sessions = {}

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
    bot.reply_to(message, 
        "👋 *Welcome to Aadhaar PDF Generator Bot*\n\n"
        "Send me a 10-digit mobile number to start.\n"
        "Example: `9876543210`\n\n"
        "Or type /help for instructions.",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda msg: msg.text and msg.text.strip().isdigit() and len(msg.text.strip()) == 10)
def handle_mobile(message):
    chat_id = message.chat.id
    mobile = message.text.strip()
    
    bot.send_chat_action(chat_id, 'typing')
    msg = bot.reply_to(message, f"🔄 Processing mobile: `{mobile}` ...", parse_mode='Markdown')
    
    res = client.init_phase1(mobile)
    
    if "process_id" not in res:
        bot.edit_message_text(
            f"❌ Error: {res.get('detail', 'Unknown error')}",
            chat_id, msg.message_id
        )
        return
    
    process_id = res['process_id']
    user_sessions[chat_id] = {
        'process_id': process_id,
        'mobile': mobile,
        'step': 'otp1'
    }
    
    bot.edit_message_text(
        f"✅ OTP sent to mobile.\n\n"
        f"📌 Process ID: `{process_id}`\n"
        f"📌 Status: {res.get('message', 'OTP sent')}\n\n"
        f"✉️ Reply with **OTP 1 (EID OTP)**",
        chat_id, msg.message_id,
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda msg: msg.chat.id in user_sessions and user_sessions[msg.chat.id]['step'] == 'otp1')
def handle_otp1(message):
    chat_id = message.chat.id
    otp1 = message.text.strip()
    session = user_sessions[chat_id]
    process_id = session['process_id']
    
    bot.send_chat_action(chat_id, 'typing')
    msg = bot.reply_to(message, "🔄 Verifying OTP 1 ...")
    
    res = client.verify_phase1(process_id, otp1)
    
    if "original_name" not in res:
        bot.edit_message_text(
            f"❌ Error: {res.get('detail', 'Invalid OTP')}",
            chat_id, msg.message_id
        )
        return
    
    name = res['original_name']
    eid = res['eid_number']
    
    session['step'] = 'otp2'
    session['name'] = name
    session['eid'] = eid
    
    bot.edit_message_text(
        f"✅ OTP 1 Verified!\n\n"
        f"👤 Name: `{name}`\n"
        f"🆔 EID: `{eid}`\n"
        f"📌 Status: {res.get('message', 'Verified')}\n\n"
        f"✉️ Reply with **OTP 2 (Download OTP)**",
        chat_id, msg.message_id,
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
    msg = bot.reply_to(message, "🔄 Generating PDF...")
    
    safe_name = "".join(c for c in name if c.isalnum())
    pdf_name = f"{safe_name}_Unlocked_Aadhaar.pdf"
    
    res = client.verify_phase2(process_id, otp2, pdf_name)
    
    if res.get("status") == "success":
        with open(pdf_name, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"✅ PDF Generated!\n👤 Name: {name}\n📁 File: {pdf_name}")
        
        bot.delete_message(chat_id, msg.message_id)
        os.remove(pdf_name)
        del user_sessions[chat_id]
    else:
        bot.edit_message_text(
            f"❌ Error: {res.get('detail', 'Failed to generate PDF')}",
            chat_id, msg.message_id
        )

@bot.message_handler(func=lambda msg: True)
def fallback(message):
    bot.reply_to(message, 
        "⚠️ Invalid input.\n"
        "Send a valid **10-digit mobile number** to start.\n"
        "Or type /help for instructions."
    )

# ==========================================
# FLASK WEBHOOK (Render ke liye)
# ==========================================
@app.route('/')
def home():
    return """
    <h1>🤖 Aadhaar PDF Bot is LIVE!</h1>
    <p>Bot is running successfully on port 5000</p>
    <p>Send a 10-digit mobile number to @your_bot_username on Telegram</p>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# ==========================================
# MAIN ENTRY - FORCED PORT 5000
# ==========================================
if __name__ == "__main__":
    # Webhook set karo
    RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://your-app.onrender.com')
    WEBHOOK_URL = f"{RENDER_URL}/webhook"
    
    # Bot ko webhook pe set karo
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook set to: {WEBHOOK_URL}")
    except Exception as e:
        print(f"⚠️ Webhook error: {e}")
    
    # PORT ko force karo 5000
    port = 5000
    print(f"🚀 Starting bot on port {port}...")
    
    # Flask server start - hamesha port 5000
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
