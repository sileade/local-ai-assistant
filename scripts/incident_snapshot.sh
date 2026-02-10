'''#!/bin/bash
# incident_snapshot.sh: Collects volatile system data for incident response analysis.

# --- Configuration ---
OUTPUT_DIR="/tmp/incident_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$OUTPUT_DIR/snapshot_$TIMESTAMP.txt"

# --- Setup ---
mkdir -p "$OUTPUT_DIR"
exec > "$REPORT_FILE" 2>&1

# --- Helper Functions ---
print_header() {
    echo -e "\n\n========================================================================"
    echo "====== $1"
    echo "========================================================================\n"
}

# --- Data Collection ---

print_header "SYSTEM INFORMATION"
date
hostname
uname -a
uptime

print_header "LOGGED-IN USERS"
who -a
w

print_header "RUNNING PROCESSES"
ps auxww

print_header "NETWORK CONNECTIONS"
ss -tulnpa

print_header "RECENT COMMAND HISTORY"
# Note: This may not capture everything, but it's a starting point.
cat ~/.bash_history

print_header "RECENT AUTHENTICATION LOGS (last 100 lines)"
# For Debian/Ubuntu
if [ -f /var/log/auth.log ]; then
    tail -n 100 /var/log/auth.log
fi
# For RHEL/CentOS
if [ -f /var/log/secure ]; then
    tail -n 100 /var/log/secure
fi

print_header "RECENT SYSTEM LOGS (last 100 lines)"
# For Debian/Ubuntu
if [ -f /var/log/syslog ]; then
    tail -n 100 /var/log/syslog
fi
# For RHEL/CentOS
if [ -f /var/log/messages ]; then
    tail -n 100 /var/log/messages
fi


echo "\n\n--- SNAPSHOT COMPLETE ---"
echo "Report saved to: $REPORT_FILE"
'''
