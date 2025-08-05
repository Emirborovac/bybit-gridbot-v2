#!/usr/bin/env python3
"""
State Manager - Persistent state backup for crash recovery
Simple JSON-based state persistence
"""

import json
import os
from datetime import datetime
from threading import Lock

class StateManager:
    def __init__(self, state_file="data/bot_state.json"):
        self.state_file = state_file
        self.lock = Lock()
        self.state = {}
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        # Load existing state if available
        self.load_state()
    
    def load_state(self):
        """Load state from JSON file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                print(f"🟢 State loaded from {self.state_file}")
            else:
                self.state = {}
                print("🟡 No previous state found, starting fresh")
        except Exception as e:
            print(f"🔴 State load error: {e}")
            self.state = {}
    
    def save_state(self, update_data=None):
        """Save current state to JSON file"""
        try:
            with self.lock:
                if update_data:
                    self.state.update(update_data)
                
                # Add timestamp
                self.state['last_updated'] = datetime.now().isoformat()
                
                # Write to temporary file first, then rename (atomic operation)
                temp_file = self.state_file + '.tmp'
                with open(temp_file, 'w') as f:
                    json.dump(self.state, f, indent=2)
                
                # Atomic rename
                os.rename(temp_file, self.state_file)
                
        except Exception as e:
            print(f"🔴 State save error: {e}")
    
    def get_state(self, key=None):
        """Get state value by key, or entire state if no key"""
        with self.lock:
            if key:
                return self.state.get(key)
            return self.state.copy()
    
    def update_position(self, position_data):
        """Update position information in state"""
        position_update = {
            'current_position': position_data,
            'position_updated': datetime.now().isoformat()
        }
        self.save_state(position_update)
    
    def update_grid_level(self, grid_level):
        """Update current grid level"""
        grid_update = {
            'current_grid_level': grid_level,
            'grid_updated': datetime.now().isoformat()
        }
        self.save_state(grid_update)
    
    def update_pnl(self, pnl_data):
        """Update P&L tracking"""
        pnl_update = {
            'daily_pnl': pnl_data.get('daily_pnl', 0),
            'total_trades': pnl_data.get('total_trades', 0),
            'accumulated_losses': pnl_data.get('accumulated_losses', 0),
            'pnl_updated': datetime.now().isoformat()
        }
        self.save_state(pnl_update)
    
    def clear_state(self):
        """Clear all state data"""
        try:
            with self.lock:
                self.state = {}
                if os.path.exists(self.state_file):
                    os.remove(self.state_file)
                print("🟢 State cleared")
        except Exception as e:
            print(f"🔴 State clear error: {e}")
    
    def backup_state(self):
        """Create timestamped backup of current state"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"data/bot_state_backup_{timestamp}.json"
            
            with open(backup_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            print(f"🟢 State backed up to {backup_file}")
            return backup_file
        except Exception as e:
            print(f"🔴 State backup error: {e}")
            return None
    
    def get_recovery_info(self):
        """Get information needed for crash recovery"""
        recovery_info = {
            'has_position': self.state.get('current_position') is not None,
            'position': self.state.get('current_position'),
            'grid_level': self.state.get('current_grid_level'),
            'last_updated': self.state.get('last_updated'),
            'accumulated_losses': self.state.get('accumulated_losses', 0)
        }
        return recovery_info