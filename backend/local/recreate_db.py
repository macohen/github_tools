#!/usr/bin/env python3
"""
Script to recreate the DuckDB database with the latest schema
"""
import os
import duckdb
import shutil
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "pr_tracker.duckdb")
SCHEMA_PATH = "../db/schema.sql"

def recreate_database():
    """Recreate the database with the latest schema"""
    
    # Backup existing database if it exists
    if os.path.exists(DB_PATH):
        backup_path = f"{DB_PATH}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Backing up existing database to: {backup_path}")
        shutil.copy2(DB_PATH, backup_path)
        
        # Remove old database
        os.remove(DB_PATH)
        print(f"Removed old database: {DB_PATH}")
    
    # Create new database
    print(f"Creating new database: {DB_PATH}")
    conn = duckdb.connect(DB_PATH)
    
    # Read and execute schema
    print(f"Applying schema from: {SCHEMA_PATH}")
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()
        # Execute each statement separately for DuckDB
        for statement in schema.split(';'):
            statement = statement.strip()
            if statement:
                conn.execute(statement)
    
    conn.commit()
    conn.close()
    
    print("✓ Database recreated successfully!")
    print(f"\nDatabase location: {os.path.abspath(DB_PATH)}")
    
    # Show tables
    conn = duckdb.connect(DB_PATH)
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
    conn.close()
    
    print("\nTables created:")
    for table in tables:
        print(f"  - {table[0]}")

if __name__ == "__main__":
    recreate_database()
