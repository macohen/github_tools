#!/bin/bash
set -e

echo "=== PR Tracker Lightsail Deployment ==="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3.11
echo "Installing Python..."
sudo apt-get install -y python3.11 python3.11-venv python3-pip

# Install Node.js 18
echo "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install nginx
echo "Installing nginx..."
sudo apt-get install -y nginx

# Create app directory
echo "Setting up application directory..."
sudo mkdir -p /opt/pr-tracker
sudo chown $USER:$USER /opt/pr-tracker
cd /opt/pr-tracker

# Clone repository (you'll need to set this up)
echo "Clone your repository manually:"
echo "  git clone <your-repo-url> ."
echo ""
echo "Then run: bash deploy/lightsail-install.sh"
