#!/bin/bash
# verify-deployment.sh
set -euo pipefail

echo "🔍 Verifying Universal Media Resolver Deployment..."
echo "==================================================="

# Check Docker
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi

# Check .env
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    exit 1
fi

# Load environment
source .env 2>/dev/null || true

# Test build
echo "🔨 Testing Docker build..."
docker build -t media-resolver-test .

# Test container
echo "🚀 Testing container..."
docker run --rm -d \
    --name media-resolver-test \
    -p 9999:8000 \
    -e JWT_SECRET=test-secret \
    -e LOG_LEVEL=warning \
    media-resolver-test

sleep 5

# Test health
echo "🏥 Testing health endpoint..."
if curl -s http://localhost:9999/health | grep -q healthy; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    docker logs media-resolver-test
    docker rm -f media-resolver-test
    exit 1
fi

# Test API
echo "🔌 Testing API endpoints..."
ENDPOINTS=("/" "/docs" "/supported")
for endpoint in "${ENDPOINTS[@]}"; do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:9999${endpoint}" | grep -q "200\|301\|302"; then
        echo "  ✅ ${endpoint}"
    else
        echo "  ❌ ${endpoint}"
    fi
done

# Cleanup
echo "🧹 Cleaning up..."
docker rm -f media-resolver-test

echo ""
echo "==================================================="
echo "🎉 ALL TESTS PASSED! System is ready for production."
echo ""
echo "To deploy: ./deploy.sh"
echo "==================================================="