'''#!/bin/bash
# health_check.sh: A script to display key system health metrics.

# --- Helper Functions ---
print_header() {
    echo -e "\n\e[1;34m--- $1 ---\e[0m"
}

# --- Main Execution ---

print_header "System Health Report"
echo "Generated on: $(date)"

print_header "CPU Load"
# Shows 1, 5, and 15-minute load averages
uptime

print_header "Memory Usage"
# Shows total, used, free, and available memory in human-readable format
free -h

print_header "Disk Space Usage"
# Shows disk usage for all mounted filesystems in human-readable format
df -h

print_header "Running Processes (Top 10 by CPU)"
# Shows the top 10 processes consuming the most CPU
ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | head -n 11

print_header "Network Connections"
# Shows listening TCP and UDP ports
ss -tuln

print_header "System Log (Last 10 Errors/Warnings)"
# Greps the syslog for recent errors or warnings
journalctl -p 3 -n 10 --no-pager

echo -e "\n\e[1;32m--- End of Report ---\e[0m"
'''
