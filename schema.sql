-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trades table (with ALL required columns)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE,
    symbol TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    quantity INTEGER NOT NULL,
    trade_type TEXT CHECK(trade_type IN ('BUY', 'SELL', 'LONG', 'SHORT')) NOT NULL,
    entry_date DATETIME NOT NULL,
    exit_date DATETIME,
    status TEXT CHECK(status IN ('OPEN', 'CLOSED', 'CANCELLED')) DEFAULT 'OPEN',
    profit_loss REAL DEFAULT 0,
    profit_loss_percentage REAL DEFAULT 0,
    strategy TEXT,
    notes TEXT,
    source TEXT DEFAULT 'WEB',
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Trade analytics table
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger to handle the 'ON UPDATE' behavior for analytics
DROP TRIGGER IF EXISTS update_trade_analytics_timestamp;
CREATE TRIGGER update_trade_analytics_timestamp
AFTER UPDATE ON trade_analytics
FOR EACH ROW
BEGIN
    UPDATE trade_analytics SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Insert sample users (using INSERT OR IGNORE to prevent duplicates)
INSERT OR IGNORE INTO users (username, email) VALUES 
('trader1', 'trader1@example.com'),
('trader2', 'trader2@example.com');

-- Insert sample trades (matching the columns exactly)
INSERT OR IGNORE INTO trades (symbol, entry_price, exit_price, quantity, trade_type, entry_date, exit_date, status, profit_loss, profit_loss_percentage, strategy, notes, source, user_id) VALUES
    ('AAPL', 150.25, NULL, 10, 'BUY', datetime('now', '-5 days'), NULL, 'OPEN', 0, 0, 'Momentum', NULL, 'SAMPLE', 1),
    ('MSFT', 420.50, NULL, 5, 'BUY', datetime('now', '-4 days'), NULL, 'OPEN', 0, 0, 'Value', NULL, 'SAMPLE', 1),
    ('GOOGL', 135.00, NULL, 8, 'BUY', datetime('now', '-3 days'), NULL, 'OPEN', 0, 0, 'Growth', NULL, 'SAMPLE', 1),
    ('NVDA', 850.00, 870.00, 4, 'BUY', datetime('now', '-3 days'), datetime('now', '-1 days'), 'CLOSED', 80.00, 2.35, 'Momentum', NULL, 'SAMPLE', 1),
    ('TSLA', 250.00, 260.00, 6, 'BUY', datetime('now', '-2 days'), datetime('now'), 'CLOSED', 60.00, 4.00, 'Breakout', NULL, 'SAMPLE', 1),
    ('AMZN', 178.50, NULL, 12, 'BUY', datetime('now', '-7 days'), NULL, 'OPEN', 0, 0, 'Growth', NULL, 'SAMPLE', 1),
    ('META', 485.00, 492.00, 3, 'BUY', datetime('now', '-6 days'), datetime('now', '-2 days'), 'CLOSED', 21.00, 1.44, 'Value', NULL, 'SAMPLE', 1),
    ('NFLX', 625.75, NULL, 7, 'BUY', datetime('now', '-5 days'), NULL, 'OPEN', 0, 0, 'Momentum', NULL, 'SAMPLE', 1),
    ('AMD', 145.30, 148.20, 15, 'BUY', datetime('now', '-4 days'), datetime('now', '-1 days'), 'CLOSED', 43.50, 2.00, 'Breakout', NULL, 'SAMPLE', 1),
    ('INTC', 42.80, NULL, 20, 'BUY', datetime('now', '-10 days'), NULL, 'OPEN', 0, 0, 'Value', NULL, 'SAMPLE', 1),
    ('PYPL', 68.50, 70.25, 8, 'SELL', datetime('now', '-8 days'), datetime('now', '-3 days'), 'CLOSED', -14.00, -2.55, 'Momentum', NULL, 'SAMPLE', 2),
    ('CRM', 298.00, NULL, 6, 'BUY', datetime('now', '-6 days'), NULL, 'OPEN', 0, 0, 'Growth', NULL, 'SAMPLE', 2),
    ('ADBE', 555.00, 560.50, 4, 'BUY', datetime('now', '-5 days'), datetime('now', '-2 days'), 'CLOSED', 22.00, 0.99, 'Value', NULL, 'SAMPLE', 2),
    ('NOW', 768.00, NULL, 2, 'BUY', datetime('now', '-4 days'), NULL, 'OPEN', 0, 0, 'Momentum', NULL, 'SAMPLE', 2),
    ('UBER', 72.30, 74.00, 14, 'BUY', datetime('now', '-3 days'), datetime('now', '-1 days'), 'CLOSED', 23.80, 2.35, 'Breakout', NULL, 'SAMPLE', 2),
    ('SHOP', 72.00, NULL, 11, 'BUY', datetime('now', '-9 days'), NULL, 'OPEN', 0, 0, 'Growth', NULL, 'SAMPLE', 2),
    ('COIN', 235.00, 245.00, 5, 'BUY', datetime('now', '-7 days'), datetime('now', '-3 days'), 'CLOSED', 50.00, 2.13, 'Momentum', NULL, 'SAMPLE', 2),
    ('SNOW', 168.50, NULL, 9, 'BUY', datetime('now', '-6 days'), NULL, 'OPEN', 0, 0, 'Value', NULL, 'SAMPLE', 2),
    ('BA', 185.00, 182.50, 7, 'SELL', datetime('now', '-5 days'), datetime('now', '-2 days'), 'CLOSED', -17.50, -1.35, 'Breakout', NULL, 'SAMPLE', 2),
    ('DIS', 110.25, NULL, 13, 'BUY', datetime('now', '-8 days'), NULL, 'OPEN', 0, 0, 'Growth', NULL, 'SAMPLE', 2),
    ('JPM', 198.50, 202.00, 10, 'BUY', datetime('now', '-4 days'), datetime('now', '-1 days'), 'CLOSED', 35.00, 1.76, 'Value', NULL, 'SAMPLE', 1),
    ('V', 275.00, NULL, 8, 'BUY', datetime('now', '-3 days'), NULL, 'OPEN', 0, 0, 'Momentum', NULL, 'SAMPLE', 1),
    ('WMT', 168.75, 170.00, 12, 'BUY', datetime('now', '-2 days'), datetime('now'), 'CLOSED', 15.00, 1.48, 'Value', NULL, 'SAMPLE', 1),
    ('JNJ', 156.30, NULL, 10, 'BUY', datetime('now', '-7 days'), NULL, 'OPEN', 0, 0, 'Growth', NULL, 'SAMPLE', 1),
    ('PG', 162.40, 163.20, 15, 'BUY', datetime('now', '-5 days'), datetime('now', '-1 days'), 'CLOSED', 12.00, 0.49, 'Value', NULL, 'SAMPLE', 1);

-- Update trade analytics based on initial data
INSERT OR IGNORE INTO trade_analytics (total_trades, winning_trades, losing_trades, win_rate, total_profit_loss, average_profit, average_loss, max_profit, max_loss)
SELECT 
    COUNT(*) as total_trades,
    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
    ROUND(100.0 * SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(SUM(profit_loss), 2) as total_profit_loss,
    ROUND(AVG(CASE WHEN profit_loss > 0 THEN profit_loss ELSE NULL END), 2) as average_profit,
    ROUND(AVG(CASE WHEN profit_loss < 0 THEN profit_loss ELSE NULL END), 2) as average_loss,
    ROUND(MAX(profit_loss), 2) as max_profit,
    ROUND(MIN(profit_loss), 2) as max_loss
FROM trades 
WHERE status = 'CLOSED';