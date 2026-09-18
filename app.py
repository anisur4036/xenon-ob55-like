# MINISTER LIKE API SRC UID PASSWORD 
# POWERED BY : @jihadx24
# CHANNEL : @jihad_x_leaker
from flask import Flask, request, jsonify, send_from_directory
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
import time
from collections import defaultdict
from datetime import datetime
import random
import os
import urllib.parse

import jwt
from datetime import timedelta

TOKEN_CACHE = {}

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return send_from_directory(app.root_path, "index.html")

KEY_LIMIT = 99
tracker = defaultdict(lambda: [0, time.time()])  # IP based tracking

# Store which accounts have liked which UIDs (temporary memory)
liked_cache = defaultdict(set)

def get_today_midnight_timestamp():
    now = datetime.now()
    midnight = datetime(now.year, now.month, now.day)
    return midnight.timestamp()

def load_accounts(server_name):
    """Load UID:Password from server-specific file"""
    try:
        # Map server to filename
        if server_name == "IND":
            filename = "account_ind.txt"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            filename = "account_br.txt"
        else:  # BD and others
            filename = "account_bd.txt"
        
        # Check if file exists
        if not os.path.exists(filename):
            print(f"⚠️ {filename} not found, trying account_ind.txt")
            filename = "account_ind.txt"
            if not os.path.exists(filename):
                print(f"❌ No account file found")
                return []
        
        accounts = []
        print(f"📂 Loading from: {filename} for server {server_name}")
        
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if ':' in line:
                    parts = line.split(':', 1)
                    uid = parts[0].strip()
                    password = parts[1].strip()
                    
                    if uid and password:
                        accounts.append({
                            "uid": uid,
                            "password": password
                        })
        
        print(f"✅ Total {len(accounts)} accounts loaded for {server_name}")
        return accounts
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

async def generate_jwt_token(uid, password):
    """Generate JWT token"""
    try:
        encoded_password = urllib.parse.quote(password)
        url = f"https://jihad-jwt.lovable.app/api/public/token?uid={uid}&password={encoded_password}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=24) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if isinstance(data, dict):
                        if 'jwt_token' in data:
                            return data['jwt_token']
                        elif 'token' in data:
                            return data['token']
                return None
    except:
        return None


async def get_valid_token(uid, password):

    if uid in TOKEN_CACHE:
        cached = TOKEN_CACHE[uid]

        remaining = (
            cached["expires_at"] - datetime.utcnow()
        ).total_seconds()

        if remaining > 1800:
            return cached["token"]

    token = await generate_jwt_token(uid, password)

    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False}
        )

        exp = payload.get("exp")

        TOKEN_CACHE[uid] = {
            "token": token,
            "expires_at": datetime.utcfromtimestamp(exp)
        }

    except:
        TOKEN_CACHE[uid] = {
            "token": token,
            "expires_at": datetime.utcnow() + timedelta(hours=24)
        }

    return token

def encrypt_message(plaintext):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(plaintext, AES.block_size)
    return binascii.hexlify(cipher.encrypt(padded_message)).decode('utf-8')

def create_protobuf_message(user_id, region):
    message = like_pb2.like()
    message.uid = int(user_id)
    message.region = region
    return message.SerializeToString()

async def check_if_already_liked(target_uid, token, server_name):
    """Check if already liked by getting profile info"""
    try:
        encrypted_uid = enc(target_uid)
        info = get_player_info(encrypted_uid, server_name, token)
        if info:
            # Can't directly check, so we'll rely on response
            return False
        return False
    except:
        return False

async def send_like(encrypted_uid, token, url):
    """Send like with token"""
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB55"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers, timeout=5) as response:
                return response.status
    except:
        return 500

async def process_account(target_uid, encrypted_uid, account, url, semaphore, server_name):
    """Process single account with smart checking"""
    async with semaphore:
        # Check if this account already liked this UID today
        account_key = f"{account['uid']}:{target_uid}"
        
        # Generate token
        token = await get_valid_token(account['uid'], account['password'])
        if not token:
            return 500, account['uid']
        
        # Send like
        status = await send_like(encrypted_uid, token, url)
        
        # If successful, mark as liked
        if status == 200:
            liked_cache[target_uid].add(account['uid'])
            return status, account['uid']
        
        return status, account['uid']

async def send_all_likes(target_uid, server_name, url):
    """Send likes from all accounts with smart checking"""
    region = server_name
    protobuf_message = create_protobuf_message(target_uid, region)
    encrypted_uid = encrypt_message(protobuf_message)
    
    accounts = load_accounts(server_name)
    if not accounts: 
        return {'success': 0, 'failed': 0, 'total': 0, 'already_liked': 0}
    
    # Filter out accounts that already liked this UID
    already_liked = liked_cache.get(target_uid, set())
    fresh_accounts = [acc for acc in accounts if acc['uid'] not in already_liked]
    
    print(f"📊 Total accounts: {len(accounts)}")
    print(f"✅ Fresh accounts: {len(fresh_accounts)}")
    print(f"⏭️  Already liked: {len(already_liked)}")
    
    if not fresh_accounts:
        return {
            'success': 0, 
            'failed': 0, 
            'total': len(accounts),
            'already_liked': len(already_liked),
            'fresh_used': 0
        }
    
    random.shuffle(fresh_accounts)
    
    semaphore = asyncio.Semaphore(25)
    tasks = []
    for acc in fresh_accounts[:2000]:  # Limit to 50 fresh accounts per request
        tasks.append(process_account(target_uid, encrypted_uid, acc, url, semaphore, server_name))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = 0
    failed = 0
    for r in results:
        if isinstance(r, tuple):
            status, uid = r
            if status == 200:
                successful += 1
            else:
                failed += 1
    
    return {
        'success': successful,
        'failed': failed,
        'total': len(accounts),
        'already_liked': len(already_liked),
        'fresh_used': len(fresh_accounts[:2000])
    }

def enc(uid):
    message = uid_generator_pb2.uid_generator()
    message.krishna_ = int(uid)
    message.teamXdarks = 1
    return encrypt_message(message.SerializeToString())

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except:
        return None

def get_player_info(encrypted_uid, server_name, token):
    """Get player info with proper URL for each server"""
    if server_name == "IND":
        url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    else:
        url = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"

    edata = bytes.fromhex(encrypted_uid)
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Authorization': f"Bearer {token}",
        'Content-Type': "application/x-www-form-urlencoded",
        'X-GA': "v1 1",
        'ReleaseVersion': "OB55"
    }

    try:
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=10)
        return decode_protobuf(response.content)
    except:
        return None

@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    server_name = request.args.get("server_name", "").upper()
    key = request.args.get("key")
    client_ip = request.remote_addr

    if key != "XENON_OFC":
        return jsonify({"error": "Invalid or missing API key 🔑"}), 403

    if not uid or not server_name:
        return jsonify({"error": "UID and server_name are required"}), 400

    # Valid servers
    valid_servers = ["IND", "BR", "US", "SAC", "NA", "BD","RU"]
    if server_name not in valid_servers:
        return jsonify({"error": f"Invalid server. Use: {valid_servers}"}), 400

    # Load accounts for this server
    accounts = load_accounts(server_name)
    if not accounts:
        # Try fallback to IND
        accounts = load_accounts("IND")
        if not accounts:
            return jsonify({"error": f"No accounts found for server {server_name}"}), 500
        print(f"⚠️ Using IND accounts as fallback for {server_name}")
    
    # Check daily limit
    today_midnight = get_today_midnight_timestamp()
    count, last_reset = tracker[client_ip]

    if last_reset < today_midnight:
        tracker[client_ip] = [0, time.time()]
        count = 0

    if count >= KEY_LIMIT:
        return jsonify({"error": "Daily limit reached", "remains": f"(0/{KEY_LIMIT})"}), 429

    # Generate token for checking (try multiple accounts)
    check_token = None
    for account in accounts[:5]:
        check_token = asyncio.run(get_valid_token(account['uid'], account['password']))
        if check_token:
            print(f"✅ Token generated with UID: {account['uid']}")
            break
    
    if not check_token:
        return jsonify({"error": "Token generation failed - no valid accounts"}), 500
    
    encrypted_uid = enc(uid)

    # Before likes
    before = get_player_info(encrypted_uid, server_name, check_token)
    if before is None:
        return jsonify({"error": "Invalid UID or server", "status": 0}), 200

    try:
        before_data = json.loads(MessageToJson(before))
        before_like = int(before_data['AccountInfo'].get('Likes', 0))
    except:
        return jsonify({"error": "Data parsing failed", "status": 0}), 200

    # Like URL based on server
    if server_name == "IND":
        like_url = "https://client.ind.freefiremobile.com/LikeProfile"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        like_url = "https://client.us.freefiremobile.com/LikeProfile"
    else:
        like_url = "https://clientbp.ggpolarbear.com/LikeProfile"

    # Send likes with smart checking
    result = asyncio.run(send_all_likes(uid, server_name, like_url))

    # After likes
    after = get_player_info(encrypted_uid, server_name, check_token)
    if after is None:
        return jsonify({"error": "Could not verify likes after command", "status": 0}), 200

    try:
        after_data = json.loads(MessageToJson(after))
        after_like = int(after_data['AccountInfo']['Likes'])
        player_id = int(after_data['AccountInfo']['UID'])
        player_name = str(after_data['AccountInfo']['PlayerNickname'])
        
        like_given = after_like - before_like
        status = 1 if like_given != 0 else 2
        
        if like_given > 0:
            tracker[client_ip][0] += 1
            count += 1
        
        remains = KEY_LIMIT - count

        return jsonify({
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_like,
            "LikesbeforeCommand": before_like,
            "PlayerNickname": player_name,
            "UID": player_id,
            "status": status,
            "remains": f"({remains}/{KEY_LIMIT})",    
        })
    except Exception as e:
        return jsonify({"error": str(e), "status": 0}), 500

@app.route('/reset-cache', methods=['GET'])
def reset_cache():
    """Reset liked cache (use carefully)"""
    key = request.args.get("key")
    if key != "XENON_OFC":
        return jsonify({"error": "Invalid key"}), 403
    
    global liked_cache
    liked_cache.clear()
    return jsonify({"message": "Cache cleared", "credit": "@jihadx24"})

if __name__ == '__main__':
    print("🚀 Server started - Smart Like System!")
    print("📁 Account files:")
    print("   - account_ind.txt (IND server)")
    print("   - account_br.txt (BR/US/SAC/NA servers)")
    print("   - account_bd.txt (BD/RU server)")
    print("🧠 Smart feature: Tracks which accounts already liked")
    print("⚡ Only fresh accounts will send likes")
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
# MINISTER LIKE API SRC UID PASSWORD 
# POWERED BY : @jihadx24
# CHANNEL : @jihad_x_leaker