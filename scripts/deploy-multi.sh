#!/bin/bash

# Multi-Service Docker Deployment Script
# Deploys Server, Workers, and Scrapers containers to remote Linux host
# Usage: ./deploy-multi.sh [--deploy-only]

set -euo pipefail

export DOCKER_BUILDKIT=1

if ! docker buildx version >/dev/null 2>&1; then
  echo "$(date +'%Y-%m-%d %H:%M:%S') docker buildx is not available. Install Buildx or update Docker before running this script." >&2
  exit 1
fi

# Lenient .env loader that doesn't "source" the file
# and supports values with spaces, parentheses, and quotes.
load_env_file() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi
  log "Loading environment variables from .env file..."
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Trim leading/trailing whitespace
    line="${line#${line%%[![:space:]]*}}"  # ltrim
    line="${line%${line##*[![:space:]]}}"  # rtrim
    # Skip blank lines and comments
    [[ -z "$line" || ${line:0:1} == '#' ]] && continue
    # Remove optional 'export '
    [[ "$line" == export* ]] && line="${line#export }"
    # Match KEY=VALUE (keep everything after first '=')
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local value="${BASH_REMATCH[2]}"
      # Strip surrounding single or double quotes, if present
      if [[ "$value" =~ ^"(.*)"$ ]]; then value="${BASH_REMATCH[1]}"; fi
      if [[ "$value" =~ ^'(.*)'$ ]]; then value="${BASH_REMATCH[1]}"; fi
      # Export without evaluation/expansion
      printf -v "$key" '%s' "$value"
      export "$key"
    else
      warn "Skipping unparsable .env line: $line"
    fi
  done < "$env_file"
}

# Parse command line arguments
DEPLOY_ONLY=false
CLEANUP_AFTER=false   # keep temp files by default
while [[ $# -gt 0 ]]; do
  case $1 in
    --deploy-only)
      DEPLOY_ONLY=true
      shift
      ;;
    --cleanup)
      CLEANUP_AFTER=true
      shift
      ;;
    --no-cleanup)
      CLEANUP_AFTER=false
      shift
      ;;
    *)
      echo "Unknown option $1"
      echo "Usage: $0 [--deploy-only] [--cleanup|--no-cleanup]"
      exit 1
      ;;
  esac
done

# Configuration
REMOTE_HOST="192.3.250.10"
REMOTE_USER="willem"  # Updated from root
REMOTE_DATA_DIR="/data"
REMOTE_DOCKER_DIR="/data/docker"
LOCAL_TEMP_DIR="/tmp/docker-deploy"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Service definitions
SERVICES="server workers scrapers"
IMAGE_TAG="latest"
ENV_FILE_NAME="deploy.env"

# Load environment variables from .env file (lenient parser)
if [[ -f .env ]]; then
    load_env_file ".env"
else
    warn "No .env file found. Environment variables may not be set correctly."
fi

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
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

# Build base image and all service images
build_images() {
    for service in ${SERVICES}; do
        local image_name="newsly-${service}"
        local dockerfile="Dockerfile.${service}"
        
        info "Building ${service} service image for AMD64: ${image_name}:${IMAGE_TAG}"
        if ! docker buildx build \
            --platform linux/amd64 \
            --load \
            --file "${dockerfile}" \
            --tag "${image_name}:${IMAGE_TAG}" \
            --build-arg BUILDKIT_INLINE_CACHE=1 \
            .; then
            error "Failed to build ${service} Docker image"
        fi
    done
}

# Save all Docker images to tar files
save_images() {
    log "Saving Docker images to tar archives..."
    mkdir -p "${LOCAL_TEMP_DIR}"
    
    # Save service images
    for service in ${SERVICES}; do
        local image_name="newsly-${service}"
        local image_file="${LOCAL_TEMP_DIR}/${image_name}-${IMAGE_TAG}.tar"
        
        if ! docker save -o "${image_file}" "${image_name}:${IMAGE_TAG}"; then
            error "Failed to save ${service} Docker image"
        fi
        info "${service} image saved to: ${image_file}"
    done
}

# Setup remote directories
setup_remote_dirs() {
    log "Setting up remote directories on ${REMOTE_HOST}..."
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "
        mkdir -p ${REMOTE_DOCKER_DIR}
        mkdir -p ${REMOTE_DATA_DIR}/logs
        ls -la ${REMOTE_DATA_DIR}
    " || error "Failed to setup remote directories"
}

# Create and transfer an env-file with selected variables
write_env_file() {
    log "Preparing env file for remote containers..."
    mkdir -p "${LOCAL_TEMP_DIR}"

    local env_path="${LOCAL_TEMP_DIR}/${ENV_FILE_NAME}"
    : > "$env_path"

    # Whitelist of variables to export to the containers
    local KEYS=(
        GOOGLE_API_KEY
        OPENAI_API_KEY
        FIRECRAWL_API_KEY
        REDDIT_CLIENT_ID
        REDDIT_CLIENT_SECRET
        REDDIT_USER_AGENT
        LOG_LEVEL
        USE_LOCAL_WHISPER
        WHISPER_MODEL_SIZE
        WHISPER_DEVICE
    )

    for key in "${KEYS[@]}"; do
        # Only write keys that are set in the environment
        if [[ -n "${!key-}" ]]; then
            # Write as KEY=VALUE without additional quoting
            printf '%s=%s\n' "$key" "${!key}" >> "$env_path"
        fi
    done

    info "Env file written to: $env_path"
}

transfer_env_file() {
    log "Transferring env file to remote host..."
    local env_path="${LOCAL_TEMP_DIR}/${ENV_FILE_NAME}"
    if [[ ! -f "$env_path" ]]; then
        error "Env file not found at $env_path"
    fi
    scp "$env_path" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DOCKER_DIR}/${ENV_FILE_NAME}" \
        || error "Failed to transfer env file"
}

# Transfer all images to remote host
transfer_images() {
    log "Transferring all images to ${REMOTE_HOST} in single command..."
    
    # Transfer all images at once
    if ! scp "${LOCAL_TEMP_DIR}"/*.tar "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DOCKER_DIR}/"; then
        error "Failed to transfer image files"
    fi
    
    info "All images transferred successfully"
}

# Deploy containers on remote host
deploy_containers() {
    log "Deploying containers on remote host..."
    
    ssh -t "${REMOTE_USER}@${REMOTE_HOST}" '
        set -e
        
        # Load service images
        echo "Loading server Docker image..."
        sudo docker load -i /data/docker/newsly-server-latest.tar || exit 1
        echo "Loading workers Docker image..."
        sudo docker load -i /data/docker/newsly-workers-latest.tar || exit 1
        echo "Loading scrapers Docker image..."
        sudo docker load -i /data/docker/newsly-scrapers-latest.tar || exit 1
        
        # Verify env file exists on remote
        ENV_FILE=/data/docker/deploy.env
        if [[ ! -s "$ENV_FILE" ]]; then
            echo "Env file missing or empty at $ENV_FILE"
            ls -l /data/docker || true
            exit 1
        fi
        
        # Stop and remove existing containers (handle name conflicts robustly)
        for container in newsly-server newsly-workers newsly-scrapers; do
            # Find exact-name matches only (avoid partial matches)
            CID=$(sudo docker ps -aq --filter "name=^/${container}$")
            if [[ -n "$CID" ]]; then
                echo "Removing existing $container container ($CID)..."
                # Force remove to handle running, dead, or stuck states
                sudo docker rm -f "$CID" || true
            fi
        done
        
        # Start server container
        echo "Starting server container..."
        if ! sudo docker run -d \
            --name newsly-server \
            --restart unless-stopped \
            -p 8000:8000 \
            -v /data:/data \
            -v /data/logs:/logs \
            --env-file /data/docker/deploy.env \
            -e PYTHONPATH=/app \
            -e SERVICE_TYPE=server \
            -e DATABASE_URL=sqlite:////data/news_app.db \
            newsly-server:latest; then
            echo "Server failed to start; cleaning up and showing last logs..."
            sudo docker logs --tail 200 newsly-server || true
            sudo docker rm -f newsly-server || true
            exit 1
        fi
            
        # Start workers container
        echo "Starting workers container..."
        if ! sudo docker run -d \
            --name newsly-workers \
            --restart unless-stopped \
            -v /data:/data \
            -v /data/logs:/logs \
            --env-file /data/docker/deploy.env \
            -e PYTHONPATH=/app \
            -e SERVICE_TYPE=workers \
            -e DATABASE_URL=sqlite:////data/news_app.db \
            newsly-workers:latest; then
            echo "Workers failed to start; cleaning up and showing last logs..."
            sudo docker logs --tail 200 newsly-workers || true
            sudo docker rm -f newsly-workers || true
            exit 1
        fi
            
        # Start scrapers container  
        echo "Starting scrapers container..."
        if ! sudo docker run -d \
            --name newsly-scrapers \
            --restart unless-stopped \
            -v /data:/data \
            -v /data/logs:/logs \
            --env-file /data/docker/deploy.env \
            -e PYTHONPATH=/app \
            -e SERVICE_TYPE=scrapers \
            -e DATABASE_URL=sqlite:////data/news_app.db \
            -e SCRAPER_CRON_SCHEDULE="0 */4 * * *" \
            -e SCRAPER_RUN_ON_START=true \
            newsly-scrapers:latest; then
            echo "Scrapers failed to start; cleaning up and showing last logs..."
            sudo docker logs --tail 200 newsly-scrapers || true
            sudo docker rm -f newsly-scrapers || true
            exit 1
        fi
            
        echo "All containers started successfully!"
        
        # Show container status
        sudo docker ps --filter name=newsly-
        
        # Do not remove transferred image files on the server
        echo "Leaving transferred image .tar files in /data/docker (remote cleanup disabled)."
    ' || error "Failed to deploy containers on remote host"
}

# Cleanup local temp files (optional)
cleanup() {
    if [[ "${CLEANUP_AFTER}" == "true" ]]; then
        log "Cleaning up temporary files..."
        rm -rf "${LOCAL_TEMP_DIR}"
    else
        log "Skipping cleanup of temporary files (requested)."
    fi
}

# Main deployment function
main() {
    if [[ "$DEPLOY_ONLY" == "true" ]]; then
        log "Starting deploy-only mode to ${REMOTE_HOST}..."
        # Ensure remote dirs and env file exist for deploy-only
        setup_remote_dirs
        write_env_file
        transfer_env_file
        deploy_containers
        log "Deploy-only completed successfully!"
    else
        log "Starting full multi-service deployment to ${REMOTE_HOST}..."
        
        # Check prerequisites
        check_docker
        
        # Build and save images
        build_images
        save_images
        
        # Setup remote environment
        setup_remote_dirs
        
        # Prepare env file
        write_env_file
        transfer_env_file

        # Transfer and deploy
        transfer_images
        deploy_containers
        
        # Cleanup (optional)
        cleanup
        
        log "Multi-service deployment completed successfully!"
    fi
    
    log "Services available:"
    log "  - Server: http://${REMOTE_HOST}:8000"
    log "  - Workers: Running in background"
    log "  - Scrapers: Running on cron schedule (every 4 hours)"
}

# Handle script interruption
trap cleanup EXIT

# Run main function
main "$@"
