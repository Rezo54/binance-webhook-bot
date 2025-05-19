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

# === Safety caps ===
start_balance_usdc = None
max_drawdown_pct = 10  # Stop if USDC drops more than 10%
max_profit_pct = 10    # Stop if USDC grows more than 10%

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
        global start_balance_usdc

        timestamp = int(time.time() * 1000)
        params = {
            "symbol": symbol.upper(),
            "side": action.upper(),
            "type": "MARKET",
            "timestamp": timestamp
        }

        quote_asset = "USDC"
        current_balance = get_spot_balance(quote_asset)

        if start_balance_usdc is None:
            start_balance_usdc = current_balance
            print(f"📌 Opening balance: {start_balance_usdc:.2f} USDC")

        # === Safety Cap: Daily PnL check ===
        change_pct = ((current_balance - start_balance_usdc) / start_balance_usdc) * 100
        if change_pct <= -max_drawdown_pct:
            return {"error": f"📉 Daily loss cap hit: {change_pct:.2f}%"}
        if change_pct >= max_profit_pct:
            return {"error": f"📈 Daily profit cap hit: {change_pct:.2f}%"}

        if action.upper() == "BUY":
            # === Safety: Skip BUY if already holding ETH ===
            base_asset = symbol.upper().replace("USDC", "")
            asset_balance = get_spot_balance(base_asset)
            if asset_balance > 0.001:
                return {"error": f"📦 Already holding {base_asset} — skipping BUY"}

            trade_usdc = round((current_balance * size) / 100, 2)
            if trade_usdc < 5:
                return {"error": f"Trade amount too small (${trade_usdc}). Minimum is $5."}
            params["quoteOrderQty"] = trade_usdc

        elif action.upper() == "SELL":
            base_asset = symbol.upper().replace("USDC", "")
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
