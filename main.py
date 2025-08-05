#!/usr/bin/env python3
"""
ByBit Grid Bot v5 - Main Orchestrator with Enhanced Grid Detection
Built on proven API methods + SQLite tracking + Universal P&L detection
ENHANCED: Bulletproof grid crossing detection + Faster monitoring
"""

import json
import time
import os
import signal
import sys
import sqlite3
from decimal import Decimal, ROUND_DOWN, getcontext
from pybit.unified_trading import HTTP, WebSocket
from dotenv import load_dotenv
from datetime import datetime

getcontext().prec = 18
load_dotenv()

class GridBot:
    def __init__(self):
        # Load credentials (your proven method)
        self.api_key = os.getenv("BYBIT_API_KEY")
        self.api_secret = os.getenv("BYBIT_SECRET_KEY")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("🔴 BYBIT_API_KEY and BYBIT_SECRET_KEY must be set")
        
        # Initialize HTTP client (your exact setup)
        self.client = HTTP(api_key=self.api_key, api_secret=self.api_secret)
        
        # Load config
        self.config = self.load_config()
        self.symbol = self.config["SYMBOL"]
        self.leverage = self.config["LEVERAGE"]
        self.base_usdt = self.config["USDT"]
        self.grid_levels = sorted(self.config["GRID_LEVELS"])
        self.sl_roe = self.config["SL"]["ROE"]
        self.tp_roe = self.config["TP"]["ROE"]
        
        # Trading state (RUNTIME MEMORY)
        self.current_position = None
        self.current_grid_level = None
        self.last_price = None
        self.running = False
        
        # P&L tracking (RUNTIME MEMORY) - NEW
        self.accumulated_losses = 0.0
        self.daily_pnl = 0.0
        self.total_trades = 0
        
        # NEW: Order ID tracking for comprehensive P&L detection
        self.current_order_id = None
        self.processed_order_ids = set()
        self.loop_count = 0
        
        # ENHANCED: Grid zone tracking for bulletproof detection
        self.last_grid_zone = None
        
        # Initialize SQLite database - NEW
        self.init_database()
        self.load_previous_state()
        
        # Get instrument info (your proven method)
        self.instrument_info = self.get_instrument_info()
        if not self.instrument_info:
            raise ValueError("🔴 Failed to fetch instrument info")
        
        self.qty_step = float(self.instrument_info["lotSizeFilter"]["qtyStep"])
        self.min_qty = float(self.instrument_info["lotSizeFilter"]["minOrderQty"])
        
        print(f"🟢 Grid Bot v5 Ready - {self.symbol} | {len(self.grid_levels)} levels")
        if self.accumulated_losses > 0:
            print(f"🟡 Accumulated losses loaded: ${self.accumulated_losses:.2f}")
    
    def calculate_exact_pnl_with_buffer(self, entry_price, exit_price, size, side):
        """Calculate exact P&L with fees + 3% safety buffer - LIGHTNING FAST"""
        
        # Raw P&L calculation
        if side == "Buy":
            raw_pnl = (exit_price - entry_price) * size
        else:  # Sell
            raw_pnl = (entry_price - exit_price) * size
        
        # ByBit fees: 0.055% entry + 0.055% exit
        entry_fee = (size * entry_price) * 0.00055
        exit_fee = (size * exit_price) * 0.00055
        total_fees = entry_fee + exit_fee
        
        # P&L after fees
        pnl_after_fees = raw_pnl - total_fees
        
        # Add 3% safety buffer (ONLY for losses)
        if pnl_after_fees < 0:
            safety_buffer = abs(pnl_after_fees) * 0.03
            final_pnl = pnl_after_fees - safety_buffer
        else:
            final_pnl = pnl_after_fees  # No buffer on profits
        
        return final_pnl
    
    def get_grid_zone(self, price):
        """Get which grid zone the price is in - ENHANCED"""
        for i, level in enumerate(self.grid_levels):
            if price <= level:
                return i
        return len(self.grid_levels)  # Above all levels
    
    def check_grid_crossing(self, current_price):
        """Enhanced grid crossing with zone-based detection - BULLETPROOF"""
        if not self.last_price:
            self.last_price = current_price
            # Initialize grid zone
            self.last_grid_zone = self.get_grid_zone(current_price)
            return None
        
        # Check current grid zone
        current_zone = self.get_grid_zone(current_price)
        
        # If we changed zones, we crossed a grid level
        if self.last_grid_zone is not None and current_zone != self.last_grid_zone:
            # Find which level was crossed
            if current_price > self.last_price:
                # Moving up - find levels between last_price and current_price
                crossed_levels = [level for level in self.grid_levels 
                                if self.last_price < level <= current_price]
            else:
                # Moving down - find levels between last_price and current_price
                crossed_levels = [level for level in self.grid_levels 
                                if current_price <= level < self.last_price]
            
            self.last_price = current_price
            self.last_grid_zone = current_zone
            
            if crossed_levels:
                return crossed_levels[0]  # Return first crossed level
        
        # Update tracking even if no crossing
        self.last_price = current_price
        self.last_grid_zone = current_zone
        return None
    
    def detect_position_closure(self):
        """Universal position closure detection"""
        if not self.current_position:
            return False
            
        # Check if our tracked position still exists
        api_position = self.get_position_info()
        
        # Position closed if we think we have one but API shows none
        if self.current_position and not api_position:
            return True
        return False
    
    def monitor_position_status(self):
        """Monitor for ANY position closure (TP/SL/Manual) - UNIVERSAL"""
        if not self.current_position:
            return
        
        # Check if position was closed
        if self.detect_position_closure():
            # Get current price for calculation
            current_price = self.get_price()
            if not current_price:
                return
            
            # Calculate exact P&L using our lightning-fast method
            calculated_pnl = self.calculate_exact_pnl_with_buffer(
                entry_price=self.current_position["entry_price"],
                exit_price=current_price,
                size=self.current_position["size"],
                side=self.current_position["side"]
            )
            
            # Determine closure type for logging
            if calculated_pnl > 0:
                closure_type = "Take Profit"
                print(f"🟢 {closure_type} | P&L: ${calculated_pnl:.2f}")
            else:
                closure_type = "Stop Loss"
                print(f"🔴 {closure_type} | P&L: ${calculated_pnl:.2f}")
            
            # Update P&L tracking
            self.update_pnl_tracking(calculated_pnl)
            
            # Log to database
            self.log_trade(
                side=f"{self.current_position['side']}-CLOSED",
                grid_level=self.current_grid_level or 0,
                usdt_amount=0,  # No new position opened
                pnl=calculated_pnl
            )
            
            # Clear position state
            self.current_position = None
            self.current_grid_level = None
            self.current_order_id = None
    
    def init_database(self):
        """Initialize SQLite database - NEW"""
        try:
            os.makedirs("data", exist_ok=True)
            self.db_path = "data/gridbot.db"
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            
            # Create tables
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_state (
                    id INTEGER PRIMARY KEY,
                    accumulated_losses REAL DEFAULT 0,
                    daily_pnl REAL DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    current_grid_level REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    side TEXT,
                    grid_level REAL,
                    usdt_amount REAL,
                    pnl REAL,
                    accumulated_losses_after REAL
                )
            """)
            
            # Initialize state if empty
            cursor = self.conn.execute("SELECT COUNT(*) FROM bot_state")
            if cursor.fetchone()[0] == 0:
                self.conn.execute("INSERT INTO bot_state (id) VALUES (1)")
            
            self.conn.commit()
            
        except Exception as e:
            print(f"🔴 Database init error: {e}")
            # Fallback to no database
            self.conn = None
    
    def load_previous_state(self):
        """Load previous state from database - NEW"""
        try:
            if not self.conn:
                return
                
            cursor = self.conn.execute("""
                SELECT accumulated_losses, daily_pnl, total_trades, current_grid_level 
                FROM bot_state WHERE id = 1
            """)
            result = cursor.fetchone()
            
            if result:
                self.accumulated_losses = result[0] or 0.0
                self.daily_pnl = result[1] or 0.0
                self.total_trades = result[2] or 0
                self.current_grid_level = result[3]
                
                if self.accumulated_losses > 0 or self.total_trades > 0:
                    print(f"🟢 State loaded - Losses: ${self.accumulated_losses:.2f} | Trades: {self.total_trades}")
                    
        except Exception as e:
            print(f"🔴 State load error: {e}")
    
    def save_state(self):
        """Save current state to database - NEW"""
        try:
            if not self.conn:
                return
                
            self.conn.execute("""
                UPDATE bot_state SET 
                    accumulated_losses = ?,
                    daily_pnl = ?,
                    total_trades = ?,
                    current_grid_level = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (self.accumulated_losses, self.daily_pnl, self.total_trades, self.current_grid_level))
            
            self.conn.commit()
            
        except Exception as e:
            print(f"🔴 State save error: {e}")
    
    def log_trade(self, side, grid_level, usdt_amount, pnl):
        """Log trade to database - NEW"""
        try:
            if not self.conn:
                return
                
            self.conn.execute("""
                INSERT INTO trades (side, grid_level, usdt_amount, pnl, accumulated_losses_after)
                VALUES (?, ?, ?, ?, ?)
            """, (side, grid_level, usdt_amount, pnl, self.accumulated_losses))
            
            self.conn.commit()
            
        except Exception as e:
            print(f"🔴 Trade log error: {e}")
    
    def update_pnl_tracking(self, trade_pnl):
        """Update P&L tracking in memory - NEW"""
        self.daily_pnl += trade_pnl
        self.total_trades += 1
        
        # Proper loss accumulation
        if trade_pnl < 0:
            self.accumulated_losses += abs(trade_pnl)
        else:
            # Profit reduces accumulated losses
            if self.accumulated_losses > 0:
                recovered = min(self.accumulated_losses, trade_pnl)
                self.accumulated_losses = max(0, self.accumulated_losses - trade_pnl)
                if recovered > 0:
                    print(f"🟢 Loss recovery: ${recovered:.2f} | Remaining: ${self.accumulated_losses:.2f}")
        
        # Save to database
        self.save_state()
    
    def calculate_position_size_with_recovery(self):
        """Calculate position size including accumulated losses - NEW"""
        return self.base_usdt + self.accumulated_losses
    
    def load_config(self):
        """Load config (your method)"""
        try:
            with open("config.json", "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"🔴 Config error: {e}")
            sys.exit(1)
    
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
                        "unrealized_pnl": float(pos["unrealisedPnl"])
                    }
            return None
        except Exception as e:
            print(f"🔴 Position info error: {e}")
            return None
    
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
    
    def reverse_position(self, current_qty, current_side, sl_roe, tp_roe, leverage):
        """Reverse position (your exact method with modifications)"""
        reverse_side = "Sell" if current_side == "Buy" else "Buy"
        reverse_qty = current_qty * 2  # Your 2x method
        
        current_price = self.get_price()
        if not current_price:
            return {"error": "Failed to get current price"}
        
        # Calculate TP/SL (your exact logic)
        if reverse_side == "Buy":
            sl_price = current_price * (1 - sl_roe / 100 / leverage)
            tp_price = current_price * (1 + tp_roe / 100 / leverage)
        else:
            sl_price = current_price * (1 + sl_roe / 100 / leverage)
            tp_price = current_price * (1 - tp_roe / 100 / leverage)
        
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
    
    def calculate_position_size(self, usdt_amount):
        """Calculate position size (your method)"""
        price = self.get_price()
        if not price:
            return None
        
        raw_qty = (usdt_amount * self.leverage) / price
        qty = self.round_down(raw_qty, self.qty_step)
        
        if qty < self.min_qty:
            qty = self.min_qty
        
        return qty
    
    def handle_ticker(self, msg):
        """Handle price updates (your WebSocket structure)"""
        if "data" in msg and isinstance(msg["data"], dict):
            price = float(msg["data"].get("lastPrice"))
            if not price:
                return
            
            # Check for grid crossing with enhanced detection
            crossed_level = self.check_grid_crossing(price)
            if crossed_level:
                self.execute_grid_trade(price, crossed_level)
    
    def execute_grid_trade(self, price, grid_level):
        """Execute trade when grid level crossed"""
        try:
            current_pos = self.get_position_info()
            
            if current_pos:
                # We have a position - check if we should reverse
                if self.should_reverse_position(price, grid_level, current_pos):
                    self.execute_reversal(current_pos, grid_level)
            else:
                # No position - open new one
                self.open_grid_position(price, grid_level)
                
        except Exception as e:
            print(f"🔴 Trade execution error: {e}")
    
    def should_reverse_position(self, price, grid_level, position):
        """Check if we should reverse the position"""
        # Simple logic: if price crosses back through our entry grid level
        return grid_level == self.current_grid_level
    
    def open_grid_position(self, price, grid_level):
        """Open new position at grid level - UPDATED"""
        # Determine side based on grid crossing direction
        side = "Buy" if price > grid_level else "Sell"
        
        # Calculate position size with loss recovery
        usdt_amount = self.calculate_position_size_with_recovery()
        qty = self.calculate_position_size(usdt_amount)
        
        if not qty:
            print("🔴 Failed to calculate position size")
            return
        
        # Calculate TP/SL
        if side == "Buy":
            sl_price = price * (1 - self.sl_roe / 100 / self.leverage)
            tp_price = price * (1 + self.tp_roe / 100 / self.leverage)
        else:
            sl_price = price * (1 + self.sl_roe / 100 / self.leverage)
            tp_price = price * (1 - self.tp_roe / 100 / self.leverage)
        
        # Place order
        result = self.place_order(side, qty, sl_price, tp_price)
        
        if "error" not in result:
            # Capture order ID for tracking
            self.current_order_id = result.get("result", {}).get("orderId")
            
            self.current_position = {"side": side, "size": qty, "entry_price": price}
            self.current_grid_level = grid_level
            
            if usdt_amount > self.base_usdt:
                print(f"🟢 {side} @ {grid_level} | Size: ${usdt_amount:.2f} | Entry: ${price:.4f}")
            else:
                print(f"🟢 {side} @ {grid_level} | Size: ${usdt_amount:.2f} | Entry: ${price:.4f}")
            
            # Log trade
            self.log_trade(side, grid_level, usdt_amount, 0.0)  # 0 PnL for new position
        else:
            print(f"🔴 Order failed: {result.get('error', 'Unknown error')}")
    
    def execute_reversal(self, current_pos, grid_level):
        """Execute position reversal with CALCULATED P&L - LIGHTNING FAST"""
        
        # Get current price for calculation
        current_price = self.get_price()
        if not current_price:
            print("🔴 Failed to get current price for reversal")
            return
        
        # 🚀 LIGHTNING-FAST P&L calculation (no API delay!)
        calculated_pnl = self.calculate_exact_pnl_with_buffer(
            entry_price=current_pos["entry_price"],
            exit_price=current_price,
            size=current_pos["size"],
            side=current_pos["side"]
        )
        
        # Update P&L tracking FIRST
        self.update_pnl_tracking(calculated_pnl)
        
        # Calculate NEW position size with accumulated losses
        usdt_amount = self.calculate_position_size_with_recovery()
        
        # Use ACTUAL ByBit position size for reversal
        actual_position_size = current_pos["size"]
        
        # Use your reverse method with ACTUAL position size
        result = self.reverse_position(
            current_qty=actual_position_size,
            current_side=current_pos["side"],
            sl_roe=self.sl_roe,
            tp_roe=self.tp_roe,
            leverage=self.leverage
        )
        
        if "error" not in result:
            # Capture new order ID
            self.current_order_id = result.get("result", {}).get("orderId")
            
            new_side = "Sell" if current_pos["side"] == "Buy" else "Buy"
            self.current_position = {"side": new_side, "size": actual_position_size * 2, "entry_price": current_price}
            
            if calculated_pnl < 0:
                print(f"🟢 {new_side} @ {grid_level} | Size: ${usdt_amount:.2f} | Loss: ${calculated_pnl:.2f}")
            else:
                print(f"🟢 {new_side} @ {grid_level} | Size: ${usdt_amount:.2f} | Profit: ${calculated_pnl:.2f}")
            
            # Log trade with calculated P&L
            self.log_trade(new_side, grid_level, usdt_amount, calculated_pnl)
        else:
            print(f"🔴 Reversal failed: {result.get('error', 'Unknown error')}")
    
    def start(self):
        """Start the bot with enhanced monitoring - FASTER"""
        try:
            # Check for existing position
            existing_pos = self.get_position_info()
            if existing_pos:
                self.current_position = existing_pos
                print(f"🟡 Existing position: {existing_pos['side']} ${existing_pos['size']}")
            
            # Start WebSocket (your exact setup)
            ws = WebSocket(
                testnet=False,
                channel_type="linear",
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            ws.ticker_stream(
                symbol=self.symbol,
                callback=self.handle_ticker
            )
            
            print(f"🟢 Grid Bot Started - Monitoring {self.symbol}")
            self.running = True
            self.loop_count = 0
            
            # Keep running with faster monitoring
            while self.running:
                time.sleep(0.001)  # 🚀 ENHANCED: 1ms = 1000 checks/second
                self.loop_count += 1
                
                # 🚀 ENHANCED: Monitor for TP/SL closures every 500ms (2x faster)
                if self.loop_count % 500 == 0:
                    self.monitor_position_status()
                
        except Exception as e:
            print(f"🔴 Bot start error: {e}")
    
    def stop(self):
        """Stop the bot"""
        print("🟡 Stopping Grid Bot...")
        self.running = False
        
        # Save final state
        self.save_state()
        
        # Close database
        if self.conn:
            self.conn.close()

def signal_handler(signum, frame):
    print("🟡 Shutdown signal received...")
    sys.exit(0)

def main():
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        bot = GridBot()
        bot.start()
    except KeyboardInterrupt:
        print("🟢 Grid Bot stopped")
    except Exception as e:
        print(f"🔴 Fatal error: {e}")

if __name__ == "__main__":
    main()