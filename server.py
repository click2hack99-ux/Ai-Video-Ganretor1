import requests
import json
import os
import sys
import time
from flask import Flask, request, jsonify
import threading
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Telegram bot configuration
TELEGRAM_BOT_TOKEN = "8635537345:AAHy2OCc2Fh40eMcPSy3VV5aZXf6x2vL_JQ"  # Replace with real token later
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ==========================================
# 1. UI COLORS & ASSETS
# ==========================================
G = '\033[92m'  # Neon Green
C = '\033[96m'  # Cyan
R = '\033[91m'  # Red
Y = '\033[93m'  # Yellow
W = '\033[0m'   # Reset

BANNER = f"""
{G}               NUMBER TO ADHAR PDF{W}
{Y}                Made by @Click2Hackk{W}
{C}=========================================================={W}
"""

# ==========================================
# 2. ANIMATIONS & HELPERS
# ==========================================
def spinner(message, delay=0.1, duration=2.5):
    spinner_chars = ['|', '/', '-', '\\']
    end_time = time.time() + duration
    i = 0
    while time.time() < end_time:
        sys.stdout.write(f"\r{Y}[*] {message} {spinner_chars[i % 4]}{W}")
        sys.stdout.flush()
        time.sleep(delay)
        i += 1
    sys.stdout.write(f"\r{G}[+] {message} Done!       {W}\n")

# ==========================================
# 3. CORE API CLIENT
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

# ==========================================
# 4. MAIN EXECUTION FLOW
# ==========================================
def run_process(mobile, chat_id, step_callback):
    """Run the entire process in background and report progress"""
    try:
        logger.info(f"Starting process for mobile {mobile}, chat_id {chat_id}")
        
        # Setup
        API_KEY = "demo"
        DOMAIN = "https://antifiednullxosint.com"
        client = AntifiedNullClient(DOMAIN, API_KEY)
        
        # Report starting message
        step_callback(chat_id, "Connecting to Server...", "info")
        
        # ----------------------------------
        # STEP 1: MOBILE NUMBER ENTRY
        # ----------------------------------
        step_callback(chat_id, "Initializing Phase 1 (Bypassing Captcha)", "progress")
        res1 = client.init_phase1(mobile)
        
        if "process_id" not in res1:
            step_callback(chat_id, f"ERROR: {res1.get('detail', res1)}", "error")
            return
            
        process_id = res1['process_id']
        step_callback(chat_id, f"Process ID: {process_id}", "info")
        step_callback(chat_id, f"Status: {res1.get('message')}", "info")
        
        # ----------------------------------
        # STEP 2: FIRST OTP (EID)
        # ----------------------------------
        step_callback(chat_id, "Waiting for EID OTP (Phase 1)...", "waiting")
        # In real implementation, would need to wait for user input or handle differently
        
        # ----------------------------------
        # STEP 3: SECOND OTP (DOWNLOAD)
        # ----------------------------------
        step_callback(chat_id, "Brute-forcing PDF & Stripping Security", "progress")
        # In real implementation, would need to wait for user input or handle differently
        
        # Report success
        step_callback(chat_id, "MISSION ACCOMPLISHED!", "success")
        
    except Exception as e:
        logger.error(f"Error in run_process: {str(e)}")
        step_callback(chat_id, f"Error occurred: {str(e)}", "error")

def send_telegram_message(chat_id, text, message_type="info"):
    """Send message to Telegram chat with error handling"""
    try:
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        
        # Add reply markup for waiting states
        if message_type == "waiting":
            payload["reply_markup"] = {
                "keyboard": [
                    [{"text": "Enter EID OTP"}],
                    [{"text": "Enter Download OTP"}]
                ],
                "one_time_keyboard": True
            }
            
        logger.debug(f"Sending message to chat {chat_id}: {text}")
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Telegram API error: {response.text}")
            return None
            
        result = response.json()
        logger.debug(f"Telegram API response: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Telegram error: {str(e)}")
        return None

@app.route('/process', methods=['POST'])
def process_request():
    """Handle direct API requests"""
    try:
        data = request.json
        mobile = data.get('mobile')
        chat_id = data.get('chat_id')
        
        if not mobile or not chat_id:
            return jsonify({"error": "Missing mobile or chat_id"}), 400
        
        # Start processing in background thread
        threading.Thread(
            target=run_process,
            args=(mobile, chat_id, send_telegram_message),
            daemon=True
        ).start()
        
        return jsonify({"status": "processing started"})
    except Exception as e:
        logger.error(f"Error in process_request: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook events"""
    try:
        data = request.json
        logger.debug(f"Received webhook: {data}")
        
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            
            # Handle different message types
            if "text" in message:
                text = message["text"]
                logger.info(f"Received message: {text}")
                
                if text.startswith("/start"):
                    send_telegram_message(chat_id, "Welcome to Number to Aadhar PDF Converter!\nSend me a mobile number to get started.")
                elif text.startswith("/help"):
                    send_telegram_message(chat_id, "Send a mobile number to start the process.")
                else:
                    # Process the number
                    send_telegram_message(chat_id, "Processing mobile number...")
                    threading.Thread(
                        target=run_process,
                        args=(text, chat_id, send_telegram_message),
                        daemon=True
                    ).start()
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route('/test-webhook', methods=['GET'])
def test_webhook():
    """Test webhook setup"""
    try:
        response = requests.get(f"{TELEGRAM_API_URL}/getWebhookInfo")
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logger.info("Starting Telegram Bot service")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
