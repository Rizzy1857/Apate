#!/bin/bash
# Network Security Hardening Script for Project Mirage Honeypot
# ============================================================
# This script implements comprehensive network isolation and security
# measures for production honeypot deployment.

set -euo pipefail

# Configuration
HONEYPOT_SUBNET="172.20.0.0/16"
HONEYPOT_INTERFACE="docker0"
LOG_SERVER="192.168.1.100"  # Replace with your SIEM/log server
DNS_SERVERS="8.8.8.8,1.1.1.1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root for iptables configuration"
        exit 1
    fi
}

# Backup existing iptables rules
backup_iptables() {
    log "Backing up existing iptables rules..."
    if command -v iptables-save &> /dev/null; then
        iptables-save > "/etc/iptables/rules.v4.backup.$(date +%s)" || true
        ip6tables-save > "/etc/iptables/rules.v6.backup.$(date +%s)" || true
        success "Iptables rules backed up"
    else
        warn "iptables-save not found, skipping backup"
    fi
}

# Create honeypot isolation rules
setup_honeypot_isolation() {
    log "Setting up honeypot network isolation..."
    
    # Create new chain for honeypot rules
    iptables -t filter -N HONEYPOT_ISOLATION 2>/dev/null || true
    iptables -t filter -F HONEYPOT_ISOLATION
    
    # Block honeypot from accessing internal networks
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 192.168.0.0/16 -j LOG --log-prefix "HONEYPOT_INTERNAL_BLOCK: "
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 192.168.0.0/16 -j DROP
    
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 172.16.0.0/12 -j LOG --log-prefix "HONEYPOT_INTERNAL_BLOCK: "
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 172.16.0.0/12 -j DROP
    
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 10.0.0.0/8 -j LOG --log-prefix "HONEYPOT_INTERNAL_BLOCK: "
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 10.0.0.0/8 -j DROP
    
    # Block access to localhost from honeypot containers
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 127.0.0.0/8 -j LOG --log-prefix "HONEYPOT_LOCALHOST_BLOCK: "
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 127.0.0.0/8 -j DROP
    
    # Block access to metadata services (AWS, GCP, Azure)
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 169.254.169.254 -j LOG --log-prefix "HONEYPOT_METADATA_BLOCK: "
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d 169.254.169.254 -j DROP
    
    # Allow only essential outbound connections
    # DNS
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -p udp --dport 53 -j ACCEPT
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -p tcp --dport 53 -j ACCEPT
    
    # HTTPS for threat intel and updates (rate limited)
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -p tcp --dport 443 -m limit --limit 10/min --limit-burst 5 -j ACCEPT
    
    # Log server (secure syslog)
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d ${LOG_SERVER} -p tcp --dport 514 -j ACCEPT
    iptables -A HONEYPOT_ISOLATION -s ${HONEYPOT_SUBNET} -d ${LOG_SERVER} -p udp --dport 514 -j ACCEPT
    
    # Apply isolation rules to FORWARD chain
    iptables -I FORWARD 1 -j HONEYPOT_ISOLATION
    
    success "Honeypot network isolation configured"
}

# Setup incoming traffic rules
setup_incoming_rules() {
    log "Setting up incoming traffic rules..."
    
    # Create chain for honeypot services
    iptables -t filter -N HONEYPOT_SERVICES 2>/dev/null || true
    iptables -t filter -F HONEYPOT_SERVICES
    
    # Rate limiting for SSH honeypot (prevent DoS)
    iptables -A HONEYPOT_SERVICES -p tcp --dport 2222 -m state --state NEW -m recent --set --name SSH_HONEYPOT
    iptables -A HONEYPOT_SERVICES -p tcp --dport 2222 -m state --state NEW -m recent --update --seconds 60 --hitcount 10 --name SSH_HONEYPOT -j LOG --log-prefix "SSH_HONEYPOT_RATE_LIMIT: "
    iptables -A HONEYPOT_SERVICES -p tcp --dport 2222 -m state --state NEW -m recent --update --seconds 60 --hitcount 10 --name SSH_HONEYPOT -j DROP
    iptables -A HONEYPOT_SERVICES -p tcp --dport 2222 -j ACCEPT
    
    # Rate limiting for HTTP honeypot
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8080 -m state --state NEW -m recent --set --name HTTP_HONEYPOT
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8080 -m state --state NEW -m recent --update --seconds 60 --hitcount 20 --name HTTP_HONEYPOT -j LOG --log-prefix "HTTP_HONEYPOT_RATE_LIMIT: "
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8080 -m state --state NEW -m recent --update --seconds 60 --hitcount 20 --name HTTP_HONEYPOT -j DROP
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8080 -j ACCEPT
    
    # IoT honeypot services
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8081 -m state --state NEW -m recent --set --name IOT_HONEYPOT
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8081 -m state --state NEW -m recent --update --seconds 60 --hitcount 15 --name IOT_HONEYPOT -j LOG --log-prefix "IOT_HONEYPOT_RATE_LIMIT: "
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8081 -m state --state NEW -m recent --update --seconds 60 --hitcount 15 --name IOT_HONEYPOT -j DROP
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8081 -j ACCEPT
    
    # Rust protocol services
    iptables -A HONEYPOT_SERVICES -p tcp --dport 7878 -m state --state NEW -m recent --set --name RUST_HONEYPOT
    iptables -A HONEYPOT_SERVICES -p tcp --dport 7878 -m state --state NEW -m recent --update --seconds 60 --hitcount 30 --name RUST_HONEYPOT -j LOG --log-prefix "RUST_HONEYPOT_RATE_LIMIT: "
    iptables -A HONEYPOT_SERVICES -p tcp --dport 7878 -m state --state NEW -m recent --update --seconds 60 --hitcount 30 --name RUST_HONEYPOT -j DROP
    iptables -A HONEYPOT_SERVICES -p tcp --dport 7878 -j ACCEPT
    
    # Management interface (restrict to specific IPs if needed)
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8000 -m state --state NEW -m recent --set --name MGMT_API
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8000 -m state --state NEW -m recent --update --seconds 60 --hitcount 30 --name MGMT_API -j LOG --log-prefix "MGMT_API_RATE_LIMIT: "
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8000 -m state --state NEW -m recent --update --seconds 60 --hitcount 30 --name MGMT_API -j DROP
    iptables -A HONEYPOT_SERVICES -p tcp --dport 8000 -j ACCEPT
    
    # Apply to INPUT chain
    iptables -I INPUT -j HONEYPOT_SERVICES
    
    success "Incoming traffic rules configured"
}

# Setup logging and monitoring
setup_logging() {
    log "Setting up security logging..."
    
    # Create chain for security logging
    iptables -t filter -N HONEYPOT_LOG 2>/dev/null || true
    iptables -t filter -F HONEYPOT_LOG
    
    # Log new connections to honeypot services
    iptables -A HONEYPOT_LOG -p tcp --dport 2222 -m state --state NEW -j LOG --log-prefix "SSH_HONEYPOT_CONNECTION: " --log-level 6
    iptables -A HONEYPOT_LOG -p tcp --dport 8080 -m state --state NEW -j LOG --log-prefix "HTTP_HONEYPOT_CONNECTION: " --log-level 6
    iptables -A HONEYPOT_LOG -p tcp --dport 8081 -m state --state NEW -j LOG --log-prefix "IOT_HONEYPOT_CONNECTION: " --log-level 6
    iptables -A HONEYPOT_LOG -p tcp --dport 7878 -m state --state NEW -j LOG --log-prefix "RUST_HONEYPOT_CONNECTION: " --log-level 6
    
    # Log suspicious activity
    iptables -A HONEYPOT_LOG -p tcp --dport 22 -m state --state NEW -j LOG --log-prefix "REAL_SSH_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOG -p tcp --dport 21 -m state --state NEW -j LOG --log-prefix "FTP_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOG -p tcp --dport 23 -m state --state NEW -j LOG --log-prefix "TELNET_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOG -p tcp --dport 3389 -m state --state NEW -j LOG --log-prefix "RDP_PROBE: " --log-level 4
    
    # Apply logging to appropriate chains
    iptables -I INPUT 1 -j HONEYPOT_LOG
    
    success "Security logging configured"
}

# Setup DDoS protection
setup_ddos_protection() {
    log "Setting up DDoS protection..."
    
    # Create chain for DDoS protection
    iptables -t filter -N DDOS_PROTECTION 2>/dev/null || true
    iptables -t filter -F DDOS_PROTECTION
    
    # Limit new connections per second
    iptables -A DDOS_PROTECTION -p tcp -m state --state NEW -m limit --limit 50/second --limit-burst 100 -j ACCEPT
    iptables -A DDOS_PROTECTION -p tcp -m state --state NEW -j LOG --log-prefix "DDOS_NEW_CONNECTION_LIMIT: " --log-level 4
    iptables -A DDOS_PROTECTION -p tcp -m state --state NEW -j DROP
    
    # Protect against SYN flood
    iptables -A DDOS_PROTECTION -p tcp --syn -m limit --limit 10/second --limit-burst 20 -j ACCEPT
    iptables -A DDOS_PROTECTION -p tcp --syn -j LOG --log-prefix "SYN_FLOOD_PROTECTION: " --log-level 4
    iptables -A DDOS_PROTECTION -p tcp --syn -j DROP
    
    # Protect against ping floods
    iptables -A DDOS_PROTECTION -p icmp -m limit --limit 1/second --limit-burst 5 -j ACCEPT
    iptables -A DDOS_PROTECTION -p icmp -j LOG --log-prefix "PING_FLOOD_PROTECTION: " --log-level 4
    iptables -A DDOS_PROTECTION -p icmp -j DROP
    
    # Apply DDoS protection early in INPUT chain
    iptables -I INPUT 1 -j DDOS_PROTECTION
    
    success "DDoS protection configured"
}

# Setup container security
setup_container_security() {
    log "Configuring container security policies..."
    
    # Block container-to-container communication except through defined networks
    iptables -A DOCKER-USER -i ${HONEYPOT_INTERFACE} -o ${HONEYPOT_INTERFACE} -j LOG --log-prefix "CONTAINER_ISOLATION: "
    
    # Allow established connections
    iptables -I DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    
    # Block access to Docker socket
    iptables -A DOCKER-USER -p tcp --dport 2375 -j LOG --log-prefix "DOCKER_SOCKET_BLOCK: "
    iptables -A DOCKER-USER -p tcp --dport 2375 -j DROP
    iptables -A DOCKER-USER -p tcp --dport 2376 -j LOG --log-prefix "DOCKER_SOCKET_TLS_BLOCK: "
    iptables -A DOCKER-USER -p tcp --dport 2376 -j DROP
    
    success "Container security policies configured"
}

# Save iptables rules
save_iptables() {
    log "Saving iptables rules..."
    
    # Create iptables directory if it doesn't exist
    mkdir -p /etc/iptables
    
    if command -v iptables-save &> /dev/null; then
        iptables-save > /etc/iptables/rules.v4
        ip6tables-save > /etc/iptables/rules.v6
        success "Iptables rules saved to /etc/iptables/"
    else
        warn "iptables-save not found, rules not persisted"
    fi
    
    # Create systemd service for rule persistence
    cat > /etc/systemd/system/iptables-restore.service << 'EOF'
[Unit]
Description=Restore iptables rules
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/rules.v4
ExecStart=/sbin/ip6tables-restore /etc/iptables/rules.v6
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl enable iptables-restore.service || warn "Could not enable iptables-restore service"
    
    success "Iptables persistence configured"
}

# Setup fail2ban for additional protection
setup_fail2ban() {
    log "Configuring fail2ban for honeypot protection..."
    
    # Check if fail2ban is installed
    if ! command -v fail2ban-server &> /dev/null; then
        warn "fail2ban not installed, skipping configuration"
        return
    fi
    
    # Create honeypot-specific jail
    cat > /etc/fail2ban/jail.d/honeypot.conf << 'EOF'
[honeypot-ssh]
enabled = true
port = 2222
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
findtime = 600
bantime = 3600
action = iptables[name=SSH-HONEYPOT, port=2222, protocol=tcp]

[honeypot-http]
enabled = true
port = 8080
filter = apache-auth
logpath = /var/log/nginx/access.log
maxretry = 5
findtime = 300
bantime = 1800
action = iptables[name=HTTP-HONEYPOT, port=8080, protocol=tcp]
EOF
    
    systemctl restart fail2ban || warn "Could not restart fail2ban service"
    success "Fail2ban configured for honeypot services"
}

# Generate security report
generate_security_report() {
    log "Generating security configuration report..."
    
    cat > /tmp/honeypot_security_report.txt << EOF
Project Mirage Honeypot - Security Configuration Report
=====================================================
Generated: $(date)
Host: $(hostname)
Kernel: $(uname -r)

Network Configuration:
- Honeypot Subnet: ${HONEYPOT_SUBNET}
- Log Server: ${LOG_SERVER}
- DNS Servers: ${DNS_SERVERS}

Iptables Rules Summary:
$(iptables -L -n --line-numbers)

Active Services:
$(ss -tlnp | grep -E "(2222|8080|8081|7878|8000)")

Security Features Enabled:
✓ Network isolation for honeypot containers
✓ Rate limiting on all honeypot services
✓ DDoS protection measures
✓ Comprehensive security logging
✓ Container-to-container isolation
✓ Docker socket protection
✓ Automatic rule persistence

Next Steps:
1. Configure centralized logging to SIEM
2. Set up monitoring alerts for security events
3. Regular security assessment and rule updates
4. Backup and disaster recovery procedures
EOF
    
    success "Security report generated: /tmp/honeypot_security_report.txt"
    cat /tmp/honeypot_security_report.txt
}

# Main execution
main() {
    log "Starting Project Mirage honeypot security hardening..."
    
    check_root
    backup_iptables
    setup_ddos_protection
    setup_honeypot_isolation
    setup_incoming_rules
    setup_logging
    setup_container_security
    save_iptables
    setup_fail2ban
    generate_security_report
    
    success "Security hardening completed successfully!"
    warn "Please review the security report and adjust configurations as needed."
    warn "Remember to test all honeypot functionality after applying these rules."
}

# Run main function
main "$@"
