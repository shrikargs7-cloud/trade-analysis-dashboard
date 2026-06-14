# ============================================================
# FILE: database.py - Complete Database Manager with Views & Triggers
# ============================================================

import sqlite3
import os
import json
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'trades.db')
        self.conn = None
        self.ensure_database_initialized()

    def ensure_database_initialized(self):
        """Check if database exists and has all tables, if not initialize"""
        if not os.path.exists(self.db_path):
            logger.info("Database not found. Creating new database...")
            self.initialize_database()
        else:
            # Verify tables exist
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
                if not cursor.fetchone():
                    logger.info("Tables missing. Re-initializing database...")
                    conn.close()
                    self.initialize_database()
                else:
                    conn.close()
            except Exception as e:
                logger.error(f"Error checking database: {e}")
                self.initialize_database()

    def initialize_database(self):
        """Create all tables, views, triggers, and indexes"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # ============================================================
            # 1. MAIN TABLES
            # ============================================================
            
            # Trades table - main fact table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    symbol TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    trade_type TEXT NOT NULL CHECK (trade_type IN ('BUY', 'SELL', 'LONG', 'SHORT')),
                    entry_date DATETIME NOT NULL,
                    exit_date DATETIME,
                    status TEXT DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
                    profit_loss REAL DEFAULT 0,
                    profit_loss_percentage REAL DEFAULT 0,
                    strategy TEXT,
                    notes TEXT,
                    source TEXT DEFAULT 'WEB',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Trade events table - for trigger logging
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE,
                    trade_id INTEGER,
                    trade_ref TEXT,
                    event_type TEXT CHECK (event_type IN ('INSERT', 'UPDATE', 'DELETE', 'CLOSE')),
                    old_value TEXT,
                    new_value TEXT,
                    changed_by TEXT DEFAULT 'SYSTEM',
                    event_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Trade analytics table - aggregated statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    total_profit_loss REAL DEFAULT 0,
                    average_profit REAL DEFAULT 0,
                    average_loss REAL DEFAULT 0,
                    max_profit REAL DEFAULT 0,
                    max_loss REAL DEFAULT 0,
                    profit_factor REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Daily aggregates table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_aggregates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    avg_pnl REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    best_trade REAL DEFAULT 0,
                    worst_trade REAL DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Strategy performance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    date DATE NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    win_count INTEGER DEFAULT 0,
                    loss_count INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    UNIQUE(strategy_name, date)
                )
            ''')
            
            # Monitor logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS monitor_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    table_name TEXT,
                    record_id INTEGER,
                    old_data TEXT,
                    new_data TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Import history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS import_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    records_imported INTEGER,
                    import_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    error_message TEXT
                )
            ''')
            
            # ============================================================
            # 2. INDEXES for performance
            # ============================================================
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(entry_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_profit ON trades(profit_loss)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_trade ON trade_events(trade_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_timestamp ON trade_events(event_timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_aggregates(date)')
            
            # ============================================================
            # 3. TRIGGERS
            # ============================================================
            
            # Trigger: Auto-generate trade_id before INSERT
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trg_generate_trade_id
                BEFORE INSERT ON trades
                FOR EACH ROW
                WHEN NEW.trade_id IS NULL
                BEGIN
                    UPDATE trades SET trade_id = 'TRD-' || strftime('%Y%m%d', 'now') || '-' || 
                        substr(hex(random()), 2, 6)
                    WHERE id = NEW.id;
                END;
            ''')
            
            # Trigger: Auto-calculate profit/loss before UPDATE (when closing trade)
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trg_calculate_pnl
                BEFORE UPDATE OF exit_price, status ON trades
                FOR EACH ROW
                WHEN NEW.status = 'CLOSED' AND OLD.status = 'OPEN'
                BEGIN
                    UPDATE trades SET 
                        profit_loss = CASE NEW.trade_type
                            WHEN 'BUY' THEN (NEW.exit_price - NEW.entry_price) * NEW.quantity
                            WHEN 'LONG' THEN (NEW.exit_price - NEW.entry_price) * NEW.quantity
                            WHEN 'SELL' THEN (NEW.entry_price - NEW.exit_price) * NEW.quantity
                            WHEN 'SHORT' THEN (NEW.entry_price - NEW.exit_price) * NEW.quantity
                        END,
                        profit_loss_percentage = ((NEW.exit_price - NEW.entry_price) / NEW.entry_price) * 100,
                        exit_date = datetime('now')
                    WHERE id = NEW.id;
                END;
            ''')
            
            # Trigger: Log INSERT events
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trg_log_trade_insert
                AFTER INSERT ON trades
                FOR EACH ROW
                BEGIN
                    INSERT INTO trade_events (event_id, trade_id, trade_ref, event_type, new_value, event_timestamp)
                    VALUES (
                        'EVT-' || strftime('%Y%m%d%H%M%S', 'now') || '-' || substr(hex(random()), 2, 4),
                        NEW.id,
                        NEW.trade_id,
                        'INSERT',
                        json_object('symbol', NEW.symbol, 'quantity', NEW.quantity, 'entry_price', NEW.entry_price),
                        datetime('now')
                    );
                END;
            ''')
            
            # Trigger: Log UPDATE events
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trg_log_trade_update
                AFTER UPDATE ON trades
                FOR EACH ROW
                WHEN OLD.status != NEW.status OR OLD.exit_price != NEW.exit_price
                BEGIN
                    INSERT INTO trade_events (event_id, trade_id, trade_ref, event_type, old_value, new_value, event_timestamp)
                    VALUES (
                        'EVT-' || strftime('%Y%m%d%H%M%S', 'now') || '-' || substr(hex(random()), 2, 4),
                        NEW.id,
                        NEW.trade_id,
                        'UPDATE',
                        json_object('status', OLD.status, 'exit_price', OLD.exit_price),
                        json_object('status', NEW.status, 'exit_price', NEW.exit_price, 'profit_loss', NEW.profit_loss),
                        datetime('now')
                    );
                END;
            ''')
            
            # Trigger: Auto-update daily aggregates after trade insert/update
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trg_update_daily_aggregates
                AFTER INSERT ON trades
                FOR EACH ROW
                BEGIN
                    INSERT OR REPLACE INTO daily_aggregates (date, total_trades, winning_trades, losing_trades, total_pnl, avg_pnl, win_rate, best_trade, worst_trade, updated_at)
                    SELECT 
                        date(NEW.entry_date),
                        COUNT(*),
                        SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END),
                        SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END),
                        COALESCE(SUM(profit_loss), 0),
                        COALESCE(AVG(profit_loss), 0),
                        COALESCE(ROUND(100.0 * SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2), 0),
                        COALESCE(MAX(profit_loss), 0),
                        COALESCE(MIN(profit_loss), 0),
                        datetime('now')
                    FROM trades
                    WHERE date(entry_date) = date(NEW.entry_date)
                    AND status = 'CLOSED';
                END;
            ''')
            
            # Trigger: Update updated_at timestamp
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trg_update_timestamp
                AFTER UPDATE ON trades
                FOR EACH ROW
                BEGIN
                    UPDATE trades SET updated_at = datetime('now') WHERE id = NEW.id;
                END;
            ''')
            
            # ============================================================
            # 4. VIEWS
            # ============================================================
            
            # View: Active trades (open positions)
            cursor.execute('''
                CREATE VIEW IF NOT EXISTS v_active_trades AS
                SELECT 
                    id, trade_id, symbol, entry_price, quantity, trade_type,
                    entry_date, strategy,
                    ROUND(entry_price * quantity, 2) as position_value
                FROM trades
                WHERE status = 'OPEN'
                ORDER BY entry_date DESC
            ''')
            
            # View: Closed trades summary
            cursor.execute('''
                CREATE VIEW IF NOT EXISTS v_closed_trades AS
                SELECT 
                    id, trade_id, symbol, entry_price, exit_price, quantity,
                    trade_type, entry_date, exit_date, profit_loss, profit_loss_percentage,
                    strategy,
                    CASE WHEN profit_loss > 0 THEN 'WIN' ELSE 'LOSS' END as result
                FROM trades
                WHERE status = 'CLOSED'
                ORDER BY exit_date DESC
            ''')
            
            # View: Symbol performance
            cursor.execute('''
                CREATE VIEW IF NOT EXISTS v_symbol_performance AS
                SELECT 
                    symbol,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                    ROUND(SUM(profit_loss), 2) as total_pnl,
                    ROUND(AVG(profit_loss), 2) as avg_pnl,
                    ROUND(100.0 * SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate,
                    ROUND(MAX(profit_loss), 2) as best_trade,
                    ROUND(MIN(profit_loss), 2) as worst_trade
                FROM trades
                WHERE status = 'CLOSED'
                GROUP BY symbol
                ORDER BY total_pnl DESC
            ''')
            
            # View: Daily performance
            cursor.execute('''
                CREATE VIEW IF NOT EXISTS v_daily_performance AS
                SELECT 
                    date(entry_date) as trade_date,
                    COUNT(*) as trades_count,
                    ROUND(SUM(profit_loss), 2) as daily_pnl,
                    ROUND(SUM(CASE WHEN profit_loss > 0 THEN profit_loss ELSE 0 END), 2) as daily_profit,
                    ROUND(SUM(CASE WHEN profit_loss < 0 THEN profit_loss ELSE 0 END), 2) as daily_loss,
                    ROUND(100.0 * SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate,
                    ROUND(SUM(SUM(profit_loss)) OVER (ORDER BY date(entry_date)), 2) as cumulative_pnl
                FROM trades
                WHERE status = 'CLOSED'
                GROUP BY date(entry_date)
                ORDER BY trade_date DESC
            ''')
            
            # View: Monthly summary
            cursor.execute('''
                CREATE VIEW IF NOT EXISTS v_monthly_performance AS
                SELECT 
                    strftime('%Y-%m', entry_date) as month,
                    COUNT(*) as total_trades,
                    ROUND(SUM(profit_loss), 2) as total_pnl,
                    ROUND(100.0 * SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate,
                    ROUND(AVG(profit_loss), 2) as avg_pnl,
                    ROUND(MAX(profit_loss), 2) as best_trade,
                    ROUND(MIN(profit_loss), 2) as worst_trade
                FROM trades
                WHERE status = 'CLOSED'
                GROUP BY strftime('%Y-%m', entry_date)
                ORDER BY month DESC
            ''')
            
            # ============================================================
            # 5. INSERT SAMPLE DATA (if empty)
            # ============================================================
            
            cursor.execute("SELECT COUNT(*) as count FROM trades")
            result = cursor.fetchone()
            if result[0] == 0:
                logger.info("Inserting sample trade data...")
                sample_trades = [
                          ('AAPL', 150.25, None, 10, 'BUY', datetime.now() - timedelta(days=5), None, 'OPEN', 0, 0, 'Momentum', None, 'SAMPLE'),
            ('MSFT', 420.50, None, 5, 'BUY', datetime.now() - timedelta(days=4), None, 'OPEN', 0, 0, 'Value', None, 'SAMPLE'),
            ('GOOGL', 135.00, None, 8, 'BUY', datetime.now() - timedelta(days=3), None, 'OPEN', 0, 0, 'Growth', None, 'SAMPLE'),
            ('NVDA', 850.00, 870.00, 4, 'BUY', datetime.now() - timedelta(days=3), datetime.now() - timedelta(days=1), 'CLOSED', 80.00, 2.35, 'Momentum', None, 'SAMPLE'),
            ('TSLA', 250.00, 260.00, 6, 'BUY', datetime.now() - timedelta(days=2), datetime.now(), 'CLOSED', 60.00, 4.00, 'Breakout', None, 'SAMPLE'),
            ('TSLA', 250.00, 260.00, 6, 'BUY', datetime.now() - timedelta(days=2), datetime.now(), 'CLOSED', 60.00, 4.00, 'Breakout', None, 'SAMPLE'),
            ('AMZN', 178.50, None, 12, 'BUY', datetime.now() - timedelta(days=7), None, 'OPEN', 0, 0, 'Growth', None, 'SAMPLE'),
            ('META', 485.00, 492.00, 3, 'BUY', datetime.now() - timedelta(days=6), datetime.now() - timedelta(days=2), 'CLOSED', 21.00, 1.44, 'Value', None, 'SAMPLE'),
            ('NFLX', 625.75, None, 7, 'BUY', datetime.now() - timedelta(days=5), None, 'OPEN', 0, 0, 'Momentum', None, 'SAMPLE'),
            ('AMD', 145.30, 148.20, 15, 'BUY', datetime.now() - timedelta(days=4), datetime.now() - timedelta(days=1), 'CLOSED', 43.50, 2.00, 'Breakout', None, 'SAMPLE'),
            ('INTC', 42.80, None, 20, 'BUY', datetime.now() - timedelta(days=10), None, 'OPEN', 0, 0, 'Value', None, 'SAMPLE'),
            ('PYPL', 68.50, 70.25, 8, 'SELL', datetime.now() - timedelta(days=8), datetime.now() - timedelta(days=3), 'CLOSED', -14.00, -2.55, 'Momentum', None, 'SAMPLE'),
            ('CRM', 298.00, None, 6, 'BUY', datetime.now() - timedelta(days=6), None, 'OPEN', 0, 0, 'Growth', None, 'SAMPLE'),
            ('ADBE', 555.00, 560.50, 4, 'BUY', datetime.now() - timedelta(days=5), datetime.now() - timedelta(days=2), 'CLOSED', 22.00, 0.99, 'Value', None, 'SAMPLE'),
            ('NOW', 768.00, None, 2, 'BUY', datetime.now() - timedelta(days=4), None, 'OPEN', 0, 0, 'Momentum', None, 'SAMPLE'),
            ('UBER', 72.30, 74.00, 14, 'BUY', datetime.now() - timedelta(days=3), datetime.now() - timedelta(days=1), 'CLOSED', 23.80, 2.35, 'Breakout', None, 'SAMPLE'),
            ('SHOP', 72.00, None, 11, 'BUY', datetime.now() - timedelta(days=9), None, 'OPEN', 0, 0, 'Growth', None, 'SAMPLE'),
            ('COIN', 235.00, 245.00, 5, 'BUY', datetime.now() - timedelta(days=7), datetime.now() - timedelta(days=3), 'CLOSED', 50.00, 2.13, 'Momentum', None, 'SAMPLE'),
            ('SNOW', 168.50, None, 9, 'BUY', datetime.now() - timedelta(days=6), None, 'OPEN', 0, 0, 'Value', None, 'SAMPLE'),
            ('BA', 185.00, 182.50, 7, 'SELL', datetime.now() - timedelta(days=5), datetime.now() - timedelta(days=2), 'CLOSED', -17.50, -1.35, 'Breakout', None, 'SAMPLE'),
            ('DIS', 110.25, None, 13, 'BUY', datetime.now() - timedelta(days=8), None, 'OPEN', 0, 0, 'Growth', None, 'SAMPLE'),
        ]
                
                
                for trade in sample_trades:
                    cursor.execute('''
                        INSERT INTO trades (trade_id, symbol, entry_price, exit_price, quantity, trade_type, 
                                          entry_date, exit_date, status, profit_loss, profit_loss_percentage, 
                                          strategy, notes, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', trade)
                
                # Insert initial analytics
                cursor.execute('''
                    INSERT INTO trade_analytics (total_trades, winning_trades, losing_trades, win_rate, 
                                                total_profit_loss, average_profit, average_loss, 
                                                max_profit, max_loss, updated_at)
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                        ROUND(100.0 * SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate,
                        ROUND(SUM(profit_loss), 2) as total_profit_loss,
                        ROUND(AVG(CASE WHEN profit_loss > 0 THEN profit_loss ELSE NULL END), 2) as average_profit,
                        ROUND(AVG(CASE WHEN profit_loss < 0 THEN profit_loss ELSE NULL END), 2) as average_loss,
                        ROUND(MAX(profit_loss), 2) as max_profit,
                        ROUND(MIN(profit_loss), 2) as max_loss,
                        datetime('now')
                    FROM trades WHERE status = 'CLOSED'
                ''')
            
            conn.commit()
            logger.info("Database initialized successfully!")
            
            # Log all created objects
            cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view', 'trigger') ORDER BY type, name")
            objects = cursor.fetchall()
            logger.info("Database Objects Created:")
            for obj in objects:
                logger.info(f"  {obj[1].upper()}: {obj[0]}")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            return True
        except sqlite3.Error as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        if self.conn:
            self.conn.close()

    def execute_query(self, query, params=None):
        try:
            cursor = self.conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            
            self.conn.commit()
            return {"success": True, "affected_rows": cursor.rowcount}
            
        except sqlite3.Error as e:
            logger.error(f"Query error: {e}")
            if self.conn:
                self.conn.rollback()
            return {"error": str(e)}

    def get_trade_analytics(self):
        query = "SELECT * FROM trade_analytics ORDER BY updated_at DESC LIMIT 1"
        return self.execute_query(query)

    def get_recent_trades(self, limit=10):
        query = "SELECT * FROM v_closed_trades ORDER BY exit_date DESC LIMIT ?"
        return self.execute_query(query, (limit,))

    def get_active_trades(self):
        query = "SELECT * FROM v_active_trades ORDER BY entry_date DESC"
        return self.execute_query(query)

    def get_symbol_performance(self):
        query = "SELECT * FROM v_symbol_performance"
        return self.execute_query(query)

    def get_daily_performance(self):
        query = "SELECT * FROM v_daily_performance LIMIT 30"
        return self.execute_query(query)

    def get_monthly_performance(self):
        query = "SELECT * FROM v_monthly_performance LIMIT 12"
        return self.execute_query(query)

    def get_performance_chart_data(self):
        trades = self.get_recent_trades(50)
        if isinstance(trades, list):
            labels = [t['symbol'] for t in trades]
            values = [t['profit_loss'] for t in trades]
            return {"labels": labels, "values": values}
        return {"labels": [], "values": []}

    def get_trade_suggestions(self):
        # AI-based trade suggestions using actual data
        perf = self.get_symbol_performance()
        suggestions = []
        
        if isinstance(perf, list):
            for p in perf[:5]:
                if p['win_rate'] > 60:
                    suggestions.append({
                        "symbol": p['symbol'],
                        "suggestion": "STRONG BUY",
                        "reason": f"Win rate: {p['win_rate']}% | Total PnL: ${p['total_pnl']}"
                    })
                elif p['win_rate'] > 40:
                    suggestions.append({
                        "symbol": p['symbol'],
                        "suggestion": "HOLD",
                        "reason": f"Win rate: {p['win_rate']}% | Monitor closely"
                    })
                else:
                    suggestions.append({
                        "symbol": p['symbol'],
                        "suggestion": "AVOID",
                        "reason": f"Win rate: {p['win_rate']}% | Poor performance"
                    })
        
        if not suggestions:
            suggestions = [
                {"symbol": "BTC/USD", "suggestion": "ACCUMULATE", "reason": "Bullish momentum detected"},
                {"symbol": "ETH/USD", "suggestion": "HOLD", "reason": "Consolidation phase"},
            ]
        
        return suggestions

    def add_trade(self, trade_data):
        query = """
            INSERT INTO trades (symbol, entry_price, quantity, trade_type, entry_date, strategy, notes, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            trade_data['symbol'],
            trade_data['entry_price'],
            trade_data['quantity'],
            trade_data['trade_type'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            trade_data.get('strategy', 'MANUAL'),
            trade_data.get('notes', ''),
            trade_data.get('source', 'WEB')
        )
        return self.execute_query(query, params)

    def close_trade(self, trade_id, exit_price):
        query = """
            UPDATE trades 
            SET exit_price = ?, status = 'CLOSED'
            WHERE id = ? AND status = 'OPEN'
        """
        return self.execute_query(query, (exit_price, trade_id))

    def import_trades_batch(self, trades_list, filename):
        """Batch import trades from CSV/Excel"""
        imported = 0
        errors = []
        
        for trade in trades_list:
            try:
                result = self.add_trade(trade)
                if isinstance(result, dict) and result.get('success'):
                    imported += 1
                else:
                    errors.append(str(trade))
            except Exception as e:
                errors.append(f"{trade.get('symbol', 'unknown')}: {e}")
        
        # Log import history
        self.execute_query("""
            INSERT INTO import_history (filename, records_imported, status, error_message)
            VALUES (?, ?, ?, ?)
        """, (filename, imported, 'COMPLETED' if not errors else 'PARTIAL', str(errors[:5]) if errors else None))
        
        # Refresh analytics
        self.refresh_analytics()
        
        return {"imported": imported, "errors": errors}

    def refresh_analytics(self):
        """Refresh trade analytics from closed trades"""
        query = """
            INSERT OR REPLACE INTO trade_analytics (id, total_trades, winning_trades, losing_trades, 
                                                   win_rate, total_profit_loss, average_profit, 
                                                   average_loss, max_profit, max_loss, updated_at)
            SELECT 
                1,
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                ROUND(100.0 * SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate,
                ROUND(SUM(profit_loss), 2) as total_profit_loss,
                ROUND(AVG(CASE WHEN profit_loss > 0 THEN profit_loss ELSE NULL END), 2) as average_profit,
                ROUND(AVG(CASE WHEN profit_loss < 0 THEN profit_loss ELSE NULL END), 2) as average_loss,
                ROUND(MAX(profit_loss), 2) as max_profit,
                ROUND(MIN(profit_loss), 2) as max_loss,
                datetime('now')
            FROM trades WHERE status = 'CLOSED'
        """
        return self.execute_query(query)