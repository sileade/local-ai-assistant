#!/bin/bash
#
# Local AI Assistant - Uninstaller
#

set -e

# --- Helper Functions ---

# Color codes
C_RESET=\'\e[0m\'
C_RED=\'\e[31m\'
C_YELLOW=\'\e[33m\'
C_BOLD=\'\e[1m\'

info() { echo -e "${C_YELLOW}${C_BOLD}[INFO]${C_RESET} $1"; }

# --- Main Execution ---

main() {
    echo -e "${C_RED}${C_BOLD}This will permanently remove all Local AI Assistant containers, volumes, and networks.${C_RESET}"
    read -p "Are you sure you want to continue? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Uninstall cancelled."
        exit 0
    fi

    DOCKER_COMPOSE_CMD="docker compose"
    if ! docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker-compose"
    fi

    info "Stopping and removing containers..."
    $DOCKER_COMPOSE_CMD down -v

    info "Removing configuration files..."
    rm -f .env
    rm -f configs/openclaw.json

    echo -e "\n${C_YELLOW}${C_BOLD}Uninstall complete.${C_RESET}"
}

main
