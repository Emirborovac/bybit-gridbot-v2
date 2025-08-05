#!/usr/bin/env python3
"""
Price Monitor - Real-time WebSocket price monitoring
Based on proven WebSocket implementation
"""

import os
import time
from pybit.unified_trading import WebSocket
from dotenv import load_dotenv

load_dotenv()

class PriceMonitor:
    def __init__(self, symbol, callback=None):
        self.symbol = symbol
        self.callback = callback
        self.ws = None
        self.running = False
        self.last_price = None
        
        # Get API credentials
        self.api_key = os.getenv("BYBIT_API_KEY")
        self.api_secret = os.getenv("BYBIT_SECRET_KEY")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("🔴 BYBIT_API_KEY and BYBIT_SECRET_KEY must be set")
    
    def handle_ticker(self, msg):
        """Handle ticker messages (your exact method)"""
        if "data" in msg and isinstance(msg["data"], dict):
            price = msg["data"].get("lastPrice")
            if price:
                price = float(price)
                self.last_price = price
                
                # Call the callback function if provided
                if self.callback:
                    self.callback(price)
    
    def start(self):
        """Start WebSocket price monitoring (your exact setup)"""
        try:
            self.ws = WebSocket(
                testnet=False,
                channel_type="linear",
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            self.ws.ticker_stream(
                symbol=self.symbol,
                callback=self.handle_ticker
            )
            
            self.running = True
            print(f"🟢 Price monitor started for {self.symbol}")
            
        except Exception as e:
            print(f"🔴 WebSocket start error: {e}")
            self.running = False
    
    def stop(self):
        """Stop WebSocket monitoring"""
        self.running = False
        if self.ws:
            try:
                # Note: pybit WebSocket doesn't have explicit close method
                # Connection will be closed when object is destroyed
                self.ws = None
                print(f"🟡 Price monitor stopped for {self.symbol}")
            except Exception as e:
                print(f"🔴 WebSocket stop error: {e}")
    
    def get_last_price(self):
        """Get the last received price"""
        return self.last_price
    
    def is_connected(self):
        """Check if WebSocket is connected"""
        return self.running and self.ws is not None

# Standalone test function
def test_price_monitor():
    """Test the price monitor independently"""
    
    def price_callback(price):
        print(f"🟡 [{time.time():.6f}] Price: {price}")
    
    symbol = "SOLUSDT"
    monitor = PriceMonitor(symbol=symbol, callback=price_callback)
    
    print(f"🟢 Testing price monitor for {symbol}...")
    monitor.start()
    
    try:
        while True:
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("🟡 Test stopped by user")
        monitor.stop()

if __name__ == "__main__":
    test_price_monitor()