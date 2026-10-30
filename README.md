# 📈 Trade Analysis Dashboard

A modern trading analytics dashboard built with Flask and SQLite. Features portfolio tracking, SQL query terminal, live performance analytics, and Excel/CSV trade importing.

---

## 🚀 Features

- **Portfolio Holdings**: Real-time position tracking and profit/loss calculation.
- **Advanced Analytics**: Win rate, Sharpe ratio, Max Drawdown, and monthly performance heatmap.
- **SQL Terminal**: Interactive SQL query console with schema viewer, predefined views, and history.
- **Database Export**: One-click SQLite database backup and download (`trades.db`).
- **Excel/CSV Import**: Batch trade importing directly into the database.
- **Serverless Ready**: Configured for seamless deployment on **Vercel** with ephemeral SQLite handling.

---

## 🛠️ Project Structure

```
├── app.py              # Main Flask application & REST API
├── api/
│   └── index.py        # Vercel Serverless Function entry point
├── database.py         # Database utilities & trigger/view management
├── schema.sql          # Full SQLite database schema & seed data
├── sqlite.py           # Standalone DB initialization script
├── templates/
│   └── index.html      # Responsive Single Page Application (SPA)
├── requirements.txt    # Python dependencies
├── vercel.json         # Vercel routing configuration
└── .gitignore          # Ignored files (databases, caches, OS files)
```

---

## 💻 Local Setup & Running

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the application

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## ☁️ Deployment on Vercel

This repository is pre-configured for Vercel:

1. Import your GitHub repository in the [Vercel Dashboard](https://vercel.com).
2. Framework Preset: **Other** (detected automatically via `vercel.json` and `api/index.py`).
3. Deploy!

> **Note on SQLite on Serverless:** Vercel functions execute in an ephemeral environment. The database is initialized automatically with sample data in `/tmp/trades.db` upon cold starts.

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | `GET` | Dashboard interface |
| `/api/holdings` | `GET` | Active trade holdings & portfolio summary |
| `/api/summary` | `GET` | Portfolio invested & win rate stats |
| `/api/trades` | `GET` | Complete trade history |
| `/api/active-trades` | `GET` | Open positions (`v_active_trades`) |
| `/api/closed-trades` | `GET` | Closed positions (`v_closed_trades`) |
| `/api/symbol-performance` | `GET` | Performance aggregated by symbol |
| `/api/daily-performance` | `GET` | Daily P&L and win rate |
| `/api/monthly-performance` | `GET` | Monthly performance summary |
| `/api/database/info` | `GET` | Schema inspection (tables, views, triggers) |
| `/api/execute-sql` | `POST` | Execute custom SQL query |
| `/api/export-db` | `GET` | Download current SQLite database file |
| `/api/health` | `GET` | Server health check |
