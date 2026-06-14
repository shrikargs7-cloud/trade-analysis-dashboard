from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime, timedelta

# IMPORTANT: Set template folder to 'templates'
app = Flask(__name__, 
            template_folder='templates',  # This tells Flask where HTML files are
            static_folder='templates/static',  # For CSS/JS files
            static_url_path='/static')

CORS(app, resources={r"/*": {"origins": "*"}})

DB_PATH = os.path.join(os.path.dirname(__file__), 'trades.db')

def get_db():
    """Get database connection with proper settings"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initialize database with all tables, views, and triggers"""
    conn = get_db()
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
            event_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trade_id) REFERENCES trades(id)
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
    # 3. TRIGGERS (Fixed to work with SQLite)
    # ============================================================
    
    # Note: SQLite triggers have limitations. Simplified versions below.
    
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
    
    # Trigger: Log INSERT events (simplified)
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_log_trade_insert
        AFTER INSERT ON trades
        FOR EACH ROW
        BEGIN
            INSERT INTO trade_events (event_id, trade_id, trade_ref, event_type, new_value, event_timestamp)
            VALUES (
                'EVT-' || strftime('%Y%m%d%H%M%S', 'now') || '-' || printf('%04d', abs(random()) % 10000),
                NEW.id,
                NEW.trade_id,
                'INSERT',
                json_object('symbol', NEW.symbol, 'quantity', NEW.quantity, 'entry_price', NEW.entry_price),
                datetime('now')
            );
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
    cursor.execute('DROP VIEW IF EXISTS v_active_trades')
    cursor.execute('''
        CREATE VIEW v_active_trades AS
        SELECT 
            id, trade_id, symbol, entry_price, quantity, trade_type,
            entry_date, strategy,
            ROUND(entry_price * quantity, 2) as position_value
        FROM trades
        WHERE status = 'OPEN'
        ORDER BY entry_date DESC
    ''')
    
    # View: Closed trades summary
    cursor.execute('DROP VIEW IF EXISTS v_closed_trades')
    cursor.execute('''
        CREATE VIEW v_closed_trades AS
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
    cursor.execute('DROP VIEW IF EXISTS v_symbol_performance')
    cursor.execute('''
        CREATE VIEW v_symbol_performance AS
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
    cursor.execute('DROP VIEW IF EXISTS v_daily_performance')
    cursor.execute('''
        CREATE VIEW v_daily_performance AS
        SELECT 
            date(entry_date) as trade_date,
            COUNT(*) as trades_count,
            ROUND(SUM(profit_loss), 2) as daily_pnl,
            ROUND(SUM(CASE WHEN profit_loss > 0 THEN profit_loss ELSE 0 END), 2) as daily_profit,
            ROUND(SUM(CASE WHEN profit_loss < 0 THEN profit_loss ELSE 0 END), 2) as daily_loss,
            ROUND(100.0 * SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate
        FROM trades
        WHERE status = 'CLOSED'
        GROUP BY date(entry_date)
        ORDER BY trade_date DESC
    ''')
    
    # View: Monthly summary
    cursor.execute('DROP VIEW IF EXISTS v_monthly_performance')
    cursor.execute('''
        CREATE VIEW v_monthly_performance AS
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
        print("Inserting sample trade data...")
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
                INSERT INTO trades (symbol, entry_price, exit_price, quantity, trade_type, 
                                  entry_date, exit_date, status, profit_loss, profit_loss_percentage, 
                                  strategy, notes, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    conn.close()
    print("✅ Database initialized successfully!")
    print(f"📁 Database location: {DB_PATH}")


# Initialize database
init_db()


# ========== SERVE YOUR HTML FILE ==========
@app.route('/')
def index():
    """Serve your HTML file from templates folder"""
    try:
        # Try to render from templates folder
        return render_template('/Users/shrikar/Desktop/my_flask_app copy/venv/trade_analysis_app/templates/index.html')
    except:
        # Fallback: check if index.html exists in root
        if os.path.exists('/Users/shrikar/Desktop/my_flask_app copy/venv/trade_analysis_app/templates/index.html'):
            return send_file('/Users/shrikar/Desktop/my_flask_app copy/venv/trade_analysis_app/templates/index.html')
        return jsonify({
            "error": "index.html not found",
            "message": "Please ensure index.html is in the 'templates' folder",
            "template_folder": app.template_folder,
            "current_directory": os.getcwd(),
            "files_in_templates": os.listdir('templates') if os.path.exists('templates') else []
        }), 404


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files from templates/static folder"""
    return send_from_directory('templates/static', path)


# ========== API ENDPOINTS FOR YOUR HTML ==========

@app.route('/api/holdings', methods=['GET'])
def get_holdings():
    """Get current holdings for dashboard (open positions)"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            symbol,
            SUM(quantity) as quantity,
            ROUND(AVG(entry_price), 2) as buy_price,
            ROUND(AVG(entry_price), 2) as current_price,
            ROUND(SUM(quantity * entry_price), 2) as invested,
            ROUND(SUM(quantity * entry_price), 2) as current_value,
            ROUND(SUM(quantity * entry_price) - SUM(quantity * entry_price), 2) as unrealized_pnl
        FROM trades 
        WHERE status = 'OPEN'
        GROUP BY symbol
        ORDER BY symbol
    ''')
    
    holdings = [dict(row) for row in cursor.fetchall()]
    
    total_invested = sum(h.get('invested', 0) for h in holdings)
    total_value = sum(h.get('current_value', 0) for h in holdings)
    
    conn.close()
    
    return jsonify({
        "holdings": holdings,
        "total_invested": round(total_invested, 2),
        "current_value": round(total_value, 2),
        "total_pnl": round(total_value - total_invested, 2)
    })


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Get portfolio summary"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COALESCE(SUM(CASE WHEN status = 'OPEN' THEN quantity * entry_price ELSE 0 END), 0) as total_invested,
            COALESCE(SUM(CASE WHEN status = 'OPEN' THEN quantity * entry_price ELSE 0 END), 0) as current_value
        FROM trades
    ''')
    result = cursor.fetchone()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins
        FROM trades WHERE status = 'CLOSED'
    ''')
    win_data = cursor.fetchone()
    
    conn.close()
    
    win_rate = 0
    if win_data['total'] and win_data['total'] > 0:
        win_rate = round((win_data['wins'] / win_data['total']) * 100, 2)
    
    return jsonify({
        "total_invested": round(result['total_invested'], 2) if result else 0,
        "current_value": round(result['current_value'], 2) if result else 0,
        "total_pnl": 0,
        "win_rate": win_rate
    })


@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get trade analytics summary"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM trade_analytics ORDER BY updated_at DESC LIMIT 1')
    analytics = cursor.fetchone()
    conn.close()
    return jsonify({"analytics": dict(analytics) if analytics else {}})


@app.route('/api/recent-trades', methods=['GET'])
def get_recent_trades():
    """Get recent trades for history table"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, symbol, quantity, entry_price as buy_price, exit_price as sell_price, 
               profit_loss, status, entry_date as buy_date
        FROM trades 
        ORDER BY entry_date DESC 
        LIMIT 20
    ''')
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"recent_trades": trades})


@app.route('/api/execute-sql', methods=['POST'])
def execute_sql():
    """Execute SQL query"""
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            conn.commit()
            conn.close()
            return jsonify({
                "success": True,
                "data": result,
                "columns": list(result[0].keys()) if result else [],
                "row_count": len(result)
            })
        else:
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            return jsonify({
                "success": True,
                "message": "Query executed successfully",
                "affected_rows": affected
            })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 400


@app.route('/api/database/info', methods=['GET'])
def database_info():
    """Get database information"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row['name'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
    views = [row['name'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name")
    triggers = [row['name'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) FROM trades")
    count = cursor.fetchone()[0]
    
    size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    
    conn.close()
    
    return jsonify({
        "tables": tables,
        "views": views,
        "triggers": triggers,
        "record_count": count,
        "db_size_mb": round(size / (1024 * 1024), 2),
        "status": "connected"
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for frontend"""
    return jsonify({"status": "healthy", "server": "running", "port": 5000})


@app.route('/api/trades', methods=['GET'])
def get_trades():
    """Get all trades (full data)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM trades ORDER BY entry_date DESC')
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"trades": trades, "count": len(trades)})


@app.route('/api/active-trades', methods=['GET'])
def get_active_trades():
    """Get open positions from view"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM v_active_trades')
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"active_trades": trades})


@app.route('/api/closed-trades', methods=['GET'])
def get_closed_trades():
    """Get closed trades from view"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM v_closed_trades LIMIT 50')
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"closed_trades": tricks})


@app.route('/api/symbol-performance', methods=['GET'])
def get_symbol_performance():
    """Get performance by symbol from view"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM v_symbol_performance')
    performance = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"symbol_performance": performance})


@app.route('/api/daily-performance', methods=['GET'])
def get_daily_performance():
    """Get daily performance from view"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM v_daily_performance LIMIT 30')
    daily = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"daily_performance": daily})


@app.route('/api/monthly-performance', methods=['GET'])
def get_monthly_performance():
    """Get monthly performance from view"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM v_monthly_performance')
    monthly = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"monthly_performance": monthly})


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("📈 COMPLETE TRADING API - ALL TABLES, VIEWS & TRIGGERS")
    print("=" * 70)
    print(f"📁 Database: {DB_PATH}")
    print(f"📁 Templates folder: {app.template_folder}")
    print(f"📄 HTML File location: templates/index.html")
    print(f"🌐 Server: http://localhost:5000")
    print("\n📊 TABLES:")
    print("   - trades (main fact table)")
    print("   - trade_events (audit log)")
    print("   - trade_analytics (aggregated stats)")
    print("   - daily_aggregates")
    print("   - strategy_performance")
    print("   - monitor_logs")
    print("   - import_history")
    print("\n👁️ VIEWS:")
    print("   - v_active_trades")
    print("   - v_closed_trades")
    print("   - v_symbol_performance")
    print("   - v_daily_performance")
    print("   - v_monthly_performance")
    print("\n⚡ TRIGGERS:")
    print("   - trg_calculate_pnl")
    print("   - trg_log_trade_insert")
    print("   - trg_update_timestamp")
    print("=" * 70)
    print("\n✅ Server is running! Press Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)