#!/bin/bash
# Start PR Tracker services

APP_DIR=$HOME/pr-tracker
LOG_DIR=$APP_DIR/logs
mkdir -p $LOG_DIR

# Kill any existing instances
pkill -f 'python server.py' 2>/dev/null
pkill -f 'python.*serve-frontend.py' 2>/dev/null
sleep 1

# Source env
set -a
source $APP_DIR/.env 2>/dev/null
set +a

# Start backend
cd $APP_DIR/backend/local
nohup $APP_DIR/.venv/bin/python server.py > $LOG_DIR/backend.log 2>&1 &
echo "Backend PID: $!"

# Start frontend
cd $APP_DIR
nohup $APP_DIR/.venv/bin/python serve-frontend.py > $LOG_DIR/frontend.log 2>&1 &
echo "Frontend PID: $!"

echo ""
echo "Backend:  http://localhost:5001"
echo "Frontend: http://$(hostname):8080"
echo ""
echo "Logs: tail -f $LOG_DIR/backend.log"
echo "Stop: pkill -f 'python server.py'; pkill -f 'serve-frontend.py'"
