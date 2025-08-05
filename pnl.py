#!/usr/bin/env python3
import os
import json
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

api_key = os.getenv("BYBIT_API_KEY")
api_secret = os.getenv("BYBIT_SECRET_KEY")

client = HTTP(api_key=api_key, api_secret=api_secret)

def get_recent_closed_pnls(symbol="SOLUSDT", limit=5):
    try:
        response = client.get_closed_pnl(
            category="linear",
            symbol=symbol,
            limit=limit
        )
        if response['retCode'] != 0:
            print("❌ Error:", response)
            return

        print(f"\n📊 Last {limit} Closed PnL Records for {symbol}:\n")
        for row in response['result']['list']:
            print(f"🧾 Time:         {row['updatedTime']}")
            print(f"🆔 Order ID:     {row['orderId']}")
            print(f"   🔹 Realized PnL: {row['closedPnl']} USDT")
            print(f"   🔹 Entry Price:  {row['avgEntryPrice']}")
            print(f"   🔹 Exit Price:   {row['avgExitPrice']}")
            print(f"   🔹 Size:         {row['qty']} contracts")
            print(f"   🔹 Side:         {row['side']}")
            print("-" * 40)

    except Exception as e:
        print("❌ Exception:", str(e))

if __name__ == "__main__":
    get_recent_closed_pnls("SOLUSDT", 5)
