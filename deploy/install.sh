#!/bin/bash
#
# Local AI Assistant - Automated Installer
#

set -e

# --- Helper Functions ---

# Color codes
C_RESET=\'\e[0m\'
C_RED=\'\e[31m\'
C_GREEN=\'\e[32m\'
C_YELLOW=\'\e[33m\'
C_BLUE=\'\e[34m\'
C_BOLD=\'\e[1m\'

info() { echo -e "${C_BLUE}${C_BOLD}[INFO]${C_RESET} $1"; }
success() { echo -e "${C_GREEN}${C_BOLD}[SUCCESS]${C_RESET} $1"; }
warn() { echo -e "${C_YELLOW}${C_BOLD}[WARNING]${C_RESET} $1"; }
error() { echo -e "${C_RED}${C_BOLD}[ERROR]${C_RESET} $1"; exit 1; }

# --- Prerequisite Check ---
check_deps() {
    info "Checking for required dependencies..."
    command -v docker >/dev/null 2>&1 || error "Docker is not installed. Please install it first."
    if ! docker compose version >/dev/null 2>&1; then
        if ! docker-compose version >/dev/null 2>&1; then
            error "Docker Compose is not installed. Please install it first."
        fi
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        DOCKER_COMPOSE_CMD="docker compose"
    fi
    command -v curl >/dev/null 2>&1 || error "curl is not installed. Please install it first."
    command -v jq >/dev/null 2>&1 || error "jq is not installed. Please install it first (e.g., sudo apt-get install jq)."
    success "All dependencies are satisfied."
}

# --- Configuration ---
configure_env() {
    info "Starting configuration..."
    
    if [ -f .env ]; then
        warn ".env file already exists."
        read -p "Do you want to reuse existing settings? (y/N): " reuse
        if [[ "$reuse" =~ ^[Yy]$ ]]; then
            source .env
            return
        fi
    fi

    cp .env.example .env

    # Get Ollama Host
    while true; do
        read -p "Enter the host address of your Ollama VM (e.g., 192.168.1.100:11434): " OLLAMA_HOST
        if [[ -z "$OLLAMA_HOST" ]]; then
            echo "Ollama host cannot be empty." >&2
            continue
        fi
        info "Testing connection to http://${OLLAMA_HOST}..."
        if curl -s --connect-timeout 5 "http://${OLLAMA_HOST}/api/tags" > /dev/null; then
            success "Successfully connected to Ollama."
            sed -i "s|^OLLAMA_HOST=.*|OLLAMA_HOST=${OLLAMA_HOST}|" .env
            break
        else
            warn "Could not connect to Ollama at http://${OLLAMA_HOST}. Please check the address and ensure Ollama is running."
        fi
    done

    # Get other settings
    read -p "Enter your Telegram Bot Token (optional, press Enter to skip): " TELEGRAM_BOT_TOKEN
    sed -i "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}|" .env

    read -p "Enter the domain name for access (optional, e.g., ai.mydomain.com): " DOMAIN_NAME
    sed -i "s|^DOMAIN_NAME=.*|DOMAIN_NAME=${DOMAIN_NAME}|" .env

    # Generate secrets
    info "Generating secure credentials..."
    OPENCLAW_TOKEN=$(openssl rand -hex 16)
    GRAFANA_PASSWORD=$(openssl rand -hex 16)
    sed -i "s|^OPENCLAW_TOKEN=.*|OPENCLAW_TOKEN=${OPENCLAW_TOKEN}|" .env
    sed -i "s|^GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=${GRAFANA_PASSWORD}|" .env
    success "Configuration saved to .env file."
}

# --- Generate Configs ---
generate_configs() {
    info "Generating configuration files..."
    source .env

    # Create OpenClaw config
    jq -n \
      --arg model "ollama/${OLLAMA_MODEL}" \
      --arg baseURL "http://${OLLAMA_HOST}/v1" \
      --arg botToken "${TELEGRAM_BOT_TOKEN}" \
      -f configs/openclaw.json.jq > configs/openclaw.json

    success "All configuration files generated."
}

# --- Main Execution ---
main() {
    echo -e "${C_BOLD}Welcome to the Local AI Assistant Installer!${C_RESET}"
    
    check_deps
    configure_env
    generate_configs

    info "Pulling the latest Docker images. This may take a while..."
    $DOCKER_COMPOSE_CMD pull

    info "Starting all services..."
    $DOCKER_COMPOSE_CMD up -d

    success "Deployment complete!"
    echo "-----------------------------------------------------"
    echo -e "${C_BOLD}Your Local AI Assistant is now running!${C_RESET}"
    echo ""
    echo -e "- ${C_YELLOW}Grafana Dashboard:${C_RESET} http://$(hostname -I | awk '{print $1}'):3000"
    echo -e "  - User: ${C_BOLD}${GRAFANA_USER:-admin}${C_RESET}"
    echo -e "  - Password: ${C_BOLD}${GRAFANA_PASSWORD}${C_RESET}"
    echo ""
    echo -e "- ${C_YELLOW}Prometheus UI:${C_RESET} http://$(hostname -I | awk '{print $1}'):9090"
    echo -e "- ${C_YELLOW}OpenClaw Gateway:${C_RESET} Port ${OPENCLAW_PORT:-18789}"
    if [ -n "$DOMAIN_NAME" ]; then
        echo ""
        echo -e "- ${C_YELLOW}Access via Nginx:${C_RESET} http://${DOMAIN_NAME}"
    fi
    echo ""
    echo "To view logs, run: ${C_BOLD}${DOCKER_COMPOSE_CMD} logs -f${C_RESET}"
    echo "To stop services, run: ${C_BOLD}${DOCKER_COMPOSE_CMD} down${C_RESET}"
    echo "-----------------------------------------------------"
}

main "$@"
