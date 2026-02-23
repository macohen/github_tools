import json
import sqlite3
import os
import boto3
from datetime import datetime

s3 = boto3.client("s3")
BUCKET = os.getenv("DB_BUCKET")
DB_KEY = "pr_tracker.db"
LOCAL_DB = "/tmp/pr_tracker.db"

def get_db():
    if not os.path.exists(LOCAL_DB):
        try:
            s3.download_file(BUCKET, DB_KEY, LOCAL_DB)
        except:
            init_db()
    
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    return conn

def save_db():
    s3.upload_file(LOCAL_DB, BUCKET, DB_KEY)

def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pr_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            repo_owner TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            total_prs INTEGER,
            unassigned_count INTEGER,
            old_prs_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS prs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER,
            pr_number INTEGER,
            title TEXT,
            url TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            age_days INTEGER,
            reviewers TEXT,
            state TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES pr_snapshots(id)
        );
    """)
    conn.commit()

def lambda_handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    
    conn = get_db()
    
    if path == "/api/snapshots" and method == "GET":
        days = int(event.get("queryStringParameters", {}).get("days", 30))
        snapshots = conn.execute(
            """SELECT * FROM pr_snapshots 
               WHERE snapshot_date >= datetime('now', '-' || ? || ' days')
               ORDER BY snapshot_date DESC""",
            (days,)
        ).fetchall()
        return {
            "statusCode": 200,
            "body": json.dumps([dict(s) for s in snapshots])
        }
    
    elif path == "/api/snapshots" and method == "POST":
        data = json.loads(event["body"])
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO pr_snapshots (repo_owner, repo_name, total_prs, unassigned_count, old_prs_count)
               VALUES (?, ?, ?, ?, ?)""",
            (data["repo_owner"], data["repo_name"], data["total_prs"], 
             data["unassigned_count"], data["old_prs_count"])
        )
        snapshot_id = cursor.lastrowid
        
        for pr in data.get("prs", []):
            cursor.execute(
                """INSERT INTO prs (snapshot_id, pr_number, title, url, created_at, 
                   updated_at, age_days, reviewers, state)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (snapshot_id, pr["number"], pr["title"], pr["url"], pr["created_at"],
                 pr["updated_at"], pr["age_days"], pr["reviewers"], pr["state"])
            )
        
        conn.commit()
        save_db()
        
        return {
            "statusCode": 201,
            "body": json.dumps({"snapshot_id": snapshot_id})
        }
    
    return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}
