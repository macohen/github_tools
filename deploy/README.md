# AWS Lightsail Deployment Guide

This guide walks you through deploying the PR Tracker application to AWS Lightsail from your cloud desktop.

## Prerequisites

- AWS account with Lightsail access
- AWS CLI configured on your cloud desktop
- GitHub repository with your code pushed

## Step 1: Create Lightsail Instance

### Option A: Using AWS Console (Recommended)

1. Go to https://lightsail.aws.amazon.com/
2. Click "Create instance"
3. Select:
   - Platform: Linux/Unix
   - Blueprint: Ubuntu 22.04 LTS
   - Instance plan: $5/month (1 GB RAM, 1 vCPU, 40 GB SSD)
4. Name your instance: `pr-tracker`
5. Click "Create instance"
6. Wait for instance to be running (takes ~2 minutes)

### Option B: Using AWS CLI

```bash
aws lightsail create-instances \
  --instance-names pr-tracker \
  --availability-zone us-west-2a \
  --blueprint-id ubuntu_22_04 \
  --bundle-id nano_2_0
```

## Step 2: Configure Networking

1. In Lightsail console, click on your instance
2. Go to "Networking" tab
3. Under "IPv4 Firewall", add rules:
   - HTTP (port 80) - Allow from anywhere
   - HTTPS (port 443) - Allow from anywhere (for future SSL)
   - SSH (port 22) - Already configured

## Step 3: Connect and Deploy

### Connect to Instance

From Lightsail console:
- Click "Connect using SSH" button (opens browser terminal)

Or from your cloud desktop:
```bash
# Download SSH key from Lightsail console first
ssh -i LightsailDefaultKey-us-west-2.pem ubuntu@<your-instance-ip>
```

### Run Deployment

```bash
# 1. Download setup script
curl -O https://raw.githubusercontent.com/<your-username>/<your-repo>/main/deploy/lightsail-setup.sh
chmod +x lightsail-setup.sh
./lightsail-setup.sh

# 2. Clone your repository
sudo mkdir -p /opt/pr-tracker
sudo chown ubuntu:ubuntu /opt/pr-tracker
cd /opt/pr-tracker
git clone https://github.com/<your-username>/<your-repo>.git .

# 3. Run installation
chmod +x deploy/lightsail-install.sh
./deploy/lightsail-install.sh

# 4. Configure environment
nano .env
# Add your GITHUB_TOKEN and save (Ctrl+X, Y, Enter)

# 5. Restart backend
sudo systemctl restart pr-tracker-backend

# 6. Check status
sudo systemctl status pr-tracker-backend
```

## Step 4: Access Your Application

1. Get your instance's public IP from Lightsail console
2. Open browser: `http://<your-instance-ip>`
3. You should see the PR Tracker dashboard!

## Management Commands

### Check Backend Status
```bash
sudo systemctl status pr-tracker-backend
```

### View Backend Logs
```bash
sudo journalctl -u pr-tracker-backend -f
```

### Restart Backend
```bash
sudo systemctl restart pr-tracker-backend
```

### Check Nginx Status
```bash
sudo systemctl status nginx
```

### View Nginx Logs
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## Updating the Application

```bash
cd /opt/pr-tracker
git pull origin main

# Rebuild frontend
cd frontend
npm install
npm run build
cd ..

# Restart backend
sudo systemctl restart pr-tracker-backend
```

## Setting Up Automated Data Collection

Add a cron job to collect PR data every 6 hours:

```bash
crontab -e
```

Add this line:
```
0 */6 * * * cd /opt/pr-tracker && /opt/pr-tracker/.venv/bin/python track_open_prs.py --store >> /var/log/pr-tracker-cron.log 2>&1
```

## Adding SSL/HTTPS (Optional)

### Using Lightsail Load Balancer

1. In Lightsail console, create a Load Balancer
2. Attach your instance to the load balancer
3. Request SSL certificate through Lightsail
4. Update DNS to point to load balancer

Cost: Additional $18/month

### Using Let's Encrypt (Free)

```bash
# Install certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Get certificate (requires domain name)
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured automatically
```

## Troubleshooting

### Backend won't start
```bash
# Check logs
sudo journalctl -u pr-tracker-backend -n 50

# Check if port 5001 is in use
sudo lsof -i :5001

# Verify environment variables
cat /opt/pr-tracker/.env
```

### Frontend shows blank page
```bash
# Check if build exists
ls -la /opt/pr-tracker/frontend/dist

# Rebuild frontend
cd /opt/pr-tracker/frontend
npm run build

# Check nginx config
sudo nginx -t
```

### Database errors
```bash
# Check database file permissions
ls -la /opt/pr-tracker/backend/local/pr_tracker.duckdb

# Fix permissions if needed
sudo chown ubuntu:ubuntu /opt/pr-tracker/backend/local/pr_tracker.duckdb
```

## Cost Estimate

- Lightsail instance: $5/month
- Data transfer: First 1TB free, then $0.09/GB
- Backups (optional): $1/month for 7-day retention

**Total: ~$5-6/month**

## Backup Strategy

### Manual Backup
```bash
# Backup database
cp /opt/pr-tracker/backend/local/pr_tracker.duckdb ~/pr_tracker_backup_$(date +%Y%m%d).duckdb

# Download to your cloud desktop
scp ubuntu@<instance-ip>:~/pr_tracker_backup_*.duckdb .
```

### Automatic Snapshots
1. In Lightsail console, go to "Snapshots" tab
2. Enable automatic snapshots (free for first 7 days)
3. Configure retention period

## Monitoring

### Set up CloudWatch (Optional)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb
```

### Simple Uptime Monitoring

Use Lightsail's built-in metrics:
1. Go to instance → Metrics tab
2. View CPU, network, and status check metrics
3. Set up metric alarms for notifications

## Security Hardening

1. **Update regularly**:
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

2. **Configure firewall**:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

3. **Disable root login**:
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PermitRootLogin no
   sudo systemctl restart sshd
   ```

4. **Keep secrets secure**:
   - Never commit `.env` file
   - Rotate GitHub tokens regularly
   - Use read-only tokens when possible

## Support

For issues or questions:
1. Check logs: `sudo journalctl -u pr-tracker-backend -f`
2. Review nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Verify environment: `cat /opt/pr-tracker/.env`
