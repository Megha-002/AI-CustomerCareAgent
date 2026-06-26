# diagnose_db.py
"""Quick diagnostic to see the actual database schema and sample data."""

import sqlite3
from pathlib import Path

db_path = str(Path(__file__).parent / "data" / "crm.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# ─── Get all table names ────────────────────────────────────
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Tables found:", tables)

# ─── For each table, show schema and sample row ─────────────
for table in tables:
    print(f"\n{'='*60}")
    print(f"TABLE: {table}")
    print(f"{'='*60}")
    
    # Schema
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    print("\nSchema:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Row count
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"\nTotal rows: {count}")
    
    # Sample first row
    cursor.execute(f"SELECT * FROM {table} LIMIT 1")
    sample = cursor.fetchone()
    if sample:
        print(f"\nSample row:")
        col_names = [col[1] for col in columns]
        for name, value in zip(col_names, sample):
            print(f"  {name} = {value!r}")

conn.close()