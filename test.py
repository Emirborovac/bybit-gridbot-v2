#!/usr/bin/env python3
"""
FIXED Position Reversal Test - Manual Testing Tool
SOLUTION: Close current position + Open new position with target USDT size
This method gives us EXACT control over the new position size!
"""

import json
import os
import time
from decimal import Decimal, ROUND_DOWN, getcontext
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

getcontext().prec = 18
load_dotenv()

class FixedReversalTester:
    def __init__(self):
        # Load credentials
        self.api_key = os.getenv("BYBIT_API_KEY")
        self.api_secret = os.getenv("BYBIT_SECRET_KEY")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("🔴 API credentials missing")
        
        # Initialize client
        self.client = HTTP(api_key=self.api_key, api_secret=self.api_secret)
        
        # Load config
        with open("config.json", "r") as f:
            config = json.load(f)
        
        self.symbol = config["SYMBOL"]
        self.leverage = config["LEVERAGE"]
        self.sl_roe = config["SL"]["ROE"]
        self.tp_roe = config["TP"]["ROE"]
        
        # Get instrument info
        self.get_instrument_info()
        
        print(f"🟢 FIXED Reversal Tester Ready - {self.symbol}")
        print(f"   Leverage: {self.leverage}x")
        print(f"   Min Qty: {self.min_qty}")
    
    def get_instrument_info(self):
        """Get instrument info"""
        res = self.client.get_instruments_info(category="linear", symbol=self.symbol)
        if res["retCode"] != 0:
            raise ValueError("Failed to get instrument info")
        
        info = res['result']['list'][0]
        self.qty_step = float(info["lotSizeFilter"]["qtyStep"])
        self.min_qty = float(info["lotSizeFilter"]["minOrderQty"])
    
    def get_price(self):
        """Get current price"""
        res = self.client.get_tickers(category="linear", symbol=self.symbol)
        return float(res["result"]["list"][0]["lastPrice"])
    
    def round_down(self, value, step):
        """Round down quantity"""
        d_value = Decimal(str(value))
        d_step = Decimal(str(step))
        rounded = (d_value // d_step) * d_step
        return float(rounded.quantize(d_step, rounding=ROUND_DOWN))
    
    def calculate_position_size(self, usdt_amount):
        """Calculate position size from USDT amount"""
        price = self.get_price()
        raw_qty = (usdt_amount * self.leverage) / price
        qty = self.round_down(raw_qty, self.qty_step)
        
        if qty < self.min_qty:
            qty = self.min_qty
        
        return qty, price
    
    def get_position_info(self):
        """Get current position"""
        res = self.client.get_positions(category="linear", symbol=self.symbol)
        if res["retCode"] != 0:
            return None
        
        for pos in res["result"]["list"]:
            if float(pos["size"]) > 0:
                return {
                    "side": pos["side"],
                    "size": float(pos["size"]),
                    "entry_price": float(pos["avgPrice"]),
                    "unrealized_pnl": float(pos["unrealisedPnl"]),
                    "value": float(pos["size"]) * float(pos["avgPrice"])
                }
        return None
    
    def place_order_with_tpsl(self, side, qty, price):
        """Place order with TP/SL"""
        # Calculate TP/SL
        if side == "Buy":
            sl_price = price * (1 - self.sl_roe / 100 / self.leverage)
            tp_price = price * (1 + self.tp_roe / 100 / self.leverage)
        else:
            sl_price = price * (1 + self.sl_roe / 100 / self.leverage)
            tp_price = price * (1 - self.tp_roe / 100 / self.leverage)
        
        print(f"🎯 Placing {side} order:")
        print(f"   Qty: {qty} {self.symbol.replace('USDT', '')}")
        print(f"   Entry: ${price:.4f}")
        print(f"   TP: ${tp_price:.4f}")
        print(f"   SL: ${sl_price:.4f}")
        
        try:
            result = self.client.place_order(
                category="linear",
                symbol=self.symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
                timeInForce="IOC",
                takeProfit=str(round(tp_price, 2)),
                stopLoss=str(round(sl_price, 2)),
                tpOrderType="Market",
                slOrderType="Market",
                tpslMode="Full",
                positionIdx=0
            )
            
            if "error" in result:
                print(f"🔴 Order failed: {result}")
                return False
            else:
                print(f"🟢 Order placed successfully!")
                return True
                
        except Exception as e:
            print(f"🔴 Exception: {e}")
            return False
    
    def place_order_no_tpsl(self, side, qty):
        """Place order WITHOUT TP/SL (for closing positions)"""
        print(f"🔄 Placing {side} order (no TP/SL):")
        print(f"   Qty: {qty} {self.symbol.replace('USDT', '')}")
        
        try:
            result = self.client.place_order(
                category="linear",
                symbol=self.symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
                timeInForce="IOC",
                positionIdx=0
            )
            
            if "error" in result:
                print(f"🔴 Order failed: {result}")
                return False
            else:
                print(f"🟢 Order executed successfully!")
                return True
                
        except Exception as e:
            print(f"🔴 Exception: {e}")
            return False
    
    def close_position(self):
        """Close current position"""
        pos = self.get_position_info()
        if not pos:
            print("🔴 No position to close")
            return False
        
        close_side = "Sell" if pos["side"] == "Buy" else "Buy"
        return self.place_order_no_tpsl(close_side, pos["size"])
    
    def show_position(self):
        """Show current position"""
        pos = self.get_position_info()
        if pos:
            usdt_margin = pos["value"] / self.leverage
            print(f"\n📊 Current Position:")
            print(f"   Side: {pos['side']}")
            print(f"   Size: {pos['size']} {self.symbol.replace('USDT', '')}")
            print(f"   Entry: ${pos['entry_price']:.4f}")
            print(f"   Value: ${pos['value']:.2f}")
            print(f"   Margin: ${usdt_margin:.2f} USDT")
            print(f"   Unrealized P&L: ${pos['unrealized_pnl']:.2f}")
        else:
            print("📊 No active position")
    
    # 🚀 NEW METHODS - FIXED REVERSAL LOGIC
    
    def reverse_with_close_open_method(self, target_usdt_amount):
        """
        🚀 SOLUTION: Close current position + Open new position with exact USDT size
        This gives us PERFECT control over the new position size!
        """
        current_pos = self.get_position_info()
        if not current_pos:
            print("🔴 No position to reverse")
            return False
        
        print(f"\n🚀 === FIXED REVERSAL METHOD ===")
        print(f"Current: {current_pos['side']} {current_pos['size']} (${current_pos['value']/self.leverage:.2f} margin)")
        print(f"Target: {target_usdt_amount} USDT position in reverse direction")
        
        # Determine reverse side
        reverse_side = "Sell" if current_pos["side"] == "Buy" else "Buy"
        
        # Calculate new position size based on target USDT
        target_qty, current_price = self.calculate_position_size(target_usdt_amount)
        
        print(f"\n📤 Step 1: Closing current {current_pos['side']} position...")
        close_success = self.close_position()
        
        if not close_success:
            print("🔴 Failed to close position")
            return False
        
        # Wait for position to close
        print("⏳ Waiting for position to close...")
        time.sleep(3)
        
        # Verify position is closed
        check_pos = self.get_position_info()
        if check_pos:
            print("🔴 Position still exists after close attempt")
            return False
        
        print(f"📥 Step 2: Opening {reverse_side} position with {target_usdt_amount} USDT...")
        open_success = self.place_order_with_tpsl(reverse_side, target_qty, current_price)
        
        if open_success:
            print(f"🟢 REVERSAL COMPLETE!")
            print(f"   New Position: {reverse_side} {target_qty}")
            print(f"   Target Size: ${target_usdt_amount} USDT")
            return True
        else:
            print("🔴 Failed to open new position")
            return False
    
    def reverse_with_single_order_method(self, target_usdt_amount):
        """
        🚀 ALTERNATIVE: Single order method with calculated quantity
        Calculate exact quantity needed to achieve target position after closing current
        """
        current_pos = self.get_position_info()
        if not current_pos:
            print("🔴 No position to reverse")
            return False
        
        print(f"\n🚀 === SINGLE ORDER REVERSAL METHOD ===")
        
        # Determine reverse side
        reverse_side = "Sell" if current_pos["side"] == "Buy" else "Buy"
        
        # Calculate target position size
        target_qty, current_price = self.calculate_position_size(target_usdt_amount)
        
        # Calculate total quantity needed (current + target)
        # This will close current position AND open new position in one order
        total_qty = current_pos["size"] + target_qty
        
        print(f"Current: {current_pos['side']} {current_pos['size']}")
        print(f"Target: {reverse_side} {target_qty} (${target_usdt_amount} USDT)")
        print(f"Total order: {reverse_side} {total_qty}")
        
        success = self.place_order_with_tpsl(reverse_side, total_qty, current_price)
        
        if success:
            print(f"🟢 SINGLE ORDER REVERSAL COMPLETE!")
            return True
        else:
            print("🔴 Single order reversal failed")
            return False

def main():
    tester = FixedReversalTester()
    
    while True:
        print("\n" + "="*60)
        print("🚀 FIXED REVERSAL TESTER - SOLUTION COMMANDS:")
        print("="*60)
        print("BASIC COMMANDS:")
        print("1. show     - Show current position")
        print("2. open5    - Open position with $5 USDT")
        print("3. open10   - Open position with $10 USDT")
        print("4. close    - Close position")
        print("")
        print("🚀 FIXED REVERSAL METHODS:")
        print("5. rev10co  - Reverse with $10 USDT (Close+Open method)")
        print("6. rev15co  - Reverse with $15 USDT (Close+Open method)")
        print("7. rev20co  - Reverse with $20 USDT (Close+Open method)")
        print("8. rev10so  - Reverse with $10 USDT (Single Order method)")
        print("9. rev15so  - Reverse with $15 USDT (Single Order method)")
        print("0. exit     - Exit program")
        print("="*60)
        
        cmd = input("🤖 Enter command: ").strip().lower()
        
        if cmd == "show":
            tester.show_position()
            
        elif cmd == "open5":
            qty, price = tester.calculate_position_size(5.0)
            tester.place_order_with_tpsl("Buy", qty, price)
            time.sleep(2)
            tester.show_position()
            
        elif cmd == "open10":
            qty, price = tester.calculate_position_size(10.0)
            tester.place_order_with_tpsl("Buy", qty, price)
            time.sleep(2)
            tester.show_position()
            
        elif cmd == "close":
            tester.close_position()
            time.sleep(2)
            tester.show_position()
            
        # 🚀 FIXED REVERSAL METHODS
        elif cmd == "rev10co":
            tester.reverse_with_close_open_method(10.0)
            time.sleep(3)
            tester.show_position()
            
        elif cmd == "rev15co":
            tester.reverse_with_close_open_method(15.0)
            time.sleep(3)
            tester.show_position()
            
        elif cmd == "rev20co":
            tester.reverse_with_close_open_method(20.0)
            time.sleep(3)
            tester.show_position()
            
        elif cmd == "rev10so":
            tester.reverse_with_single_order_method(10.0)
            time.sleep(3)
            tester.show_position()
            
        elif cmd == "rev15so":
            tester.reverse_with_single_order_method(15.0)
            time.sleep(3)
            tester.show_position()
            
        elif cmd == "exit":
            break
            
        else:
            print("🔴 Invalid command")

if __name__ == "__main__":
    main()