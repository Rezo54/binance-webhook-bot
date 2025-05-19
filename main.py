from flask import Flask, request
import requests, hmac, hashlib, time
import os

app = Flask(__name__)

BINANCE_API_KEY = os.getenv('RwfBf5ZAdWTvoqfa0w59MUxGamfto6SYdLKjuIERKeorPg0l7wHS5JLZZUh22yCW')
BINANCE_SECRET_KEY = os.getenv('IKtF2T91DI4FuyfBqBcxEFIXlyouzkeRLD5EVf87Q0KEptdBOsm3yUpSwlMYDRsv')
BASE_URL = 'https://api.binance.com'

def send_order(symbol, side, quantity):
    timestamp = int(time.time() * 1000)
    params = {
        'symbol': symbol.upper(),
        'side': side.upper(),
        'type': 'MARKET',
        'quantity': quantity,
        'timestamp': timestamp
    }
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    signature = hmac.new(BINANCE_SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params['signature'] = signature
    headers = {'X-MBX-APIKEY': BINANCE_API_KEY}
    return requests.post(f"{BASE_URL}/api/v3/order", headers=headers, params=params).json()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    symbol = data.get('symbol')
    action = data.get('action')
    size = float(data.get('size', 0))
    if symbol and action and size > 0:
        return send_order(symbol, action, size)
    return {'error': 'Invalid data'}, 400

if __name__ == '__main__':
    app.run()
