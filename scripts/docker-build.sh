#!/bin/bash
# Build all Docker images for the news app

set -e

export DOCKER_BUILDKIT=1

if ! docker buildx version >/dev/null 2>&1; then
    echo "❌ docker buildx is not available. Install Buildx or update Docker Desktop before running this script."
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

echo "🏗️  Building Docker images for News App"
echo "======================================"

# Function to build images with progress
build_image() {
    local dockerfile=$1
    local tag=$2
    local description=$3
    
    echo ""
    echo "Building $description..."
    echo "Dockerfile: $dockerfile"
    echo "Tag: $tag"
    
    local build_args=(
        --load
        --file "$dockerfile"
        --tag "$tag"
        --build-arg BUILDKIT_INLINE_CACHE=1
    )

    if docker buildx build "${build_args[@]}" .; then
        echo "✅ Successfully built $tag"
    else
        echo "❌ Failed to build $tag"
        exit 1
    fi
}

# Build service images
build_image "Dockerfile.server" "news-app:server" "FastAPI server image"
build_image "Dockerfile.workers" "news-app:workers" "task workers image"
build_image "Dockerfile.scrapers" "news-app:scrapers" "content scrapers image with cron"

echo ""
echo "🎉 All Docker images built successfully!"
echo ""
echo "Available images:"
docker images | grep -E "news-app:(server|workers|scrapers)"

echo ""
echo "Next steps:"
echo "1. Configure .env.docker with your settings"
echo "2. Run: ./scripts/docker-up.sh"
echo ""
echo "To rebuild after code changes:"
echo "./scripts/docker-build.sh"
