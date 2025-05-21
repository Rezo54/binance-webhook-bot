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
max_drawdown_pct = 5  # Stop if USDC drops more than 5%
max_profit_pct = 3    # Stop if USDC grows more than 5%
target_profit_pct = 1.5  # 1.2% target for limit sell after buy

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

        if start_balance_usdc is None or start_balance_usdc == 0:
            start_balance_usdc = current_balance
            print(f"📌 Opening balance initialized: {start_balance_usdc:.2f} USDC")

        # Proceed only if starting balance is valid
        if start_balance_usdc > 0:
            change_pct = ((current_balance - start_balance_usdc) / start_balance_usdc) * 100
        if change_pct <= -max_drawdown_pct:
            return {"error": f"📉 Daily loss cap hit: {change_pct:.2f}%"}
        if change_pct >= max_profit_pct:
            return {"error": f"📈 Daily profit cap hit: {change_pct:.2f}%"}
    
        if action.upper() == "BUY":
            base_asset = symbol.upper().replace("USDC", "")
            asset_balance = get_spot_balance(base_asset)
            if asset_balance > 0.001:
                return {"error": f"📦 Already holding {base_asset} — skipping BUY"}

            trade_usdc = round((current_balance * size) / 100, 2)
            if trade_usdc < 5:
                return {"error": f"Trade amount too small (${trade_usdc}). Minimum is $5."}
            params["quoteOrderQty"] = trade_usdc

            # Place market BUY
            query_string = '&'.join([f"{k}={params[k]}" for k in params])
            signature = hmac.new(
                BINANCE_SECRET_KEY.encode(),
                query_string.encode(),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature
            headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
            response = requests.post(f"{BASE_URL}/api/v3/order", headers=headers, params=params)
            buy_result = response.json()

            if "fills" not in buy_result:
                return {"error": "BUY order did not return fills", "details": buy_result}

            # Get avg fill price and quantity bought
            fills = buy_result.get("fills", [])
            total_qty = sum(float(f["qty"]) for f in fills)
            total_cost = sum(float(f["qty"]) * float(f["price"]) for f in fills)
            avg_price = total_cost / total_qty if total_qty else 0
            target_price = round(avg_price * (1 + target_profit_pct / 100), 2)

            print(f"🎯 Target price set at {target_price} for {total_qty} {base_asset}")

            # Place limit SELL at target
            sell_params = {
                "symbol": symbol.upper(),
                "side": "SELL",
                "type": "LIMIT",
                "quantity": round(total_qty, 6),
                "price": target_price,
                "timeInForce": "GTC",
                "timestamp": int(time.time() * 1000)
            }
            sell_qs = '&'.join([f"{k}={sell_params[k]}" for k in sell_params])
            sell_sig = hmac.new(BINANCE_SECRET_KEY.encode(), sell_qs.encode(), hashlib.sha256).hexdigest()
            sell_params["signature"] = sell_sig
            sell_resp = requests.post(f"{BASE_URL}/api/v3/order", headers=headers, params=sell_params)
            sell_result = sell_resp.json()

            return {"buy": buy_result, "limit_sell": sell_result}

        elif action.upper() == "SELL":
            base_asset = symbol.upper().replace("USDC", "")
            balance = get_spot_balance(base_asset)
            if balance <= 0:
                return {"error": f"No {base_asset} balance available to sell."}
            params["quantity"] = round(balance, 6)

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

        else:
            return {"error": f"Invalid action: {action}"}

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
