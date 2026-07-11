import requests
import json
import os
import sys
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from flask import Flask
import threading
import signal

# ==========================================
# 1. UI COLORS & ASSETS
# ==========================================
G = '\033[92m'  # Neon Green
C = '\033[96m'  # Cyan
R = '\033[91m'  # Red
Y = '\033[93m'  # Yellow
W = '\033[0m'   # Reset

# Conversation states
WAITING_MOBILE, WAITING_OTP1, WAITING_OTP2 = range(3)

# Store user data temporarily
user_data = {}

# Flask app for keeping alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# ==========================================
# 2. CORE API CLIENT
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

# Initialize API client
API_KEY = "demo"
DOMAIN = "https://antifiednullxosint.com"
client = AntifiedNullClient(DOMAIN, API_KEY)

# ==========================================
# 3. TELEGRAM BOT HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🔍 Start Search", callback_data='start_search')],
        [InlineKeyboardButton("ℹ️ Help", callback_data='help')],
        [InlineKeyboardButton("📞 Contact Developer", url='https://t.me/Click2Hackk')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🌟 *Welcome to Number to Aadhaar Bot!*\n\n"
        f"👋 Hello {user.first_name}!\n\n"
        f"🔐 *This bot helps you retrieve Aadhaar PDF*\n\n"
        f"📱 Click 'Start Search' to begin\n"
        f"ℹ️ Click 'Help' for instructions",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'start_search':
        await query.message.reply_text(
            "📱 *Please enter the target mobile number:*\n\n"
            "Format: 10-digit number\n"
            "Example: 9876543210\n\n"
            "Type /cancel to abort",
            parse_mode='Markdown'
        )
        return WAITING_MOBILE
    
    elif query.data == 'help':
        await query.message.reply_text(
            "📖 *How to use this bot:*\n\n"
            "1️⃣ Click 'Start Search'\n"
            "2️⃣ Enter the 10-digit mobile number\n"
            "3️⃣ Enter EID OTP when prompted\n"
            "4️⃣ Enter Download OTP when prompted\n"
            "5️⃣ Receive the Aadhaar PDF\n\n"
            "⚠️ *Requirements:*\n"
            "• Valid mobile number\n"
            "• Access to OTPs\n"
            "• Active internet connection\n\n"
            "Type /start to go back",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

async def get_mobile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the mobile number"""
    mobile = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Validate mobile number
    if not mobile.isdigit() or len(mobile) != 10:
        await update.message.reply_text(
            "❌ *Invalid mobile number!*\n\n"
            "Please enter a valid 10-digit mobile number.\n"
            "Type /cancel to abort",
            parse_mode='Markdown'
        )
        return WAITING_MOBILE
    
    # Send processing message
    msg = await update.message.reply_text("🔄 *Initializing Phase 1...*\n⏳ Bypassing Captcha...", parse_mode='Markdown')
    
    # Call API
    res1 = client.init_phase1(mobile)
    
    if "process_id" not in res1:
        await msg.edit_text(f"❌ *ERROR:* {res1.get('detail', res1)}", parse_mode='Markdown')
        return ConversationHandler.END
    
    # Store process ID
    process_id = res1['process_id']
    user_data[user_id] = {
        'process_id': process_id,
        'mobile': mobile
    }
    
    await msg.edit_text(
        f"✅ *Phase 1 Initialized!*\n\n"
        f"🔑 Process ID: `{process_id}`\n"
        f"📱 Mobile: `{mobile}`\n"
        f"📊 Status: {res1.get('message', 'Ready')}\n\n"
        f"📩 *Please enter the EID OTP (Phase 1):*",
        parse_mode='Markdown'
    )
    return WAITING_OTP1

async def get_otp1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the first OTP"""
    otp1 = update.message.text.strip()
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Session expired. Please /start again.")
        return ConversationHandler.END
    
    process_id = user_data[user_id]['process_id']
    
    msg = await update.message.reply_text("🔄 *Verifying OTP 1...*\n🔍 Extracting Target Info...", parse_mode='Markdown')
    
    res2 = client.verify_phase1(process_id, otp1)
    
    if "original_name" not in res2:
        await msg.edit_text(f"❌ *ERROR:* {res2.get('detail', res2)}", parse_mode='Markdown')
        return ConversationHandler.END
    
    # Store user info
    user_data[user_id].update({
        'name': res2['original_name'],
        'eid': res2['eid_number']
    })
    
    name = res2['original_name']
    eid = res2['eid_number']
    
    await msg.edit_text(
        f"🎯 *TARGET ACQUIRED!*\n\n"
        f"👤 ━━ Name: *{name}*\n"
        f"🆔 ━━ EID: `{eid}`\n"
        f"📊 ━━ Status: {res2.get('message', 'Ready')}\n\n"
        f"📩 *Please enter the Download OTP (Phase 2):*",
        parse_mode='Markdown'
    )
    return WAITING_OTP2

async def get_otp2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the second OTP and send PDF"""
    otp2 = update.message.text.strip()
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Session expired. Please /start again.")
        return ConversationHandler.END
    
    process_id = user_data[user_id]['process_id']
    name = user_data[user_id]['name']
    
    msg = await update.message.reply_text("🔄 *Processing...*\n🔓 Brute-forcing PDF & Stripping Security...", parse_mode='Markdown')
    
    # Generate filename
    safe_name = "".join(c for c in name if c.isalnum())
    pdf_name = f"{safe_name}_Unlocked_Aadhaar.pdf"
    
    res3 = client.verify_phase2(process_id, otp2, pdf_name)
    
    if res3.get("status") == "success":
        # Send the PDF file
        await msg.edit_text("📤 *Uploading PDF to Telegram...*", parse_mode='Markdown')
        
        try:
            with open(res3['file'], 'rb') as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    filename=pdf_name,
                    caption=f"🎉 *MISSION ACCOMPLISHED!* [✓]\n\n"
                           f"👤 Name: *{name}*\n"
                           f"📄 Aadhaar PDF successfully retrieved!\n\n"
                           f"🔒 Stay safe, use responsibly.\n"
                           f"👨‍💻 Made by @Click2Hackk",
                    parse_mode='Markdown'
                )
            
            await msg.delete()
            
            # Clean up file
            try:
                os.remove(res3['file'])
            except:
                pass
        except Exception as e:
            await msg.edit_text(f"❌ *Error sending file:* {str(e)}", parse_mode='Markdown')
            return ConversationHandler.END
        
        # Clear user data
        if user_id in user_data:
            del user_data[user_id]
    else:
        await msg.edit_text(f"❌ *ERROR:* {res3.get('detail', res3)}", parse_mode='Markdown')
        return ConversationHandler.END
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation"""
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    await update.message.reply_text(
        "🚫 *Operation cancelled.*\n\n"
        "Type /start to begin again.",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# ==========================================
# 4. MAIN FUNCTION
# ==========================================
def run_flask():
    """Run Flask on port 5000"""
    app.run(host='0.0.0.0', port=5000)

def main():
    """Start the bot."""
    # Your bot token
    TOKEN = "8635537345:AAEIcMVDIieiwlGlHWLr2Dr82Hhny3qcyss"
    
    # Start Flask in background
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Create the Application
    application = Application.builder().token(TOKEN).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_handler)
        ],
        states={
            WAITING_MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mobile)],
            WAITING_OTP1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_otp1)],
            WAITING_OTP2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_otp2)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    
    # Start the bot
    print(f"{G}[✓] Bot is running...{W}")
    print(f"{C}[i] Flask server on port 5000{W}")
    print(f"{C}[i] Press Ctrl+C to stop{W}")
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print(f"\n{R}[!] Bot stopped by user.{W}")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{R}[!] Bot stopped by user.{W}")
        sys.exit()
