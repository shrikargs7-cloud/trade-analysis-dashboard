import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'trades.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

conn = sqlite3.connect(DB_PATH)
try:
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"schema.sql not found at: {SCHEMA_PATH}")

    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()

    conn.executescript(schema)
    conn.commit()
    print(f"✅ Database created successfully using: {SCHEMA_PATH}")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
