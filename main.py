from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import time
import os

print("✅ Flask app loaded successfully")

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
BASE_URL = "https://api.binance.com"

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Binance webhook bot is live."

# === Get balance for given asset ===
def get_spot_balance(asset):
    try:
        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        timestamp = int(time.time() * 1000)
        params = {"timestamp": timestamp}
        query_string = '&'.join([f"{k}={params[k]}" for k in params])
        signature = hmac.new(
            BINANCE_SECRET_KEY.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature

        response = requests.get(f"{BASE_URL}/api/v3/account", headers=headers, params=params)
        balances = response.json().get("balances", [])
        for b in balances:
            if b["asset"] == asset:
                return float(b["free"])
        return 0.0
    except Exception as e:
        print(f"❌ Balance check failed: {e}")
        return 0.0

# === Send market order ===
def send_order(symbol, action, size):
    try:
        timestamp = int(time.time() * 1000)
        params = {
            "symbol": symbol.upper(),
            "side": action.upper(),
            "type": "MARKET",
            "timestamp": timestamp
        }

        if action.upper() == "BUY":
            quote_asset = "USDC"
            balance = get_spot_balance(quote_asset)
            if balance <= 0:
                return {"error": f"No {quote_asset} balance available to buy."}
            trade_usdc = round((balance * size) / 100, 2)
            if trade_usdc < 5:
                return {"error": f"Trade amount too small (${trade_usdc}). Minimum is $5."}
            params["quoteOrderQty"] = trade_usdc

        elif action.upper() == "SELL":
            base_asset = symbol.upper().replace("USDC", "")  # e.g., ETH from ETHUSDC
            balance = get_spot_balance(base_asset)
            if balance <= 0:
                return {"error": f"No {base_asset} balance available to sell."}
            params["quantity"] = round(balance, 6)

        else:
            return {"error": f"Invalid action: {action}"}

        query_string = '&'.join([f"{k}={params[k]}" for k in params])
        signature = hmac.new(
            BINANCE_SECRET_KEY.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature

        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        response = requests.post(f"{BASE_URL}/api/v3/order", headers=headers, params=params)
        return response.json()

    except Exception as e:
        return {"error": str(e)}

# === Webhook route ===
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📦 Webhook received:", data)

    symbol = data.get("symbol")
    action = data.get("action")
    size = data.get("size")

    if not all([symbol, action, size is not None]):
        return jsonify({"error": "Missing one or more required fields"}), 400

    try:
        size = float(size)
    except ValueError:
        return jsonify({"error": "Invalid size format"}), 400

    result = send_order(symbol, action, size)
    print("✅ Binance response:", result)
    return jsonify(result)

# === Run server ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
