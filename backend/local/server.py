#!/usr/bin/env python3
import duckdb
import json
import os
import subprocess
import sys
import logging
import threading
import queue
from datetime import datetime
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pr_tracker_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

DB_PATH = os.getenv("DB_PATH", "pr_tracker.duckdb")
logger.info(f"Using database: {DB_PATH}")

# Cache for in-memory database connection (shared across requests in tests)
_memory_db_conn = None

def get_db():
    global _memory_db_conn
    logger.debug(f"Opening database connection: {DB_PATH}")
    
    # For in-memory databases, reuse the same connection
    if DB_PATH == ':memory:':
        if _memory_db_conn is None:
            _memory_db_conn = duckdb.connect(DB_PATH)
        return _memory_db_conn
    
    # For file-based databases, create new connection each time
    conn = duckdb.connect(DB_PATH)
    return conn

def init_db():
    logger.info("Initializing database schema")
    schema_path = os.path.join(os.path.dirname(__file__), "../db/schema.sql")
    with open(schema_path) as f:
        conn = get_db()
        # DuckDB doesn't have executescript, execute statements one by one
        schema = f.read()
        for statement in schema.split(';'):
            statement = statement.strip()
            if statement:
                conn.execute(statement)
        # Don't close in-memory connections
        if DB_PATH != ':memory:':
            conn.close()
    logger.info("Database schema initialized successfully")

@app.route("/api/snapshots", methods=["GET"])
def get_snapshots():
    days = request.args.get("days", 30, type=int)
    logger.info(f"GET /api/snapshots - Fetching snapshots for last {days} days")
    
    try:
        conn = get_db()
        snapshots = conn.execute(
            f"""SELECT * FROM pr_snapshots 
               WHERE snapshot_date >= current_timestamp - INTERVAL '{days} DAYS'
               ORDER BY snapshot_date DESC"""
        ).fetchall()
        
        logger.info(f"Found {len(snapshots)} snapshots")
        # Convert to list of dicts
        columns = [desc[0] for desc in conn.description]
        result = [dict(zip(columns, row)) for row in snapshots]
        
        # Don't close in-memory connections
        if DB_PATH != ':memory:':
            conn.close()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching snapshots: {str(e)}", exc_info=True)
        error_response = {
            "error": str(e),
            "message": "Failed to fetch snapshots"
        }
        # In debug mode, include stack trace
        if app.debug:
            import traceback
            error_response["traceback"] = traceback.format_exc()
        return jsonify(error_response), 500

@app.route("/api/snapshots/<int:snapshot_id>/prs", methods=["GET"])
def get_snapshot_prs(snapshot_id):
    logger.info(f"GET /api/snapshots/{snapshot_id}/prs - Fetching PRs for snapshot")
    
    try:
        conn = get_db()
        prs = conn.execute(
            "SELECT * FROM prs WHERE snapshot_id = $1 ORDER BY age_days DESC",
            [snapshot_id]
        ).fetchall()
        
        logger.info(f"Found {len(prs)} PRs for snapshot {snapshot_id}")
        columns = [desc[0] for desc in conn.description]
        result = [dict(zip(columns, row)) for row in prs]
        
        if DB_PATH != ':memory:':
            conn.close()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching PRs for snapshot {snapshot_id}: {str(e)}", exc_info=True)
        error_response = {
            "error": str(e),
            "message": f"Failed to fetch PRs for snapshot {snapshot_id}"
        }
        # In debug mode, include stack trace
        if app.debug:
            import traceback
            error_response["traceback"] = traceback.format_exc()
        return jsonify(error_response), 500

@app.route("/api/snapshots/<int:snapshot_id>", methods=["DELETE"])
def delete_snapshot(snapshot_id):
    """Delete a snapshot and all associated PRs and comments"""
    logger.info(f"DELETE /api/snapshots/{snapshot_id} - Deleting snapshot")
    
    try:
        conn = get_db()
        
        # Check if snapshot exists
        snapshot = conn.execute(
            "SELECT id FROM pr_snapshots WHERE id = $1",
            [snapshot_id]
        ).fetchone()
        
        if not snapshot:
            logger.warning(f"Snapshot {snapshot_id} not found")
            return jsonify({
                "error": "Snapshot not found",
                "message": f"Snapshot with ID {snapshot_id} does not exist"
            }), 404
        
        # Manually delete in correct order: comments -> prs -> snapshot
        # First, delete all comments for PRs in this snapshot
        conn.execute("""
            DELETE FROM pr_comments 
            WHERE pr_id IN (
                SELECT id FROM prs WHERE snapshot_id = $1
            )
        """, [snapshot_id])
        
        # Then delete all PRs for this snapshot
        conn.execute(
            "DELETE FROM prs WHERE snapshot_id = $1",
            [snapshot_id]
        )
        
        # Finally delete the snapshot itself
        conn.execute(
            "DELETE FROM pr_snapshots WHERE id = $1",
            [snapshot_id]
        )
        
        if DB_PATH != ':memory:':
            conn.close()
        
        logger.info(f"Successfully deleted snapshot {snapshot_id}")
        return jsonify({
            "success": True,
            "message": f"Snapshot {snapshot_id} deleted successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting snapshot {snapshot_id}: {str(e)}", exc_info=True)
        error_response = {
            "error": str(e),
            "message": f"Failed to delete snapshot {snapshot_id}"
        }
        # In debug mode, include stack trace
        if app.debug:
            import traceback
            error_response["traceback"] = traceback.format_exc()
        return jsonify(error_response), 500

@app.route("/api/snapshots", methods=["POST"])
def create_snapshot():
    data = request.json
    logger.info(f"POST /api/snapshots - Creating snapshot for {data.get('repo_owner')}/{data.get('repo_name')}")
    logger.debug(f"Snapshot data: {data.get('total_prs')} PRs, {len(data.get('prs', []))} PR details")
    
    conn = get_db()
    
    try:
        # Use RETURNING to get the inserted ID
        result = conn.execute(
            """INSERT INTO pr_snapshots (repo_owner, repo_name, total_prs, unassigned_count, old_prs_count)
               VALUES ($1, $2, $3, $4, $5) RETURNING id""",
            [data["repo_owner"], data["repo_name"], data["total_prs"], 
             data["unassigned_count"], data["old_prs_count"]]
        )
        snapshot_id = result.fetchone()[0]
        logger.info(f"Created snapshot with ID: {snapshot_id}")
        
        pr_count = 0
        comment_count = 0
        for pr in data.get("prs", []):
            result = conn.execute(
                """INSERT INTO prs (snapshot_id, pr_number, title, url, created_at, 
                   updated_at, age_days, reviewers, state)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id""",
                [snapshot_id, pr["number"], pr["title"], pr["url"], pr["created_at"],
                 pr["updated_at"], pr["age_days"], pr["reviewers"], pr["state"]]
            )
            pr_id = result.fetchone()[0]
            pr_count += 1
            
            # Store comment counts
            for comment in pr.get("comments", []):
                conn.execute(
                    """INSERT INTO pr_comments (pr_id, reviewer, comment_count)
                       VALUES ($1, $2, $3)""",
                    [pr_id, comment["reviewer"], comment["comment_count"]]
                )
                comment_count += 1
        
        if DB_PATH != ':memory:':
            conn.close()
        logger.info(f"Stored {pr_count} PRs and {comment_count} comment records")
        return jsonify({"snapshot_id": snapshot_id}), 201
        
    except Exception as e:
        logger.error(f"Error creating snapshot: {str(e)}", exc_info=True)
        if DB_PATH != ':memory:':
            conn.close()
        error_response = {
            "error": str(e),
            "message": "Failed to create snapshot"
        }
        # In debug mode, include stack trace and request data
        if app.debug:
            import traceback
            error_response["traceback"] = traceback.format_exc()
            error_response["debug"] = {
                "repo_owner": data.get("repo_owner"),
                "repo_name": data.get("repo_name"),
                "total_prs": data.get("total_prs"),
                "pr_count": len(data.get("prs", []))
            }
        return jsonify(error_response), 500

@app.route("/api/stats", methods=["GET"])
def get_stats():
    # Get threshold parameter with default value of 30
    threshold_str = request.args.get("threshold", None)
    
    # If threshold is provided, validate it
    if threshold_str is not None:
        try:
            threshold = int(threshold_str)
            if threshold <= 0:
                logger.warning(f"Invalid threshold parameter: {threshold}")
                return jsonify({
                    "error": "threshold must be a positive integer"
                }), 400
        except (ValueError, TypeError):
            logger.warning(f"Non-numeric threshold parameter: {threshold_str}")
            return jsonify({
                "error": "threshold must be a positive integer"
            }), 400
    else:
        threshold = 30  # Default value
    
    logger.info(f"GET /api/stats - Fetching statistics with threshold={threshold}")
    
    try:
        conn = get_db()
        latest = conn.execute(
            "SELECT * FROM pr_snapshots ORDER BY snapshot_date DESC LIMIT 1"
        ).fetchone()
        
        if latest:
            columns = [desc[0] for desc in conn.description]
            latest_dict = dict(zip(columns, latest))
            logger.info(f"Latest snapshot: ID={latest_dict['id']}, Date={latest_dict['snapshot_date']}")
        else:
            latest_dict = None
            logger.info("No snapshots found")
        
        # Calculate trend metrics using SQL with CTEs
        trend = conn.execute(
            """
            WITH snapshot_dates AS (
                SELECT 
                    id AS snapshot_id,
                    snapshot_date,
                    repo_owner,
                    repo_name
                FROM pr_snapshots
                WHERE snapshot_date >= current_timestamp - INTERVAL '30 DAYS'
                ORDER BY snapshot_date ASC
            ),
            pr_metrics AS (
                SELECT 
                    p.snapshot_id,
                    COUNT(*) AS total_prs,
                    SUM(CASE 
                        WHEN p.reviewers IS NOT NULL AND p.reviewers != 'None' 
                        THEN 1 ELSE 0 
                    END) AS under_review_count,
                    SUM(CASE 
                        WHEN (LENGTH(p.reviewers) - LENGTH(REPLACE(p.reviewers, '[APPROVED]', ''))) / LENGTH('[APPROVED]') >= 2
                        THEN 1 ELSE 0 
                    END) AS two_approvals_count,
                    SUM(CASE 
                        WHEN p.age_days > $1
                        THEN 1 ELSE 0 
                    END) AS old_prs_count
                FROM prs p
                WHERE p.state = 'open'
                GROUP BY p.snapshot_id
            )
            SELECT 
                sd.snapshot_date,
                COALESCE(pm.total_prs, 0) AS total_prs,
                COALESCE(pm.under_review_count, 0) AS under_review_count,
                COALESCE(pm.two_approvals_count, 0) AS two_approvals_count,
                COALESCE(pm.old_prs_count, 0) AS old_prs_count
            FROM snapshot_dates sd
            LEFT JOIN pr_metrics pm ON sd.snapshot_id = pm.snapshot_id
            ORDER BY sd.snapshot_date ASC
            """,
            [threshold]
        ).fetchall()
        
        logger.info(f"Found {len(trend)} trend data points with threshold={threshold}")
        trend_columns = [desc[0] for desc in conn.description]
        trend_list = [dict(zip(trend_columns, row)) for row in trend]
        
        # Get reviewer workload from latest snapshot
        reviewer_stats = []
        if latest_dict:
            prs = conn.execute(
                "SELECT id, reviewers FROM prs WHERE snapshot_id = $1 AND state = 'open'",
                [latest_dict["id"]]
            ).fetchall()
            
            logger.debug(f"Processing {len(prs)} PRs for reviewer stats")
            
            # Count PRs and comments per reviewer
            reviewer_data = {}
            for pr_row in prs:
                pr_id = pr_row[0]
                reviewers_str = pr_row[1]
                
                if reviewers_str and reviewers_str != "None":
                    # Parse reviewers string like "user1 [APPROVED], user2 [NO ACTION]"
                    reviewers = reviewers_str.split(", ")
                    for reviewer in reviewers:
                        # Extract username (before the bracket) and status
                        parts = reviewer.split(" [")
                        username = parts[0].strip()
                        status = parts[1].rstrip("]") if len(parts) > 1 else ""
                        
                        if username:
                            if username not in reviewer_data:
                                reviewer_data[username] = {"count": 0, "comments": 0, "approvals": 0}
                            reviewer_data[username]["count"] += 1
                            
                            # Count approvals
                            if status == "APPROVED":
                                reviewer_data[username]["approvals"] += 1
                            
                            # Get comment count for this reviewer on this PR
                            comment_result = conn.execute(
                                "SELECT comment_count FROM pr_comments WHERE pr_id = $1 AND reviewer = $2",
                                [pr_id, username]
                            ).fetchone()
                            if comment_result:
                                reviewer_data[username]["comments"] += comment_result[0]
            
            # Convert to list and sort by PR count
            reviewer_stats = [
                {"reviewer": name, "count": data["count"], "comments": data["comments"], "approvals": data["approvals"]}
                for name, data in sorted(reviewer_data.items(), key=lambda x: x[1]["count"], reverse=True)
            ]
            
            logger.info(f"Generated stats for {len(reviewer_stats)} reviewers")
        
        if DB_PATH != ':memory:':
            conn.close()
        return jsonify({
            "latest": latest_dict,
            "trend": trend_list,
            "reviewers": reviewer_stats
        })
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}", exc_info=True)
        error_response = {
            "error": str(e),
            "message": "Failed to fetch statistics"
        }
        # In debug mode, include stack trace
        if app.debug:
            import traceback
            error_response["traceback"] = traceback.format_exc()
        return jsonify(error_response), 500

@app.route("/api/snapshots/<int:snapshot_id>/reviewers", methods=["GET"])
def get_snapshot_reviewers(snapshot_id):
    """Get reviewer workload for a specific snapshot"""
    logger.info(f"GET /api/snapshots/{snapshot_id}/reviewers - Fetching reviewer stats")
    
    try:
        conn = get_db()
        
        # Verify snapshot exists
        snapshot = conn.execute(
            "SELECT id FROM pr_snapshots WHERE id = $1",
            [snapshot_id]
        ).fetchone()
        
        if not snapshot:
            logger.warning(f"Snapshot {snapshot_id} not found")
            return jsonify({
                "error": "Snapshot not found",
                "message": f"Snapshot with ID {snapshot_id} does not exist"
            }), 404
        
        # Get PRs for this snapshot
        prs = conn.execute(
            "SELECT id, reviewers FROM prs WHERE snapshot_id = $1 AND state = 'open'",
            [snapshot_id]
        ).fetchall()
        
        logger.debug(f"Processing {len(prs)} PRs for reviewer stats")
        
        # Count PRs and comments per reviewer
        reviewer_data = {}
        for pr_row in prs:
            pr_id = pr_row[0]
            reviewers_str = pr_row[1]
            
            if reviewers_str and reviewers_str != "None":
                # Parse reviewers string like "user1 [APPROVED], user2 [NO ACTION]"
                reviewers = reviewers_str.split(", ")
                for reviewer in reviewers:
                    # Extract username (before the bracket) and status
                    parts = reviewer.split(" [")
                    username = parts[0].strip()
                    status = parts[1].rstrip("]") if len(parts) > 1 else ""
                    
                    if username:
                        if username not in reviewer_data:
                            reviewer_data[username] = {"count": 0, "comments": 0, "approvals": 0}
                        reviewer_data[username]["count"] += 1
                        
                        # Count approvals
                        if status == "APPROVED":
                            reviewer_data[username]["approvals"] += 1
                        
                        # Get comment count for this reviewer on this PR
                        comment_result = conn.execute(
                            "SELECT comment_count FROM pr_comments WHERE pr_id = $1 AND reviewer = $2",
                            [pr_id, username]
                        ).fetchone()
                        if comment_result:
                            reviewer_data[username]["comments"] += comment_result[0]
        
        # Convert to list and sort by PR count
        reviewer_stats = [
            {"reviewer": name, "count": data["count"], "comments": data["comments"], "approvals": data["approvals"]}
            for name, data in sorted(reviewer_data.items(), key=lambda x: x[1]["count"], reverse=True)
        ]
        
        logger.info(f"Generated stats for {len(reviewer_stats)} reviewers from snapshot {snapshot_id}")
        
        if DB_PATH != ':memory:':
            conn.close()
        
        return jsonify(reviewer_stats)
        
    except Exception as e:
        logger.error(f"Error fetching reviewer stats for snapshot {snapshot_id}: {str(e)}", exc_info=True)
        error_response = {
            "error": str(e),
            "message": f"Failed to fetch reviewer stats for snapshot {snapshot_id}"
        }
        if app.debug:
            import traceback
            error_response["traceback"] = traceback.format_exc()
        return jsonify(error_response), 500

@app.route("/api/snapshots/compare", methods=["GET"])
def compare_snapshots():
    """Compare two snapshots to identify new, closed, and status-changed PRs"""
    snapshot1_id = request.args.get("snapshot1", type=int)
    snapshot2_id = request.args.get("snapshot2", type=int)
    
    if not snapshot1_id or not snapshot2_id:
        return jsonify({
            "error": "Both snapshot1 and snapshot2 parameters are required"
        }), 400
    
    logger.info(f"GET /api/snapshots/compare - Comparing snapshots {snapshot1_id} and {snapshot2_id}")
    
    try:
        conn = get_db()
        
        # Fetch PRs from both snapshots
        prs1 = conn.execute(
            "SELECT pr_number, title, url, reviewers, age_days FROM prs WHERE snapshot_id = $1 AND state = 'open'",
            [snapshot1_id]
        ).fetchall()
        
        prs2 = conn.execute(
            "SELECT pr_number, title, url, reviewers, age_days FROM prs WHERE snapshot_id = $1 AND state = 'open'",
            [snapshot2_id]
        ).fetchall()
        
        # Convert to dicts for easier processing
        prs1_dict = {pr[0]: {"pr_number": pr[0], "title": pr[1], "url": pr[2], "reviewers": pr[3], "age_days": pr[4]} for pr in prs1}
        prs2_dict = {pr[0]: {"pr_number": pr[0], "title": pr[1], "url": pr[2], "reviewers": pr[3], "age_days": pr[4]} for pr in prs2}
        
        def get_approval_count(reviewers_str):
            if not reviewers_str or reviewers_str == "None":
                return 0
            return len([r for r in reviewers_str.split(", ") if "[APPROVED]" in r])
        
        def get_color(approval_count):
            if approval_count >= 2:
                return "green"
            elif approval_count == 1:
                return "yellow"
            else:
                return "red"
        
        # Find new PRs (in snapshot2 but not in snapshot1)
        new_prs = []
        for pr_num, pr_data in prs2_dict.items():
            if pr_num not in prs1_dict:
                approval_count = get_approval_count(pr_data["reviewers"])
                new_prs.append({
                    **pr_data,
                    "approval_count": approval_count,
                    "color": get_color(approval_count)
                })
        
        # Find closed PRs (in snapshot1 but not in snapshot2)
        closed_prs = []
        for pr_num, pr_data in prs1_dict.items():
            if pr_num not in prs2_dict:
                approval_count = get_approval_count(pr_data["reviewers"])
                closed_prs.append({
                    **pr_data,
                    "approval_count": approval_count,
                    "color": get_color(approval_count)
                })
        
        # Find status-changed PRs (in both but different approval status)
        status_changed = []
        unchanged = []
        for pr_num, pr_data2 in prs2_dict.items():
            if pr_num in prs1_dict:
                pr_data1 = prs1_dict[pr_num]
                approval_count1 = get_approval_count(pr_data1["reviewers"])
                approval_count2 = get_approval_count(pr_data2["reviewers"])
                color1 = get_color(approval_count1)
                color2 = get_color(approval_count2)
                
                if color1 != color2:
                    status_changed.append({
                        **pr_data2,
                        "approval_count_before": approval_count1,
                        "approval_count_after": approval_count2,
                        "color_before": color1,
                        "color_after": color2
                    })
                else:
                    unchanged.append({
                        **pr_data2,
                        "approval_count": approval_count2,
                        "color": color2
                    })
        
        # Get snapshot metadata
        snapshot1 = conn.execute("SELECT snapshot_date, repo_owner, repo_name FROM pr_snapshots WHERE id = $1", [snapshot1_id]).fetchone()
        snapshot2 = conn.execute("SELECT snapshot_date, repo_owner, repo_name FROM pr_snapshots WHERE id = $1", [snapshot2_id]).fetchone()
        
        if DB_PATH != ':memory:':
            conn.close()
        
        result = {
            "snapshot1": {
                "id": snapshot1_id,
                "date": snapshot1[0] if snapshot1 else None,
                "repo": f"{snapshot1[1]}/{snapshot1[2]}" if snapshot1 else None
            },
            "snapshot2": {
                "id": snapshot2_id,
                "date": snapshot2[0] if snapshot2 else None,
                "repo": f"{snapshot2[1]}/{snapshot2[2]}" if snapshot2 else None
            },
            "new_prs": new_prs,
            "closed_prs": closed_prs,
            "status_changed": status_changed,
            "unchanged": unchanged,
            "summary": {
                "new_count": len(new_prs),
                "closed_count": len(closed_prs),
                "status_changed_count": len(status_changed),
                "unchanged_count": len(unchanged)
            }
        }
        
        logger.info(f"Comparison complete: {len(new_prs)} new, {len(closed_prs)} closed, {len(status_changed)} changed")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error comparing snapshots: {str(e)}", exc_info=True)
        error_response = {
            "error": str(e),
            "message": "Failed to compare snapshots"
        }
        if app.debug:
            import traceback
            error_response["traceback"] = traceback.format_exc()
        return jsonify(error_response), 500

@app.route("/api/import", methods=["POST"])
def import_data():
    """Trigger the track_open_prs.py script to collect and store data"""
    logger.info("POST /api/import - Starting data import")
    
    try:
        # Get the path to track_open_prs.py (two directories up from here)
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "track_open_prs.py"))
        logger.info(f"Running script: {script_path}")
        
        # Run the script with --store flag
        result = subprocess.run(
            [sys.executable, script_path, "--store"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        logger.info(f"Script exit code: {result.returncode}")
        logger.debug(f"Script stdout: {result.stdout}")
        
        if result.returncode == 0:
            logger.info("Data import completed successfully")
            return jsonify({
                "success": True,
                "message": "Data imported successfully",
                "output": result.stdout
            })
        else:
            logger.error(f"Script failed with stderr: {result.stderr}")
            error_response = {
                "success": False,
                "message": "Import failed",
                "error": result.stderr,
                "stdout": result.stdout
            }
            # In debug mode, include full details
            if app.debug:
                error_response["debug"] = {
                    "script_path": script_path,
                    "exit_code": result.returncode
                }
            return jsonify(error_response), 500
    except subprocess.TimeoutExpired:
        logger.error("Import timed out after 5 minutes")
        return jsonify({
            "success": False,
            "message": "Import timed out after 5 minutes"
        }), 500
    except Exception as e:
        logger.error(f"Import error: {str(e)}", exc_info=True)
        error_response = {
            "success": False,
            "message": f"Import error: {str(e)}"
        }
        # In debug mode, include stack trace
        if app.debug:
            import traceback
            error_response["traceback"] = traceback.format_exc()
        return jsonify(error_response), 500

@app.route("/api/import-historical", methods=["POST"])
def import_historical():
    """Trigger the import_historical_snapshots.py script with streaming progress"""
    logger.info("POST /api/import-historical - Starting historical import")
    
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    
    if not start_date:
        logger.error("Missing start_date parameter")
        return jsonify({
            "success": False,
            "message": "start_date parameter is required"
        }), 400
    
    def generate():
        """Generator function to stream progress updates"""
        try:
            # Get the path to import_historical_snapshots.py
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "import_historical_snapshots.py"))
            logger.info(f"Running script: {script_path} with start_date={start_date}, end_date={end_date}")
            
            # Build command
            cmd = [sys.executable, script_path, start_date]
            if end_date:
                cmd.append(end_date)
            
            # Run the script and stream output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            imported = 0
            skipped = 0
            failed = 0
            total = 0
            current_date = None
            
            # Read output line by line
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue
                
                logger.debug(f"Script output: {line}")
                
                # Parse progress from log lines
                if 'Processing snapshot for' in line:
                    # Extract date from line like "Processing snapshot for 2025-12-22"
                    parts = line.split('Processing snapshot for')
                    if len(parts) > 1:
                        current_date = parts[1].strip()
                        
                        # Send progress update
                        if total > 0:
                            percent = int((imported + skipped + failed) / total * 100)
                        else:
                            percent = 0
                        
                        progress_data = {
                            'type': 'progress',
                            'current_date': current_date,
                            'imported': imported,
                            'skipped': skipped,
                            'failed': failed,
                            'percent': percent
                        }
                        yield f"data: {json.dumps(progress_data)}\n\n"
                
                elif 'Successfully imported:' in line:
                    imported = int(line.split(':')[1].strip())
                elif 'Skipped (already exist):' in line:
                    skipped = int(line.split(':')[1].strip())
                elif 'Failed:' in line:
                    failed = int(line.split(':')[1].strip())
                elif 'Total dates processed:' in line:
                    total = int(line.split(':')[1].strip())
                elif 'Will import' in line and 'weekly snapshots' in line:
                    # Extract total from line like "Will import 9 weekly snapshots"
                    parts = line.split('Will import')
                    if len(parts) > 1:
                        total = int(parts[1].split()[0])
            
            process.wait()
            
            if process.returncode == 0:
                logger.info(f"Historical import completed: {imported} imported, {skipped} skipped, {failed} failed")
                
                # Send completion update
                complete_data = {
                    'type': 'complete',
                    'success': True,
                    'imported': imported,
                    'skipped': skipped,
                    'failed': failed,
                    'total': total
                }
                yield f"data: {json.dumps(complete_data)}\n\n"
            else:
                logger.error(f"Script failed with return code: {process.returncode}")
                error_data = {
                    'type': 'error',
                    'message': 'Historical import failed'
                }
                # In debug mode, include more details
                if app.debug:
                    error_data['debug'] = {
                        'script_path': script_path,
                        'exit_code': process.returncode,
                        'command': ' '.join(cmd)
                    }
                yield f"data: {json.dumps(error_data)}\n\n"
                
        except Exception as e:
            logger.error(f"Historical import error: {str(e)}", exc_info=True)
            error_data = {
                'type': 'error',
                'message': f"Import error: {str(e)}"
            }
            # In debug mode, include stack trace
            if app.debug:
                import traceback
                error_data['traceback'] = traceback.format_exc()
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        logger.info("Database not found, initializing...")
        init_db()
    
    logger.info("Starting Flask server on port 5001")
    app.run(host="0.0.0.0", debug=True, port=5001)
