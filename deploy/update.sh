#!/bin/bash
#
# Local AI Assistant - Updater
#

set -e

# --- Helper Functions ---

# Color codes
C_RESET=\'\e[0m\'
C_GREEN=\'\e[32m\'
C_BLUE=\'\e[34m\'
C_BOLD=\'\e[1m\'

info() { echo -e "${C_BLUE}${C_BOLD}[INFO]${C_RESET} $1"; }
success() { echo -e "${C_GREEN}${C_BOLD}[SUCCESS]${C_RESET} $1"; }

# --- Main Execution ---

main() {
    echo -e "${C_BOLD}Updating Local AI Assistant...${C_RESET}"

    DOCKER_COMPOSE_CMD="docker compose"
    if ! docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker-compose"
    fi

    info "Pulling the latest versions of all Docker images..."
    $DOCKER_COMPOSE_CMD pull

    info "Recreating containers with the new images..."
    $DOCKER_COMPOSE_CMD up -d

    success "Update complete! All services have been updated and restarted."
}

main
