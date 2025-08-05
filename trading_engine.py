#!/usr/bin/env python3
"""
Trading Engine - Order execution and position management
Based on proven ByBit API methods
"""

import os
from decimal import Decimal, ROUND_DOWN, getcontext
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

getcontext().prec = 18
load_dotenv()

class TradingEngine:
    def __init__(self, config):
        # API credentials
        self.api_key = os.getenv("BYBIT_API_KEY")
        self.api_secret = os.getenv("BYBIT_SECRET_KEY")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("🔴 BYBIT_API_KEY and BYBIT_SECRET_KEY must be set")
        
        # Initialize HTTP client (your exact method)
        self.client = HTTP(api_key=self.api_key, api_secret=self.api_secret)
        
        # Config
        self.symbol = config["SYMBOL"]
        self.leverage = config["LEVERAGE"]
        self.sl_roe = config["SL"]["ROE"]
        self.tp_roe = config["TP"]["ROE"]
        
        # Instrument info
        self.instrument_info = None
        self.qty_step = None
        self.min_qty = None
        
        print(f"🟢 Trading Engine initialized for {self.symbol}")
    
    def initialize(self):
        """Initialize trading engine with instrument info"""
        self.instrument_info = self.get_instrument_info()
        if not self.instrument_info:
            raise ValueError("🔴 Failed to fetch instrument info")
        
        self.qty_step = float(self.instrument_info["lotSizeFilter"]["qtyStep"])
        self.min_qty = float(self.instrument_info["lotSizeFilter"]["minOrderQty"])
        
        print(f"🟢 Instrument info loaded - Min qty: {self.min_qty}, Step: {self.qty_step}")
    
    def get_instrument_info(self):
        """Get instrument info (your exact method)"""
        try:
            res = self.client.get_instruments_info(category="linear", symbol=self.symbol)
            if res["retCode"] != 0:
                print("🔴 Error fetching instrument info:", res)
                return None
            return res['result']['list'][0]
        except Exception as e:
            print(f"🔴 Instrument info error: {e}")
            return None
    
    def get_price(self):
        """Get current price (your exact method)"""
        try:
            res = self.client.get_tickers(category="linear", symbol=self.symbol)
            return float(res["result"]["list"][0]["lastPrice"])
        except Exception as e:
            print(f"🔴 Price fetch error: {e}")
            return None
    
    def round_down(self, value: float, step: float) -> float:
        """Round down quantity (your exact method)"""
        d_value = Decimal(str(value))
        d_step = Decimal(str(step))
        rounded = (d_value // d_step) * d_step
        return float(rounded.quantize(d_step, rounding=ROUND_DOWN))
    
    def calculate_position_size(self, usdt_amount, price=None):
        """Calculate position size based on USDT amount"""
        if not price:
            price = self.get_price()
            if not price:
                return None
        
        raw_qty = (usdt_amount * self.leverage) / price
        qty = self.round_down(raw_qty, self.qty_step)
        
        if qty < self.min_qty:
            qty = self.min_qty
        
        return qty
    
    def calculate_tp_sl_prices(self, side, entry_price):
        """Calculate TP/SL prices (your exact logic)"""
        if side == "Buy":
            sl_price = entry_price * (1 - self.sl_roe / 100 / self.leverage)
            tp_price = entry_price * (1 + self.tp_roe / 100 / self.leverage)
        else:  # Sell
            sl_price = entry_price * (1 + self.sl_roe / 100 / self.leverage)
            tp_price = entry_price * (1 - self.tp_roe / 100 / self.leverage)
        
        return tp_price, sl_price
    
    def place_order(self, side, qty, stop_loss, take_profit):
        """Place order with TP/SL (your exact method)"""
        try:
            return self.client.place_order(
                category="linear",
                symbol=self.symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
                timeInForce="IOC",
                takeProfit=str(round(take_profit, 2)),
                stopLoss=str(round(stop_loss, 2)),
                tpOrderType="Market",
                slOrderType="Market",
                tpslMode="Full",
                positionIdx=0
            )
        except Exception as e:
            return {"error": str(e)}
    
    def place_grid_order(self, side, usdt_amount, price=None):
        """Place a grid order with calculated TP/SL"""
        if not price:
            price = self.get_price()
            if not price:
                return {"error": "Failed to get current price"}
        
        # Calculate position size
        qty = self.calculate_position_size(usdt_amount, price)
        if not qty:
            return {"error": "Failed to calculate position size"}
        
        # Calculate TP/SL
        tp_price, sl_price = self.calculate_tp_sl_prices(side, price)
        
        # Place order
        result = self.place_order(side, qty, sl_price, tp_price)
        
        if "error" not in result:
            result["qty"] = qty
            result["entry_price"] = price
            result["tp_price"] = tp_price
            result["sl_price"] = sl_price
        
        return result
    
    def reverse_position(self, current_qty, current_side, usdt_amount):
        """Reverse position using 2x quantity method (your exact method)"""
        reverse_side = "Sell" if current_side == "Buy" else "Buy"
        
        # Calculate new quantity based on USDT amount
        current_price = self.get_price()
        if not current_price:
            return {"error": "Failed to get current price"}
        
        new_qty = self.calculate_position_size(usdt_amount, current_price)
        if not new_qty:
            return {"error": "Failed to calculate new position size"}
        
        # Use 2x quantity for reversal (your method)
        reverse_qty = new_qty * 2
        
        # Calculate TP/SL for reverse direction
        tp_price, sl_price = self.calculate_tp_sl_prices(reverse_side, current_price)
        
        print(f"🟡 Reversing: {current_side} -> {reverse_side} | Qty: {reverse_qty} | Entry: ${current_price:.4f}")
        
        try:
            return self.client.place_order(
                category="linear",
                symbol=self.symbol,
                side=reverse_side,
                orderType="Market",
                qty=str(reverse_qty),
                timeInForce="IOC",
                takeProfit=str(round(tp_price, 2)),
                stopLoss=str(round(sl_price, 2)),
                tpOrderType="Market",
                slOrderType="Market",
                tpslMode="Full",
                positionIdx=0
            )
        except Exception as e:
            return {"error": str(e)}
    
    def get_position_info(self):
        """Get current position (your exact method)"""
        try:
            res = self.client.get_positions(category="linear", symbol=self.symbol)
            if res["retCode"] != 0:
                print("🔴 Error fetching position:", res)
                return None
            
            positions = res["result"]["list"]
            for pos in positions:
                if float(pos["size"]) > 0:  # Active position
                    return {
                        "side": pos["side"],
                        "size": float(pos["size"]),
                        "entry_price": float(pos["avgPrice"]),
                        "unrealized_pnl": float(pos["unrealisedPnl"]),
                        "mark_price": float(pos["markPrice"])
                    }
            return None
        except Exception as e:
            print(f"🔴 Position info error: {e}")
            return None
    
    def get_closed_pnl(self, limit=10):
        """Get closed P&L history (your method)"""
        try:
            response = self.client.get_closed_pnl(
                category="linear",
                symbol=self.symbol,
                limit=limit
            )
            return response
        except Exception as e:
            print(f"🔴 Closed P&L error: {e}")
            return {"error": str(e)}
    
    def close_position(self):
        """Close current position"""
        position = self.get_position_info()
        if not position:
            return {"error": "No position to close"}
        
        # Close position by placing opposite order
        close_side = "Sell" if position["side"] == "Buy" else "Buy"
        
        try:
            return self.client.place_order(
                category="linear",
                symbol=self.symbol,
                side=close_side,
                orderType="Market",
                qty=str(position["size"]),
                timeInForce="IOC",
                positionIdx=0
            )
        except Exception as e:
            return {"error": str(e)}
    
    def get_account_balance(self):
        """Get USDT balance"""
        try:
            res = self.client.get_wallet_balance(accountType="UNIFIED")
            if res["retCode"] == 0:
                for coin in res["result"]["list"][0]["coin"]:
                    if coin["coin"] == "USDT":
                        return {
                            "balance": float(coin["walletBalance"]),
                            "available": float(coin["availableToWithdraw"])
                        }
            return None
        except Exception as e:
            print(f"🔴 Balance fetch error: {e}")
            return None