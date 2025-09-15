#!/bin/bash
# Start all Docker services for the news app

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

echo "🚀 Starting News App Docker Services"
echo "==================================="

# Check if .env.docker exists
if [ ! -f ".env.docker" ]; then
    echo "❌ .env.docker file not found!"
    echo ""
    echo "Please create .env.docker with your configuration:"
    echo "cp .env.docker.example .env.docker"
    echo "# Then edit .env.docker with your settings"
    exit 1
fi

# Create data and logs directories if they don't exist
echo "📁 Creating data and logs directories..."
mkdir -p data logs
echo "✅ Directories ready"

# Check if images exist, build if necessary
echo ""
echo "🔍 Checking Docker images..."
missing=false
for img in news-app:server news-app:workers news-app:scrapers; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    missing=true
    break
  fi
done

if [ "$missing" = true ]; then
  echo "❌ One or more Docker images not found. Building them first..."
  ./scripts/docker-build.sh
else
  echo "✅ Docker images found"
fi

# Start services with docker-compose
echo ""
echo "🏁 Starting services with docker-compose..."
docker-compose up -d

# Wait a moment for services to start
echo ""
echo "⏳ Waiting for services to initialize..."
sleep 10

# Show service status
echo ""
echo "📊 Service Status:"
docker-compose ps

# Show logs briefly
echo ""
echo "📝 Recent logs:"
echo "=============="
docker-compose logs --tail=20

# Health check information
echo ""
echo "🔍 Health Check URLs:"
echo "  - Server: http://localhost:8000/health"
echo "  - Admin: http://localhost:8000/admin"
echo ""

# Show useful commands
echo "📋 Useful commands:"
echo "  - View all logs: docker-compose logs -f"
echo "  - View server logs: docker-compose logs -f server"
echo "  - View worker logs: docker-compose logs -f workers"
echo "  - View scraper logs: docker-compose logs -f scrapers"
echo "  - Stop services: ./scripts/docker-down.sh"
echo "  - Restart single service: docker-compose restart <service>"
echo ""

# Manual scraper trigger info
echo "🕒 Scraper scheduling:"
echo "  - Scrapers run automatically every 4 hours (configurable via SCRAPER_CRON_SCHEDULE)"
echo "  - Manual trigger: docker-compose exec scrapers python scripts/run_scrapers.py"
echo ""

echo "✅ All services started successfully!"
