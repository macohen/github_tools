#!/bin/bash
set -e

echo "=== Installing PR Tracker Application ==="

# Ensure we're in the right directory
cd /opt/pr-tracker

# Set up Python backend
echo "Setting up Python backend..."
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

# Build frontend
echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Create environment file
echo "Creating environment file..."
cat > .env << 'EOF'
GITHUB_TOKEN=your_token_here
GITHUB_REPO_OWNER=awslabs
GITHUB_REPO_NAME=aws-athena-query-federation
DB_PATH=/opt/pr-tracker/backend/local/pr_tracker.duckdb
API_URL=http://localhost:5001/api
EOF

echo ""
echo "⚠️  IMPORTANT: Edit /opt/pr-tracker/.env and add your GITHUB_TOKEN"
echo ""

# Create systemd service for backend
echo "Creating systemd service..."
sudo tee /etc/systemd/system/pr-tracker-backend.service > /dev/null << 'EOF'
[Unit]
Description=PR Tracker Backend API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/pr-tracker/backend/local
Environment="PATH=/opt/pr-tracker/.venv/bin"
EnvironmentFile=/opt/pr-tracker/.env
ExecStart=/opt/pr-tracker/.venv/bin/python server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure nginx
echo "Configuring nginx..."
sudo tee /etc/nginx/sites-available/pr-tracker > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    # Frontend - serve static files
    location / {
        root /opt/pr-tracker/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API - proxy to Flask
    location /api {
        proxy_pass http://localhost:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/pr-tracker /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx config
sudo nginx -t

# Start services
echo "Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable pr-tracker-backend
sudo systemctl start pr-tracker-backend
sudo systemctl restart nginx

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "Next steps:"
echo "1. Edit /opt/pr-tracker/.env and add your GITHUB_TOKEN"
echo "2. Restart backend: sudo systemctl restart pr-tracker-backend"
echo "3. Check status: sudo systemctl status pr-tracker-backend"
echo "4. View logs: sudo journalctl -u pr-tracker-backend -f"
echo ""
echo "Your app will be available at: http://<your-lightsail-ip>"
echo ""
