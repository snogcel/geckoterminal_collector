#!/bin/bash

# GeckoTerminal Data Collector Deployment Script
# This script handles deployment of the collector in various environments

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION="${VERSION:-latest}"
ENVIRONMENT="${ENVIRONMENT:-production}"
CONFIG_FILE="${CONFIG_FILE:-config.yaml}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
GeckoTerminal Data Collector Deployment Script

Usage: $0 [OPTIONS] COMMAND

Commands:
    build           Build Docker image
    deploy          Deploy the application
    start           Start the services
    stop            Stop the services
    restart         Restart the services
    status          Show service status
    logs            Show service logs
    backup          Create data backup
    restore         Restore from backup
    cleanup         Clean up old resources
    health          Check system health

Options:
    -e, --environment ENV    Deployment environment (default: production)
    -v, --version VERSION    Application version (default: latest)
    -c, --config FILE        Configuration file (default: config.yaml)
    -h, --help              Show this help message

Environment Variables:
    GECKO_DB_URL            Database connection URL
    GECKO_LOG_LEVEL         Logging level (DEBUG, INFO, WARNING, ERROR)
    POSTGRES_PASSWORD       PostgreSQL password (if using PostgreSQL)
    GRAFANA_PASSWORD        Grafana admin password (if using monitoring)

Examples:
    $0 build                           # Build Docker image
    $0 deploy                          # Deploy with default settings
    $0 -e development deploy           # Deploy in development mode
    $0 start --with-monitoring         # Start with monitoring stack
    $0 backup /path/to/backup          # Create backup
    $0 logs --follow                   # Follow logs in real-time

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -v|--version)
                VERSION="$2"
                shift 2
                ;;
            -c|--config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                COMMAND="$1"
                shift
                break
                ;;
        esac
    done
    
    # Store remaining arguments
    ARGS=("$@")
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    # Determine Docker Compose command
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        DOCKER_COMPOSE="docker compose"
    fi
    
    log_success "Prerequisites check passed"
}

# Load environment configuration
load_environment() {
    log_info "Loading environment configuration for: $ENVIRONMENT"
    
    # Load environment-specific configuration
    ENV_FILE="$PROJECT_ROOT/.env.$ENVIRONMENT"
    if [[ -f "$ENV_FILE" ]]; then
        log_info "Loading environment file: $ENV_FILE"
        set -a
        source "$ENV_FILE"
        set +a
    else
        log_warning "Environment file not found: $ENV_FILE"
    fi
    
    # Load default .env file
    DEFAULT_ENV_FILE="$PROJECT_ROOT/.env"
    if [[ -f "$DEFAULT_ENV_FILE" ]]; then
        log_info "Loading default environment file: $DEFAULT_ENV_FILE"
        set -a
        source "$DEFAULT_ENV_FILE"
        set +a
    fi
    
    # Set build metadata
    export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
    export VERSION="$VERSION"
    export VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."
    
    cd "$PROJECT_ROOT"
    
    docker build \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VERSION="$VERSION" \
        --build-arg VCS_REF="$VCS_REF" \
        -t "gecko-terminal-collector:$VERSION" \
        -t "gecko-terminal-collector:latest" \
        .
    
    log_success "Docker image built successfully"
}

# Deploy application
deploy_application() {
    log_info "Deploying GeckoTerminal Data Collector..."
    
    cd "$PROJECT_ROOT"
    
    # Create necessary directories
    mkdir -p data logs backups
    
    # Copy configuration if it doesn't exist
    if [[ ! -f "$CONFIG_FILE" ]]; then
        if [[ -f "config.yaml.example" ]]; then
            log_info "Creating configuration file from example"
            cp config.yaml.example "$CONFIG_FILE"
        else
            log_warning "No configuration file found. Please create $CONFIG_FILE"
        fi
    fi
    
    # Determine which services to start
    PROFILES=""
    if [[ "${WITH_POSTGRES:-false}" == "true" ]]; then
        PROFILES="$PROFILES --profile postgres"
    fi
    if [[ "${WITH_REDIS:-false}" == "true" ]]; then
        PROFILES="$PROFILES --profile redis"
    fi
    if [[ "${WITH_MONITORING:-false}" == "true" ]]; then
        PROFILES="$PROFILES --profile monitoring"
    fi
    
    # Deploy with Docker Compose
    $DOCKER_COMPOSE $PROFILES up -d
    
    log_success "Deployment completed"
}

# Start services
start_services() {
    log_info "Starting services..."
    
    cd "$PROJECT_ROOT"
    
    # Parse additional arguments
    PROFILES=""
    for arg in "${ARGS[@]}"; do
        case $arg in
            --with-postgres)
                PROFILES="$PROFILES --profile postgres"
                ;;
            --with-redis)
                PROFILES="$PROFILES --profile redis"
                ;;
            --with-monitoring)
                PROFILES="$PROFILES --profile monitoring"
                ;;
        esac
    done
    
    $DOCKER_COMPOSE $PROFILES up -d
    
    log_success "Services started"
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    
    cd "$PROJECT_ROOT"
    $DOCKER_COMPOSE down
    
    log_success "Services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    
    stop_services
    start_services
    
    log_success "Services restarted"
}

# Show service status
show_status() {
    log_info "Service status:"
    
    cd "$PROJECT_ROOT"
    $DOCKER_COMPOSE ps
    
    # Show health status
    echo
    log_info "Health status:"
    docker exec gecko-collector python -m gecko_terminal_collector.cli health-check 2>/dev/null || log_warning "Health check failed"
}

# Show logs
show_logs() {
    cd "$PROJECT_ROOT"
    
    # Parse log arguments
    FOLLOW=""
    SERVICE="gecko-collector"
    
    for arg in "${ARGS[@]}"; do
        case $arg in
            --follow|-f)
                FOLLOW="-f"
                ;;
            --service)
                shift
                SERVICE="$1"
                ;;
        esac
    done
    
    $DOCKER_COMPOSE logs $FOLLOW "$SERVICE"
}

# Create backup
create_backup() {
    if [[ ${#ARGS[@]} -eq 0 ]]; then
        log_error "Backup path required. Usage: $0 backup <backup_path>"
        exit 1
    fi
    
    BACKUP_PATH="${ARGS[0]}"
    
    log_info "Creating backup at: $BACKUP_PATH"
    
    docker exec gecko-collector python -m gecko_terminal_collector.cli backup "$BACKUP_PATH" --compress
    
    log_success "Backup created successfully"
}

# Restore from backup
restore_backup() {
    if [[ ${#ARGS[@]} -eq 0 ]]; then
        log_error "Backup path required. Usage: $0 restore <backup_path>"
        exit 1
    fi
    
    BACKUP_PATH="${ARGS[0]}"
    
    log_info "Restoring from backup: $BACKUP_PATH"
    
    # Confirm restoration
    read -p "This will overwrite existing data. Are you sure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        exit 0
    fi
    
    docker exec gecko-collector python -m gecko_terminal_collector.cli restore "$BACKUP_PATH" --overwrite --verify
    
    log_success "Restore completed successfully"
}

# Clean up old resources
cleanup_resources() {
    log_info "Cleaning up old resources..."
    
    # Remove old containers
    docker container prune -f
    
    # Remove old images
    docker image prune -f
    
    # Remove old volumes (with confirmation)
    read -p "Remove unused volumes? This may delete data. (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker volume prune -f
    fi
    
    log_success "Cleanup completed"
}

# Check system health
check_health() {
    log_info "Checking system health..."
    
    # Check if container is running
    if ! docker ps | grep -q gecko-collector; then
        log_error "Collector container is not running"
        exit 1
    fi
    
    # Run health check
    if docker exec gecko-collector python -m gecko_terminal_collector.cli health-check --json; then
        log_success "System health check passed"
    else
        log_error "System health check failed"
        exit 1
    fi
}

# Main execution
main() {
    # Parse arguments
    parse_args "$@"
    
    # Check if command is provided
    if [[ -z "${COMMAND:-}" ]]; then
        log_error "No command specified. Use -h for help."
        exit 1
    fi
    
    # Check prerequisites
    check_prerequisites
    
    # Load environment
    load_environment
    
    # Execute command
    case "$COMMAND" in
        build)
            build_image
            ;;
        deploy)
            build_image
            deploy_application
            ;;
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        backup)
            create_backup
            ;;
        restore)
            restore_backup
            ;;
        cleanup)
            cleanup_resources
            ;;
        health)
            check_health
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"