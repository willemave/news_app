#!/bin/bash
# Stop all Docker services for the news app

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

echo "🛑 Stopping News App Docker Services"
echo "===================================="

# Parse command line arguments
REMOVE_VOLUMES=false
REMOVE_IMAGES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --remove-volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        --remove-images)
            REMOVE_IMAGES=true
            shift
            ;;
        --clean-all)
            REMOVE_VOLUMES=true
            REMOVE_IMAGES=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --remove-volumes    Remove data volumes (WARNING: deletes database!)"
            echo "  --remove-images     Remove Docker images"
            echo "  --clean-all         Remove both volumes and images"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

# Show current service status
echo "📊 Current service status:"
docker-compose ps

# Stop and remove containers
echo ""
echo "⏹️  Stopping services..."
docker-compose down

echo "✅ Services stopped"

# Remove volumes if requested
if [ "$REMOVE_VOLUMES" = true ]; then
    echo ""
    echo "⚠️  WARNING: Removing volumes will delete all data including the database!"
    echo "This action cannot be undone."
    echo ""
    read -p "Are you sure you want to remove volumes? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing volumes..."
        docker-compose down -v
        # Also remove local data directory contents
        if [ -d "data" ]; then
            echo "Removing local data directory contents..."
            rm -rf data/*
        fi
        if [ -d "logs" ]; then
            echo "Removing local logs directory contents..."
            rm -rf logs/*
        fi
        echo "✅ Volumes removed"
    else
        echo "❌ Volume removal cancelled"
    fi
fi

# Remove images if requested
if [ "$REMOVE_IMAGES" = true ]; then
    echo ""
    echo "🗑️  Removing Docker images..."
    
    # Remove service images
    for image in news-app:server news-app:workers news-app:scrapers; do
        if docker image inspect "$image" >/dev/null 2>&1; then
            echo "Removing $image..."
            docker rmi "$image" || echo "Failed to remove $image"
        fi
    done
    
    echo "✅ Images removed"
fi

# Clean up orphaned containers and networks
echo ""
echo "🧹 Cleaning up..."
docker system prune -f >/dev/null 2>&1

echo ""
echo "✅ All services stopped successfully!"

# Show final status
if [ "$REMOVE_VOLUMES" = false ] && [ "$REMOVE_IMAGES" = false ]; then
    echo ""
    echo "💡 Tips:"
    echo "  - Data and logs are preserved in ./data and ./logs"
    echo "  - Restart with: ./scripts/docker-up.sh"
    echo "  - To remove all data: $0 --remove-volumes"
    echo "  - To remove images: $0 --remove-images"
    echo "  - To clean everything: $0 --clean-all"
fi
