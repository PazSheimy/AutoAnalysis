from flask import Flask, render_template, jsonify, request
import threading
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import ta
import sys
import time
import webview

app = Flask(__name__)

# Connect to MT5
def connect_to_mt5():
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        sys.exit()
    print('Connected to MT5')

# Get real-time data
def get_realtime_data(instrument, timeframe, lookback):
    rates = mt5.copy_rates_from_pos(instrument, timeframe, 0, lookback)
    data = pd.DataFrame(rates, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'])
    data['time'] = pd.to_datetime(data['time'], unit='s')
    return data

def calculate_indicators(data):
    # Example: Simple Moving Average (SMA)
    data['SMA'] = ta.trend.SMAIndicator(data['close'], window=9).sma_indicator()
    n = 20
   
    # Calculate Standard Deviation using a population approach
    data['StdDev'] = data['close'].rolling(window=n).apply(lambda x: np.std(x, ddof=0))

    # Calculate 1st Standard Deviation lower and higher
    data['1sdLower'] = data['close'] - data['StdDev']
    data['1sdHigher'] = data['close'] + data['StdDev']

    # Calculate 2nd Standard Deviation lower and higher
    data['2sdLower'] = data['close'] - (2 * data['StdDev'])
    data['2sdHigher'] = data['close'] + (2 * data['StdDev'])

    # Calculate Lower Band and Upper Band
    data['LowerBand'] = data.apply(lambda row: min(row['close'], row['1sdLower'], row['2sdLower']), axis=1)
    data['UpperBand'] = data.apply(lambda row: max(row['close'], row['1sdHigher'], row['2sdHigher']), axis=1)


    # Add more indicators here as needed

    return data

@app.route('/data', methods=['POST'])
def add_custom_price():
    custom_price = request.json['price']
    instrument = 'EURUSD'
    timeframe = mt5.TIMEFRAME_H1
    lookback = 100
    data = get_realtime_data(instrument, timeframe, lookback)
    data_with_indicators = calculate_indicators(data)
    data_with_indicators.fillna(0, inplace=True)
    
    new_row = data_with_indicators.iloc[-1].copy()
    new_row['close'] = custom_price
    new_row = calculate_indicators(pd.DataFrame([new_row]))
    new_row.fillna(0, inplace=True)
    json_data = new_row.to_dict(orient='records')[0]
    json_data['time'] = json_data['time'].strftime('%Y-%m-%dT%H:%M:%S')
    return jsonify(json_data)



@app.route('/')
def index():
    return render_template('index.html')


@app.route('/data')
def get_data():
    custom_price = request.args.get('price', type=float)
    instrument = 'EURUSD'
    timeframe = mt5.TIMEFRAME_H1
    lookback = 30
    data = get_realtime_data(instrument, timeframe, lookback)
    data_with_indicators = calculate_indicators(data)
    data_with_indicators.fillna(0, inplace=True)

    if custom_price is not None:
        n = 20
        new_data = data_with_indicators.iloc[-n:].copy()
        new_data = new_data.append(pd.Series({"close": custom_price}), ignore_index=True)

        # Calculate indicators for the new data with the custom price
        new_data_with_indicators = calculate_indicators(new_data)
        new_data_with_indicators.fillna(0, inplace=True)

        # Get the last row with the custom price and its calculated indicators
        new_row = new_data_with_indicators.iloc[-1]

        # Set the time of the new row to be the same as the last row in data_with_indicators
        new_row['time'] = data_with_indicators.iloc[-1]['time']

        data_with_indicators = data_with_indicators.append(new_row, ignore_index=True)

    json_data = data_with_indicators.to_dict(orient='records')
    for record in json_data:
        record['time'] = record['time'].strftime('%Y-%m-%dT%H:%M:%S')
    return jsonify(json_data)


def run_app():
    app.run()

if __name__ == '__main__':
    connect_to_mt5()
    t = threading.Thread(target=run_app)
    t.start()

    # Create a web view window
    webview.create_window('AutoAnalysis', 'http://127.0.0.1:5000', min_size=(800, 600))
    webview.start()