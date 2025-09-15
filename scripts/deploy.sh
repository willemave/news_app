#!/bin/bash

# Docker Deployment Script
# Deploys Docker containers to remote Linux host at 192.3.250.10

set -e

# Configuration
REMOTE_HOST="192.3.250.10"
REMOTE_USER="root"  # Change this to your username
REMOTE_DATA_DIR="/data"
REMOTE_DOCKER_DIR="/data/docker"
LOCAL_TEMP_DIR="/tmp/docker-deploy"
IMAGE_NAME="newsly-app"
IMAGE_TAG="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if Docker is running locally
check_docker() {
    log "Checking Docker status..."
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running locally. Please start Docker first."
    fi
}

# Build the Docker images
build_image() {
    log "Building server Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
    if ! docker build -f Dockerfile.server -t "${IMAGE_NAME}:${IMAGE_TAG}" .; then
        error "Failed to build server Docker image"
    fi
}

# Save Docker image to tar file
save_image() {
    log "Saving Docker image to tar archive..."
    mkdir -p "${LOCAL_TEMP_DIR}"
    local image_file="${LOCAL_TEMP_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar"
    
    if ! docker save -o "${image_file}" "${IMAGE_NAME}:${IMAGE_TAG}"; then
        error "Failed to save Docker image"
    fi
    
    log "Image saved to: ${image_file}"
    echo "${image_file}"
}

# Setup remote directories
setup_remote_dirs() {
    log "Setting up remote directories on ${REMOTE_HOST}..."
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "
        sudo mkdir -p ${REMOTE_DATA_DIR}
        sudo mkdir -p ${REMOTE_DOCKER_DIR}
        sudo chown -R \$(whoami):\$(whoami) ${REMOTE_DATA_DIR}
    " || error "Failed to setup remote directories"
}

# Transfer image to remote host
transfer_image() {
    local image_file="$1"
    local remote_image_file="${REMOTE_DOCKER_DIR}/$(basename ${image_file})"
    
    log "Transferring image to ${REMOTE_HOST}:${remote_image_file}..."
    if ! scp "${image_file}" "${REMOTE_USER}@${REMOTE_HOST}:${remote_image_file}"; then
        error "Failed to transfer image file"
    fi
    
    echo "${remote_image_file}"
}

# Load and run Docker container on remote host
deploy_container() {
    local remote_image_file="$1"
    
    log "Loading Docker image on remote host..."
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "
        # Load the Docker image
        docker load -i '${remote_image_file}' || exit 1
        
        # Stop existing container if running
        if docker ps -q --filter name=${IMAGE_NAME} | grep -q .; then
            echo 'Stopping existing container...'
            docker stop ${IMAGE_NAME} || true
        fi
        
        # Remove existing container if exists
        if docker ps -aq --filter name=${IMAGE_NAME} | grep -q .; then
            echo 'Removing existing container...'
            docker rm ${IMAGE_NAME} || true
        fi
        
        # Run the new container
        echo 'Starting new container...'
        docker run -d \
            --name ${IMAGE_NAME} \
            --restart unless-stopped \
            -p 8000:8000 \
            -v ${REMOTE_DATA_DIR}:/app/data \
            -v ${REMOTE_DATA_DIR}/logs:/app/logs \
            -e DATABASE_URL=sqlite:////app/data/news_app.db \
            ${IMAGE_NAME}:${IMAGE_TAG} || exit 1
            
        echo 'Container started successfully!'
        
        # Show container status
        docker ps --filter name=${IMAGE_NAME}
        
        # Clean up the image file
        rm -f '${remote_image_file}'
    " || error "Failed to deploy container on remote host"
}

# Cleanup local temp files
cleanup() {
    log "Cleaning up temporary files..."
    rm -rf "${LOCAL_TEMP_DIR}"
}

# Main deployment function
main() {
    log "Starting deployment to ${REMOTE_HOST}..."
    
    # Check prerequisites
    check_docker
    
    # Build and save image
    build_image
    local image_file
    image_file=$(save_image)
    
    # Setup remote environment
    setup_remote_dirs
    
    # Transfer and deploy
    local remote_image_file
    remote_image_file=$(transfer_image "${image_file}")
    deploy_container "${remote_image_file}"
    
    # Cleanup
    cleanup
    
    log "Deployment completed successfully!"
    log "Your application should be available at http://${REMOTE_HOST}:8000"
}

# Handle script interruption
trap cleanup EXIT

# Run main function
main "$@"
