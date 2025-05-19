from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import time
import os

app = Flask(__name__)

BINANCE_API_KEY = os.getenv('RwfBf5ZAdWTvoqfa0w59MUxGamfto6SYdLKjuIERKeorPg0l7wHS5JLZZUh22yCW')
BINANCE_SECRET_KEY = os.getenv('IKtF2T91DI4FuyfBqBcxEFIXlyouzkeRLD5EVf87Q0KEptdBOsm3yUpSwlMYDRsv')
BASE_URL = 'https://api.binance.com'

# === Binance Spot Order Function ===
def send_order(symbol, side, quantity):
    try:
        timestamp = int(time.time() * 1000)

        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": quantity,
            "timestamp": timestamp
        }

        # Generate signature
        query_string = '&'.join([f"{key}={params[key]}" for key in params])
        signature = hmac.new(
            BINANCE_SECRET_KEY.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature

        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}

        # Send order
        response = requests.post(f"{BASE_URL}/api/v3/order", headers=headers, params=params)
        return response.json()

    except Exception as e:
        return {"error": str(e)}

# === Webhook Endpoint ===
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("Received webhook:", data)

    symbol = data.get("symbol")
    action = data.get("action")
    size = data.get("size")

    if not all([symbol, action, size]):
        return jsonify({"error": "Missing one or more required fields"}), 400

    try:
        size = float(size)
    except ValueError:
        return jsonify({"error": "Invalid size format"}), 400

    result = send_order(symbol, action, size)
    return jsonify(result)

