import sqlite3
import os

# 1. Connect to the database
conn = sqlite3.connect('trades.db')

# 2. Try multiple possible locations
possible_paths = [
    'schema.sql',  # Current directory
    '../schema.sql',  # One level up
    './schema.sql',  # Explicit current directory
    '/Users/shrikar/Desktop/my_flask_app copy/venv/trade_analysis_app/schema.sql',  # Your absolute path
]

schema_path = None
for path in possible_paths:
    if os.path.exists(path):
        schema_path = path
        break

# 3. Read and execute
try:
    if schema_path is None:
        raise FileNotFoundError(f"schema.sql not found in any of: {possible_paths}")
    
    with open(schema_path, 'r') as f:
        schema = f.read()
    
    conn.executescript(schema)
    conn.commit()
    print(f"✅ Database created successfully using: {schema_path}")
    
except FileNotFoundError as e:
    print(f"❌ Error: {e}")
    print(f"   Current directory: {os.getcwd()}")
    print(f"   Files here: {os.listdir('.')}")
except sqlite3.Error as e:
    print(f"❌ SQLite Error: {e}")
finally:
    conn.close()