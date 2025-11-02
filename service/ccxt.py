import ccxt
# from config import config



def get_btc_price():
    exchange = ccxt.binance()
    ticker = exchange.fetch_ticker('BTC/USDT')
    return ticker['last']



if __name__ == "__main__":
    print(get_btc_price())