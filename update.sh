#!/bin/bash
# CloudDate — One-click update script
# Usage: bash update.sh

set -e

echo "🔄 Updating CloudDate..."

# Pull latest code
echo "📥 Pulling latest changes..."
git pull origin main

# Rebuild and restart
echo "🐳 Rebuilding Docker image..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo ""
echo "✅ CloudDate updated successfully!"
echo "🌐 Dashboard: http://$(hostname -I | awk '{print $1}'):${PORT:-5001}"
docker compose logs --tail=5
