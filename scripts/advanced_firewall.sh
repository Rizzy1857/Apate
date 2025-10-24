#!/bin/bash
# Advanced Network Firewall Configuration for Project Mirage
# =========================================================
# Implements production-grade iptables rules for honeypot security

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/mirage-firewall.log"

# Network Configuration
HONEYPOT_INTERFACE="docker0"
HONEYPOT_SUBNET="172.20.0.0/16"
MONITORING_SUBNET="172.21.0.0/16"
ADMIN_IPS=(
    "192.168.1.100"     # Admin workstation - replace with actual
    "10.0.1.50"         # VPN gateway - replace with actual
)

# Service Ports
SSH_HONEYPOT_PORT="2222"
HTTP_HONEYPOT_PORT="8080" 
IOT_HONEYPOT_PORT="8081"
RUST_HONEYPOT_PORT="7878"
MGMT_API_PORT="8000"

# Rate Limiting Configuration
SSH_RATE_LIMIT="5/min"
HTTP_RATE_LIMIT="20/min"
IOT_RATE_LIMIT="15/min"
RUST_RATE_LIMIT="30/min"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1" | tee -a "$LOG_FILE"
}

error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
        exit 1
    fi
    
    if ! command -v iptables &> /dev/null; then
        error "iptables not found"
        exit 1
    fi
    
    if ! command -v ipset &> /dev/null; then
        log "Installing ipset for advanced IP management..."
        apt-get update && apt-get install -y ipset
    fi
}

# Create ipsets for dynamic IP management
setup_ipsets() {
    log "Setting up IP sets for dynamic management..."
    
    # Create ipsets (ignore errors if already exist)
    ipset create honeypot_attackers hash:ip timeout 3600 2>/dev/null || true
    ipset create honeypot_whitelist hash:ip timeout 0 2>/dev/null || true
    ipset create rate_limited_ips hash:ip timeout 300 2>/dev/null || true
    ipset create suspicious_ips hash:ip timeout 1800 2>/dev/null || true
    
    # Add admin IPs to whitelist
    for admin_ip in "${ADMIN_IPS[@]}"; do
        ipset add honeypot_whitelist "$admin_ip" 2>/dev/null || true
    done
    
    log "IP sets configured successfully"
}

# Flush existing rules
flush_existing_rules() {
    log "Flushing existing iptables rules..."
    
    # Save current rules as backup
    iptables-save > "/etc/iptables/rules.backup.$(date +%s)" 2>/dev/null || true
    
    # Flush all chains
    iptables -F
    iptables -X 2>/dev/null || true
    iptables -t nat -F
    iptables -t nat -X 2>/dev/null || true
    iptables -t mangle -F
    iptables -t mangle -X 2>/dev/null || true
    
    log "Existing rules flushed"
}

# Set default policies
set_default_policies() {
    log "Setting secure default policies..."
    
    # Default deny policies
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT ACCEPT  # Allow outbound by default
    
    log "Default policies set to secure defaults"
}

# Create custom chains
create_custom_chains() {
    log "Creating custom iptables chains..."
    
    # Main honeypot chains
    iptables -N HONEYPOT_INPUT 2>/dev/null || true
    iptables -N HONEYPOT_FORWARD 2>/dev/null || true
    iptables -N HONEYPOT_LOGGING 2>/dev/null || true
    
    # Security chains
    iptables -N DDOS_PROTECTION 2>/dev/null || true
    iptables -N RATE_LIMITING 2>/dev/null || true
    iptables -N THREAT_DETECTION 2>/dev/null || true
    iptables -N CONTAINER_ISOLATION 2>/dev/null || true
    
    # Service-specific chains
    iptables -N SSH_HONEYPOT 2>/dev/null || true
    iptables -N HTTP_HONEYPOT 2>/dev/null || true
    iptables -N IOT_HONEYPOT 2>/dev/null || true
    iptables -N RUST_HONEYPOT 2>/dev/null || true
    iptables -N MGMT_API 2>/dev/null || true
    
    log "Custom chains created"
}

# Configure loopback and established connections
setup_basic_rules() {
    log "Setting up basic connectivity rules..."
    
    # Allow loopback
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -o lo -j ACCEPT
    
    # Allow established and related connections
    iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    
    log "Basic connectivity rules configured"
}

# Configure DDoS protection
setup_ddos_protection() {
    log "Setting up DDoS protection..."
    
    # Clear the chain
    iptables -F DDOS_PROTECTION
    
    # Limit new connections globally
    iptables -A DDOS_PROTECTION -m conntrack --ctstate NEW -m limit --limit 50/second --limit-burst 100 -j RETURN
    iptables -A DDOS_PROTECTION -m conntrack --ctstate NEW -j LOG --log-prefix "DDOS_NEW_CONN_LIMIT: " --log-level 4
    iptables -A DDOS_PROTECTION -m conntrack --ctstate NEW -j DROP
    
    # SYN flood protection
    iptables -A DDOS_PROTECTION -p tcp --syn -m limit --limit 10/second --limit-burst 20 -j RETURN
    iptables -A DDOS_PROTECTION -p tcp --syn -j LOG --log-prefix "SYN_FLOOD: " --log-level 4
    iptables -A DDOS_PROTECTION -p tcp --syn -j DROP
    
    # ICMP flood protection
    iptables -A DDOS_PROTECTION -p icmp -m limit --limit 5/second --limit-burst 10 -j RETURN
    iptables -A DDOS_PROTECTION -p icmp -j LOG --log-prefix "ICMP_FLOOD: " --log-level 4
    iptables -A DDOS_PROTECTION -p icmp -j DROP
    
    # Invalid packets
    iptables -A DDOS_PROTECTION -m conntrack --ctstate INVALID -j LOG --log-prefix "INVALID_PKT: " --log-level 4
    iptables -A DDOS_PROTECTION -m conntrack --ctstate INVALID -j DROP
    
    log "DDoS protection configured"
}

# Configure threat detection
setup_threat_detection() {
    log "Setting up threat detection rules..."
    
    # Clear the chain
    iptables -F THREAT_DETECTION
    
    # Port scanning detection
    iptables -A THREAT_DETECTION -p tcp --tcp-flags SYN,ACK,FIN,RST RST -m limit --limit 1/s --limit-burst 2 -j RETURN
    iptables -A THREAT_DETECTION -p tcp --tcp-flags SYN,ACK,FIN,RST RST -j LOG --log-prefix "PORT_SCAN_RST: " --log-level 4
    iptables -A THREAT_DETECTION -p tcp --tcp-flags SYN,ACK,FIN,RST RST -m recent --set --name portscan --rsource
    iptables -A THREAT_DETECTION -p tcp --tcp-flags SYN,ACK,FIN,RST RST -j DROP
    
    # NMAP detection
    iptables -A THREAT_DETECTION -p tcp --tcp-flags ALL NONE -j LOG --log-prefix "NMAP_NULL_SCAN: " --log-level 4
    iptables -A THREAT_DETECTION -p tcp --tcp-flags ALL NONE -j DROP
    iptables -A THREAT_DETECTION -p tcp --tcp-flags ALL ALL -j LOG --log-prefix "NMAP_XMAS_SCAN: " --log-level 4
    iptables -A THREAT_DETECTION -p tcp --tcp-flags ALL ALL -j DROP
    
    # Suspicious flag combinations
    iptables -A THREAT_DETECTION -p tcp --tcp-flags ALL FIN,URG,PSH -j LOG --log-prefix "SUSPICIOUS_FLAGS: " --log-level 4
    iptables -A THREAT_DETECTION -p tcp --tcp-flags ALL FIN,URG,PSH -j DROP
    iptables -A THREAT_DETECTION -p tcp --tcp-flags ALL SYN,RST,ACK,FIN,URG -j LOG --log-prefix "SUSPICIOUS_FLAGS: " --log-level 4
    iptables -A THREAT_DETECTION -p tcp --tcp-flags ALL SYN,RST,ACK,FIN,URG -j DROP
    
    # Add detected attackers to ipset
    iptables -A THREAT_DETECTION -m recent --name portscan --rcheck --seconds 60 --hitcount 5 -j SET --add-set honeypot_attackers src
    
    log "Threat detection rules configured"
}

# Configure rate limiting
setup_rate_limiting() {
    log "Setting up service-specific rate limiting..."
    
    # Clear the chain
    iptables -F RATE_LIMITING
    
    # Check whitelist first
    iptables -A RATE_LIMITING -m set --match-set honeypot_whitelist src -j RETURN
    
    # Check if already rate limited
    iptables -A RATE_LIMITING -m set --match-set rate_limited_ips src -j DROP
    
    # SSH honeypot rate limiting
    iptables -A RATE_LIMITING -p tcp --dport "$SSH_HONEYPOT_PORT" -m recent --set --name ssh_attempts --rsource
    iptables -A RATE_LIMITING -p tcp --dport "$SSH_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 5 --name ssh_attempts --rsource -j SET --add-set rate_limited_ips src --timeout 300
    iptables -A RATE_LIMITING -p tcp --dport "$SSH_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 5 --name ssh_attempts --rsource -j LOG --log-prefix "SSH_RATE_LIMIT: " --log-level 4
    iptables -A RATE_LIMITING -p tcp --dport "$SSH_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 5 --name ssh_attempts --rsource -j DROP
    
    # HTTP honeypot rate limiting
    iptables -A RATE_LIMITING -p tcp --dport "$HTTP_HONEYPOT_PORT" -m recent --set --name http_attempts --rsource
    iptables -A RATE_LIMITING -p tcp --dport "$HTTP_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 20 --name http_attempts --rsource -j SET --add-set rate_limited_ips src --timeout 300
    iptables -A RATE_LIMITING -p tcp --dport "$HTTP_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 20 --name http_attempts --rsource -j LOG --log-prefix "HTTP_RATE_LIMIT: " --log-level 4
    iptables -A RATE_LIMITING -p tcp --dport "$HTTP_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 20 --name http_attempts --rsource -j DROP
    
    # IoT honeypot rate limiting
    iptables -A RATE_LIMITING -p tcp --dport "$IOT_HONEYPOT_PORT" -m recent --set --name iot_attempts --rsource
    iptables -A RATE_LIMITING -p tcp --dport "$IOT_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 15 --name iot_attempts --rsource -j SET --add-set rate_limited_ips src --timeout 300
    iptables -A RATE_LIMITING -p tcp --dport "$IOT_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 15 --name iot_attempts --rsource -j LOG --log-prefix "IOT_RATE_LIMIT: " --log-level 4
    iptables -A RATE_LIMITING -p tcp --dport "$IOT_HONEYPOT_PORT" -m recent --update --seconds 60 --hitcount 15 --name iot_attempts --rsource -j DROP
    
    log "Rate limiting rules configured"
}

# Configure container isolation
setup_container_isolation() {
    log "Setting up container isolation rules..."
    
    # Clear the chain
    iptables -F CONTAINER_ISOLATION
    
    # Block inter-container communication within honeypot network (except via defined services)
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d "$HONEYPOT_SUBNET" -p tcp --dport 6379 -j ACCEPT  # Redis
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d "$HONEYPOT_SUBNET" -j LOG --log-prefix "CONTAINER_ISOLATION: " --log-level 6
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d "$HONEYPOT_SUBNET" -j DROP
    
    # Block honeypot containers from accessing host services
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 127.0.0.0/8 -j LOG --log-prefix "HOST_ACCESS_BLOCK: " --log-level 4
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 127.0.0.0/8 -j DROP
    
    # Block access to private networks
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 192.168.0.0/16 -j LOG --log-prefix "PRIVATE_NET_BLOCK: " --log-level 4
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 192.168.0.0/16 -j DROP
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 10.0.0.0/8 -j LOG --log-prefix "PRIVATE_NET_BLOCK: " --log-level 4
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 10.0.0.0/8 -j DROP
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 172.16.0.0/12 -j LOG --log-prefix "PRIVATE_NET_BLOCK: " --log-level 4
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 172.16.0.0/12 -j DROP
    
    # Block cloud metadata services
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 169.254.169.254 -j LOG --log-prefix "METADATA_BLOCK: " --log-level 4
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -d 169.254.169.254 -j DROP
    
    # Allow essential outbound (DNS, NTP, threat intel)
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -p udp --dport 53 -j ACCEPT  # DNS
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -p tcp --dport 53 -j ACCEPT  # DNS over TCP
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -p udp --dport 123 -j ACCEPT  # NTP
    iptables -A CONTAINER_ISOLATION -s "$HONEYPOT_SUBNET" -p tcp --dport 443 -m limit --limit 10/min -j ACCEPT  # HTTPS (rate limited)
    
    log "Container isolation rules configured"
}

# Configure logging
setup_logging() {
    log "Setting up comprehensive logging rules..."
    
    # Clear the chain
    iptables -F HONEYPOT_LOGGING
    
    # Log all new connections to honeypot services
    iptables -A HONEYPOT_LOGGING -p tcp --dport "$SSH_HONEYPOT_PORT" -m conntrack --ctstate NEW -j LOG --log-prefix "SSH_HONEYPOT: " --log-level 6
    iptables -A HONEYPOT_LOGGING -p tcp --dport "$HTTP_HONEYPOT_PORT" -m conntrack --ctstate NEW -j LOG --log-prefix "HTTP_HONEYPOT: " --log-level 6
    iptables -A HONEYPOT_LOGGING -p tcp --dport "$IOT_HONEYPOT_PORT" -m conntrack --ctstate NEW -j LOG --log-prefix "IOT_HONEYPOT: " --log-level 6
    iptables -A HONEYPOT_LOGGING -p tcp --dport "$RUST_HONEYPOT_PORT" -m conntrack --ctstate NEW -j LOG --log-prefix "RUST_HONEYPOT: " --log-level 6
    
    # Log management API access
    iptables -A HONEYPOT_LOGGING -p tcp --dport "$MGMT_API_PORT" -m conntrack --ctstate NEW -j LOG --log-prefix "MGMT_API: " --log-level 6
    
    # Log attempts to common services (not honeypots)
    iptables -A HONEYPOT_LOGGING -p tcp --dport 22 -j LOG --log-prefix "REAL_SSH_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOGGING -p tcp --dport 21 -j LOG --log-prefix "FTP_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOGGING -p tcp --dport 23 -j LOG --log-prefix "TELNET_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOGGING -p tcp --dport 25 -j LOG --log-prefix "SMTP_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOGGING -p tcp --dport 80 -j LOG --log-prefix "HTTP_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOGGING -p tcp --dport 443 -j LOG --log-prefix "HTTPS_PROBE: " --log-level 4
    iptables -A HONEYPOT_LOGGING -p tcp --dport 3389 -j LOG --log-prefix "RDP_PROBE: " --log-level 4
    
    log "Logging rules configured"
}

# Configure service-specific rules
setup_service_rules() {
    log "Setting up service-specific rules..."
    
    # SSH Honeypot
    iptables -F SSH_HONEYPOT
    iptables -A SSH_HONEYPOT -p tcp --dport "$SSH_HONEYPOT_PORT" -m conntrack --ctstate NEW -j ACCEPT
    
    # HTTP Honeypot  
    iptables -F HTTP_HONEYPOT
    iptables -A HTTP_HONEYPOT -p tcp --dport "$HTTP_HONEYPOT_PORT" -m conntrack --ctstate NEW -j ACCEPT
    
    # IoT Honeypot
    iptables -F IOT_HONEYPOT
    iptables -A IOT_HONEYPOT -p tcp --dport "$IOT_HONEYPOT_PORT" -m conntrack --ctstate NEW -j ACCEPT
    
    # Rust Honeypot
    iptables -F RUST_HONEYPOT
    iptables -A RUST_HONEYPOT -p tcp --dport "$RUST_HONEYPOT_PORT" -m conntrack --ctstate NEW -j ACCEPT
    
    # Management API (restricted to admin IPs)
    iptables -F MGMT_API
    for admin_ip in "${ADMIN_IPS[@]}"; do
        iptables -A MGMT_API -s "$admin_ip" -p tcp --dport "$MGMT_API_PORT" -j ACCEPT
    done
    iptables -A MGMT_API -p tcp --dport "$MGMT_API_PORT" -j LOG --log-prefix "MGMT_UNAUTHORIZED: " --log-level 4
    iptables -A MGMT_API -p tcp --dport "$MGMT_API_PORT" -j DROP
    
    log "Service-specific rules configured"
}

# Apply all chains to main chains
apply_chains() {
    log "Applying custom chains to main iptables chains..."
    
    # INPUT chain processing order
    iptables -A INPUT -j DDOS_PROTECTION
    iptables -A INPUT -j THREAT_DETECTION
    iptables -A INPUT -j RATE_LIMITING
    iptables -A INPUT -j HONEYPOT_LOGGING
    iptables -A INPUT -j SSH_HONEYPOT
    iptables -A INPUT -j HTTP_HONEYPOT
    iptables -A INPUT -j IOT_HONEYPOT
    iptables -A INPUT -j RUST_HONEYPOT
    iptables -A INPUT -j MGMT_API
    
    # FORWARD chain (for container traffic)
    iptables -A FORWARD -j CONTAINER_ISOLATION
    iptables -A FORWARD -j HONEYPOT_LOGGING
    
    # Apply to Docker chains
    iptables -I DOCKER-USER 1 -j CONTAINER_ISOLATION
    
    log "Custom chains applied to main iptables chains"
}

# Save configuration
save_configuration() {
    log "Saving iptables configuration..."
    
    mkdir -p /etc/iptables
    iptables-save > /etc/iptables/rules.v4
    
    # Create systemd service for persistence
    cat > /etc/systemd/system/mirage-firewall.service << 'EOF'
[Unit]
Description=Project Mirage Firewall Rules
After=network.target docker.service
Before=docker-compose.service

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/rules.v4
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
EOF

    systemctl enable mirage-firewall.service
    
    log "Configuration saved and persistence enabled"
}

# Generate monitoring script
create_monitoring_script() {
    log "Creating firewall monitoring script..."
    
    cat > /usr/local/bin/mirage-firewall-monitor.sh << 'EOF'
#!/bin/bash
# Project Mirage Firewall Monitoring Script

LOG_FILE="/var/log/mirage-firewall-monitor.log"
ALERT_THRESHOLD=50

# Check rate limited IPs
rate_limited_count=$(ipset list rate_limited_ips | grep -c "^[0-9]" || echo 0)
if [[ $rate_limited_count -gt $ALERT_THRESHOLD ]]; then
    echo "$(date): HIGH ALERT - $rate_limited_count IPs currently rate limited" >> "$LOG_FILE"
fi

# Check attacker IPs
attacker_count=$(ipset list honeypot_attackers | grep -c "^[0-9]" || echo 0)
if [[ $attacker_count -gt 10 ]]; then
    echo "$(date): WARNING - $attacker_count IPs flagged as attackers" >> "$LOG_FILE"
fi

# Check for recent suspicious activity
suspicious_count=$(journalctl --since "1 hour ago" | grep -c "SUSPICIOUS\|THREAT\|ATTACK" || echo 0)
if [[ $suspicious_count -gt 20 ]]; then
    echo "$(date): HIGH ALERT - $suspicious_count suspicious events in last hour" >> "$LOG_FILE"
fi

# Generate summary
echo "$(date): Monitoring Summary - Rate Limited: $rate_limited_count, Attackers: $attacker_count, Suspicious Events: $suspicious_count" >> "$LOG_FILE"
EOF

    chmod +x /usr/local/bin/mirage-firewall-monitor.sh
    
    # Create cron job for monitoring
    echo "*/10 * * * * root /usr/local/bin/mirage-firewall-monitor.sh" > /etc/cron.d/mirage-firewall-monitor
    
    log "Firewall monitoring script created"
}

# Generate status report
generate_status_report() {
    log "Generating firewall status report..."
    
    cat > /tmp/mirage-firewall-status.txt << EOF
Project Mirage Firewall Configuration Report
==========================================
Generated: $(date)
Host: $(hostname)
Kernel: $(uname -r)

=== Configuration Summary ===
Honeypot Subnet: $HONEYPOT_SUBNET
Monitoring Subnet: $MONITORING_SUBNET
Admin IPs: ${ADMIN_IPS[*]}

=== Service Ports ===
SSH Honeypot: $SSH_HONEYPOT_PORT
HTTP Honeypot: $HTTP_HONEYPOT_PORT
IoT Honeypot: $IOT_HONEYPOT_PORT
Rust Honeypot: $RUST_HONEYPOT_PORT
Management API: $MGMT_API_PORT

=== Active IPSets ===
$(ipset list -n)

=== Current IPSet Statistics ===
$(for set in honeypot_attackers rate_limited_ips suspicious_ips; do
    count=$(ipset list "$set" | grep -c "^[0-9]" || echo 0)
    echo "$set: $count entries"
done)

=== Iptables Rules Count ===
$(iptables -L | grep -c "^Chain\|^target")

=== Security Features Enabled ===
✓ DDoS Protection with rate limiting
✓ Threat detection and port scan detection  
✓ Service-specific rate limiting
✓ Container network isolation
✓ Comprehensive security logging
✓ Dynamic IP management with ipsets
✓ Admin IP whitelisting
✓ Automated monitoring and alerting

=== Next Steps ===
1. Monitor /var/log/mirage-firewall-monitor.log for alerts
2. Review firewall logs: journalctl -f | grep -E "HONEYPOT|THREAT|SUSPICIOUS"
3. Check ipset statistics: ipset list honeypot_attackers
4. Test honeypot functionality after rule application
5. Configure log shipping to SIEM system

=== Maintenance Commands ===
View current rules: iptables -L -n --line-numbers
Check ipset contents: ipset list [set_name]
Monitor live activity: tail -f /var/log/kern.log | grep -E "HONEYPOT|THREAT"
Restart firewall: systemctl restart mirage-firewall.service
EOF
    
    echo "Firewall configuration report generated: /tmp/mirage-firewall-status.txt"
    cat /tmp/mirage-firewall-status.txt
}

# Main execution function
main() {
    log "Starting Project Mirage advanced firewall configuration..."
    
    check_prerequisites
    setup_ipsets
    flush_existing_rules
    set_default_policies
    create_custom_chains
    setup_basic_rules
    setup_ddos_protection
    setup_threat_detection
    setup_rate_limiting
    setup_container_isolation
    setup_logging
    setup_service_rules
    apply_chains
    save_configuration
    create_monitoring_script
    generate_status_report
    
    log "Advanced firewall configuration completed successfully!"
    log "Please review the status report and test all services"
}

# Execute main function
main "$@"
