#!/bin/bash
# deploy.sh - One-command universal deployment
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Universal Media Resolver v2.1${NC}"
echo "======================================"

check_prereqs() {
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        echo "Install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Check Docker Compose (v1 or v2)
    if ! command -v docker-compose &> /dev/null; then
        if ! docker compose version &> /dev/null; then
            echo -e "${YELLOW}⚠️  Docker Compose not found${NC}"
            echo "Install Docker Compose: https://docs.docker.com/compose/install/"
            exit 1
        else
            echo -e "${GREEN}✅ Docker Compose v2 available${NC}"
        fi
    else
        echo -e "${GREEN}✅ Docker Compose v1 available${NC}"
    fi
    
    echo -e "${GREEN}✅ Prerequisites satisfied${NC}"
}

setup_environment() {
    echo -e "${YELLOW}📝 Setting up environment...${NC}"
    
    # Create directories
    mkdir -p ./{data,logs,cache,ssl,nginx}
    
    # Create .env if missing
    if [ ! -f .env ]; then
        echo -e "${YELLOW}📄 Creating .env file...${NC}"
        cp .env.example .env
        
        # Generate JWT secret
        if command -v openssl &> /dev/null; then
            JWT_SECRET=$(openssl rand -hex 32)
        else
            JWT_SECRET=$(date +%s%N | sha256sum | base64 | head -c 32)
        fi
        
        # Update .env
        sed -i.bak "s|JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" .env
        rm -f .env.bak
        
        echo -e "${GREEN}🔑 Generated JWT secret${NC}"
    fi
    
    # Set permissions (Linux only)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo -e "${YELLOW}🔒 Setting permissions...${NC}"
        sudo chown -R 1000:1000 ./data ./logs ./cache 2>/dev/null || true
        sudo chmod 755 ./data ./logs ./cache
    fi
    
    # Make scripts executable
    chmod +x docker-entrypoint.sh 2>/dev/null || true
}

build_image() {
    echo -e "${YELLOW}🔨 Building Docker image...${NC}"
    
    if [ "${SKIP_BUILD:-false}" != "true" ]; then
        DOCKER_BUILDKIT=1 docker build \
            --tag media-resolver:latest \
            --tag media-resolver:$(date +%Y%m%d) \
            --build-arg BUILDKIT_INLINE_CACHE=1 \
            .
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Image built successfully${NC}"
        else
            echo -e "${RED}❌ Image build failed${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⏭️  Skipping build${NC}"
    fi
}

start_services() {
    echo -e "${YELLOW}🚀 Starting services...${NC}"
    
    # Stop existing
    docker-compose down 2>/dev/null || true
    
    # Start
    docker-compose up -d
    
    # Wait for health
    echo -e "${YELLOW}⏳ Waiting for services...${NC}"
    
    MAX_WAIT=60
    WAITED=0
    while [ $WAITED -lt $MAX_WAIT ]; do
        if curl -s http://localhost:${HOST_PORT:-8000}/health 2>/dev/null | grep -q healthy; then
            echo -e "${GREEN}✅ Services are healthy${NC}"
            break
        fi
        
        echo -n "."
        sleep 2
        WAITED=$((WAITED + 2))
    done
    
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo -e "${RED}❌ Services took too long to start${NC}"
        docker-compose logs
        exit 1
    fi
}

show_status() {
    echo -e "${GREEN}🎉 Deployment complete!${NC}"
    echo ""
    echo "================================"
    echo "🌐 Access Information"
    echo "================================"
    
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP="localhost"
    fi
    
    echo "Local:      http://localhost:${HOST_PORT:-8000}"
    echo "Network:    http://${LOCAL_IP}:${HOST_PORT:-8000}"
    echo "API Docs:   http://localhost:${HOST_PORT:-8000}/docs"
    echo "Health:     http://localhost:${HOST_PORT:-8000}/health"
    
    echo ""
    echo "================================"
    echo "🔧 Useful Commands"
    echo "================================"
    echo "View logs:    docker-compose logs -f"
    echo "Stop:         docker-compose down"
    echo "Restart:      docker-compose restart"
    echo "Shell:        docker-compose exec media-resolver bash"
    echo "Update:       SKIP_BUILD=false ./deploy.sh"
    echo ""
    echo -e "${YELLOW}⚠️  First run may take longer as caches are built${NC}"
}

main() {
    check_prereqs
    setup_environment
    build_image
    start_services
    show_status
}

case "${1:-}" in
    "clean")
        echo -e "${YELLOW}🧹 Cleaning up...${NC}"
        docker-compose down -v --remove-orphans
        docker system prune -f
        echo -e "${GREEN}✅ Cleanup complete${NC}"
        ;;
    "update")
        echo -e "${YELLOW}🔄 Updating...${NC}"
        SKIP_BUILD=false ./deploy.sh
        ;;
    "logs")
        docker-compose logs -f
        ;;
    "status")
        docker-compose ps
        ;;
    "help")
        echo "Usage: ./deploy.sh [command]"
        echo ""
        echo "Commands:"
        echo "  (none)    Deploy/update services"
        echo "  clean     Remove all containers and data"
        echo "  update    Rebuild and restart"
        echo "  logs      View service logs"
        echo "  status    Show service status"
        echo "  help      Show this help"
        ;;
    *)
        main
        ;;
esac