from flask import Flask, render_template, request
import decimal
import json
import requests
import websocket
import plotly
import plotly.graph_objs as go

app = Flask(__name__)

S = "BNBUSDT"
N = 8
T = "30m"
L = 3

close_prices = []
candle_count = 0
data = []
sma_values = []


def calculate_sma(prices, n):
    if len(prices) < n:
        return None
    sma = sum(prices[-n:]) / n
    return sma


def get_historical_candles(symbol, interval, limit):
    api_url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        candles = json.loads(response.text)
        closing_prices = [decimal.Decimal(candle[4]) for candle in candles]
        return closing_prices
    else:
        print("Не вдалося отримати історичні свічки з Binance API.")
        return []


def on_message(ws, message):
    global candle_count, data, sma_values

    json_message = json.loads(message)
    candles = json_message["k"]

    close_price = decimal.Decimal(candles["c"])
    close_prices.append(close_price)

    if len(close_prices) > N:
        close_prices.pop(0)

    sma_value = calculate_sma(close_prices, N)
    print(f"Ціна закриття: {close_price}, SMA: {sma_value}")

    if close_price > sma_value:
        candle_count += 1
    else:
        candle_count = 0

    if candle_count >= L:
        message = f"Ціна закриття {close_price} перевищує SMA {sma_value} протягом {candle_count} свічок."
        print(message)
        candle_count = 0
        data.append(close_price)  # Add the close price to the graph data
        sma_values.append(sma_value)  # Add the SMA value to the sma_values list

    if len(data) > L:
        data.pop(0)  # Remove the oldest data point if the data exceeds the limit L
        sma_values.pop(0)  # Remove the corresponding SMA value


# WebSocket on_close event handler
def on_close(ws):
    print("WebSocket connection closed.")


@app.route('/', methods=['GET', 'POST'])
def index():
    global S, N, T, L, close_prices, data, sma_values

    if request.method == 'POST':
        S = request.form['symbol']
        N = int(request.form['period'])
        T = request.form['interval']
        L = int(request.form['limit'])

        closing_prices = get_historical_candles(S, T, N)
        if closing_prices:
            close_prices = closing_prices[-N:]

        SOCKET = f"wss://stream.binance.com:9443/ws/{S.lower()}@kline_{T}"
        ws = websocket.WebSocketApp(SOCKET, on_message=on_message, on_close=on_close)
        ws.run_forever()

    graph_data = go.Scatter(x=list(range(len(data))), y=data, mode='lines', name='Close Price')
    sma_data = go.Scatter(x=list(range(len(sma_values))), y=sma_values, mode='lines', name='SMA')
    graph_layout = go.Layout(title='Close Price vs. Time')
    graph_fig = go.Figure(data=[graph_data, sma_data], layout=graph_layout)
    graph_html = plotly.offline.plot(graph_fig, output_type='div')

    notification_visible = candle_count >= L  # Check if notification should be visible

    return render_template('index.html', symbol=S, period=N, interval=T, limit=L, close_prices=close_prices,
                           graph_html=graph_html, candle_count=candle_count, limit_value=L,
                           notification_visible=notification_visible)


if __name__ == '__main__':
    app.run(debug=True)
