#!/bin/bash
# Quick deployment script for Google OAuth fix
# Run this on demo.echomind.ch server

set -e

echo "🔧 Deploying Google OAuth fix to demo.echomind.ch..."

cd /root/echo-mind

echo "📥 Pulling latest changes..."
git fetch origin
git checkout feature/issue-4-test-google-connector
git pull origin feature/issue-4-test-google-connector

echo "🔄 Rebuilding API service..."
cd deployment/docker-cluster
docker compose -f docker-compose.yml -f docker-compose-host.yml up -d --build --force-recreate api

echo "⏳ Waiting 10 seconds for API to start..."
sleep 10

echo "✅ Verifying Google OAuth configuration..."
RESULT=$(curl -s https://demo.echomind.ch/api/v1/google/auth/configured | jq -r '.configured')

if [ "$RESULT" = "true" ]; then
    echo "✅ SUCCESS! Google OAuth is now configured!"
    curl -s https://demo.echomind.ch/api/v1/google/auth/configured | jq
else
    echo "❌ FAILED! Still not configured. Checking logs..."
    docker logs echomind-api --tail 50 | grep -i google
    exit 1
fi

echo ""
echo "🎉 Deployment complete! You can now:"
echo "   1. Go to https://demo.echomind.ch"
echo "   2. Navigate to Workspace > Connectors"
echo "   3. Add a Google Drive connector"
echo "   4. Click 'Connect to Google' - OAuth should work!"
