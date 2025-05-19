from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import time
import os

print("✅ Flask app loaded successfully")

# Load Binance API keys from environment
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Binance webhook bot is live."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📦 Webhook received:", data)

    symbol = data.get("symbol")
    action = data.get("action")
    size = data.get("size")

    if not all([symbol, action, size]):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        size = float(size)
    except ValueError:
        return jsonify({"error": "Invalid size format"}), 400

    timestamp = int(time.time() * 1000)
    params = {
        "symbol": symbol.upper(),
        "side": action.upper(),
        "type": "MARKET",
        "quantity": size,
        "timestamp": timestamp
    }

    query_string = '&'.join([f"{k}={params[k]}" for k in params])
    signature = hmac.new(
        BINANCE_SECRET_KEY.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()
    params["signature"] = signature

    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    response = requests.post("https://api.binance.com/api/v3/order", headers=headers, params=params)
    
    return jsonify(response.json())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
