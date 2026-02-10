'''#!/bin/bash
# harden_server.sh: A script to apply basic security hardening to a Debian-based Linux server.

# --- WARNING ---
# This script makes significant changes to the system. It is designed for a fresh server.
# Run with caution and review each step. It is idempotent where possible.
# --- WARNING ---

set -e

print_header() {
    echo -e "\n\e[1;34m--- $1 ---\e[0m"
}

print_info() {
    echo -e "\e[0;32m[INFO]\e[0m $1"
}

# 1. Update System Packages
print_header "Updating System Packages"
apt-get update
apt-get upgrade -y
apt-get dist-upgrade -y
apt-get autoremove -y
apt-get autoclean -y
print_info "System packages updated."

# 2. Configure Firewall (UFW)
print_header "Configuring Firewall (UFW)"
if ! command -v ufw &> /dev/null; then
    apt-get install ufw -y
fi
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh # Port 22
ufw allow http # Port 80
ufw allow https # Port 443
# Add other necessary ports here, e.g., ufw allow 3000 for Grafana
ufw --force enable
print_info "Firewall configured. SSH, HTTP, HTTPS allowed."

# 3. Secure SSH Configuration
print_header "Securing SSH"
SSHD_CONFIG="/etc/ssh/sshd_config"
# Disable root login
sed -i 's/PermitRootLogin yes/PermitRootLogin no/g' $SSHD_CONFIG
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/g' $SSHD_CONFIG
# Enforce key-based authentication
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/g' $SSHD_CONFIG
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/g' $SSHD_CONFIG

systemctl restart sshd
print_info "SSH secured: Root login disabled, password authentication disabled."

# 4. Install and run Fail2ban
print_header "Setting up Fail2ban"
if ! command -v fail2ban-client &> /dev/null; then
    apt-get install fail2ban -y
fi
cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
systemctl enable fail2ban
systemctl start fail2ban
print_info "Fail2ban installed and enabled to protect against brute-force attacks."

# 5. Remove Unnecessary Packages
print_header "Removing Unnecessary Packages"
apt-get purge -y telnetd nis yp-tools
print_info "Removed legacy services (telnet, nis, etc.)."

# 6. Harden Kernel Parameters (sysctl)
print_header "Hardening Kernel Parameters"
SYSCTL_CONF="/etc/sysctl.d/99-hardening.conf"
cat > $SYSCTL_CONF << EOL
# IP Spoofing protection
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Ignore ICMP broadcast requests
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Disable source-routed packets
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0

# Ignore send redirects
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Block SYN attacks
net.ipv4.tcp_syncookies = 1
EOL
sysctl --system
print_info "Kernel parameters hardened."

echo -e "\n\e[1;32m--- Hardening Complete ---\e[0m"
'''
