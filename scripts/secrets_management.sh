#!/bin/bash
# Secrets Management and Key Rotation System for Project Mirage
# ============================================================
# Implements comprehensive secrets handling, API key management, and automated rotation

set -euo pipefail

# Configuration
SECRETS_DIR="/opt/mirage/secrets"
VAULT_DIR="/opt/mirage/vault"
BACKUP_DIR="/opt/mirage/backups/secrets"
LOG_FILE="/var/log/mirage-secrets.log"

# Key rotation intervals (in days)
API_KEY_ROTATION_INTERVAL=30
DB_PASSWORD_ROTATION_INTERVAL=90
REDIS_PASSWORD_ROTATION_INTERVAL=60
HONEYPOT_TOKEN_ROTATION_INTERVAL=7

# Security configuration
ENCRYPTION_KEY_FILE="$VAULT_DIR/master.key"
SECRETS_DB_FILE="$VAULT_DIR/secrets.db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}$(date '+%Y-%m-%d %H:%M:%S') [WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1${NC}" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] $1${NC}" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites for secrets management..."
    
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root for secure secrets management"
        exit 1
    fi
    
    # Check for required tools
    local required_tools=("openssl" "sqlite3" "docker" "curl")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error "$tool is required but not installed"
            exit 1
        fi
    done
    
    # Install additional security tools if needed
    if ! command -v age &> /dev/null; then
        log "Installing age encryption tool..."
        wget -O /tmp/age.tar.gz https://github.com/FiloSottile/age/releases/latest/download/age-v1.1.1-linux-amd64.tar.gz
        tar -xzf /tmp/age.tar.gz -C /tmp
        mv /tmp/age/age /usr/local/bin/
        mv /tmp/age/age-keygen /usr/local/bin/
        chmod +x /usr/local/bin/age /usr/local/bin/age-keygen
        rm -rf /tmp/age*
    fi
    
    success "Prerequisites check completed"
}

# Initialize secure directories
init_secure_directories() {
    log "Initializing secure directory structure..."
    
    # Create directories with proper permissions
    mkdir -p "$SECRETS_DIR" "$VAULT_DIR" "$BACKUP_DIR"
    chmod 700 "$SECRETS_DIR" "$VAULT_DIR" "$BACKUP_DIR"
    
    # Create secrets subdirectories
    mkdir -p "$SECRETS_DIR"/{api-keys,certificates,passwords,tokens}
    chmod 700 "$SECRETS_DIR"/{api-keys,certificates,passwords,tokens}
    
    # Set up secure ownership (assuming mirage user exists)
    if id mirage &>/dev/null; then
        chown -R mirage:mirage "$SECRETS_DIR" "$VAULT_DIR"
    fi
    
    success "Secure directories initialized"
}

# Generate master encryption key
generate_master_key() {
    log "Generating master encryption key..."
    
    if [[ -f "$ENCRYPTION_KEY_FILE" ]]; then
        warn "Master key already exists, skipping generation"
        return
    fi
    
    # Generate age key pair
    age-keygen -o "$ENCRYPTION_KEY_FILE"
    chmod 600 "$ENCRYPTION_KEY_FILE"
    
    # Extract public key for reference
    grep "# public key:" "$ENCRYPTION_KEY_FILE" | cut -d' ' -f4 > "$VAULT_DIR/master.pub"
    chmod 644 "$VAULT_DIR/master.pub"
    
    success "Master encryption key generated"
}

# Initialize secrets database
init_secrets_database() {
    log "Initializing secrets database..."
    
    if [[ -f "$SECRETS_DB_FILE" ]]; then
        log "Secrets database already exists"
        return
    fi
    
    # Create SQLite database for secret metadata
    sqlite3 "$SECRETS_DB_FILE" << 'EOF'
CREATE TABLE secrets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_rotated DATETIME DEFAULT CURRENT_TIMESTAMP,
    rotation_interval INTEGER,
    file_path TEXT,
    description TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE rotation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    secret_name TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    old_value_hash TEXT,
    new_value_hash TEXT,
    rotation_reason TEXT
);

CREATE INDEX idx_secrets_name ON secrets(name);
CREATE INDEX idx_secrets_type ON secrets(type);
CREATE INDEX idx_rotation_log_secret ON rotation_log(secret_name);
EOF

    chmod 600 "$SECRETS_DB_FILE"
    success "Secrets database initialized"
}

# Generate secure random password
generate_password() {
    local length=${1:-32}
    local complexity=${2:-"high"}
    
    case $complexity in
        "low")
            # Simple alphanumeric
            tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length"
            ;;
        "medium")
            # Alphanumeric with some symbols
            tr -dc 'A-Za-z0-9!@#$%^&*' < /dev/urandom | head -c "$length"
            ;;
        "high")
            # Full complexity
            tr -dc 'A-Za-z0-9!@#$%^&*()_+-=[]{}|;:,.<>?' < /dev/urandom | head -c "$length"
            ;;
    esac
}

# Generate API key
generate_api_key() {
    local provider=${1:-"generic"}
    
    case $provider in
        "openai")
            echo "sk-$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 48)"
            ;;
        "anthropic")
            echo "ant-$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 40)"
            ;;
        "github")
            echo "ghp_$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 36)"
            ;;
        *)
            # Generic API key format
            echo "$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 64)"
            ;;
    esac
}

# Encrypt and store secret
store_secret() {
    local name="$1"
    local value="$2"
    local secret_type="$3"
    local description="$4"
    local rotation_interval="${5:-0}"
    
    log "Storing secret: $name"
    
    local file_path="$SECRETS_DIR/$secret_type/$name.age"
    local public_key
    public_key=$(cat "$VAULT_DIR/master.pub")
    
    # Encrypt the secret
    echo "$value" | age -r "$public_key" > "$file_path"
    chmod 600 "$file_path"
    
    # Store metadata in database
    sqlite3 "$SECRETS_DB_FILE" << EOF
INSERT OR REPLACE INTO secrets 
(name, type, file_path, description, rotation_interval) 
VALUES ('$name', '$secret_type', '$file_path', '$description', $rotation_interval);
EOF
    
    # Log the action
    local value_hash
    value_hash=$(echo "$value" | sha256sum | cut -d' ' -f1)
    sqlite3 "$SECRETS_DB_FILE" << EOF
INSERT INTO rotation_log 
(secret_name, action, new_value_hash, rotation_reason) 
VALUES ('$name', 'created', '$value_hash', 'initial_creation');
EOF
    
    success "Secret '$name' stored securely"
}

# Retrieve and decrypt secret
get_secret() {
    local name="$1"
    
    local file_path
    file_path=$(sqlite3 "$SECRETS_DB_FILE" "SELECT file_path FROM secrets WHERE name='$name' AND status='active'")
    
    if [[ -z "$file_path" ]] || [[ ! -f "$file_path" ]]; then
        error "Secret '$name' not found"
        return 1
    fi
    
    # Decrypt the secret
    age -d -i "$ENCRYPTION_KEY_FILE" "$file_path" 2>/dev/null || {
        error "Failed to decrypt secret '$name'"
        return 1
    }
}

# Rotate secret
rotate_secret() {
    local name="$1"
    local new_value="$2"
    local rotation_reason="${3:-manual_rotation}"
    
    log "Rotating secret: $name"
    
    # Get old value hash for audit trail
    local old_value
    old_value=$(get_secret "$name")
    local old_value_hash
    old_value_hash=$(echo "$old_value" | sha256sum | cut -d' ' -f1)
    
    # Get secret metadata
    local secret_info
    secret_info=$(sqlite3 "$SECRETS_DB_FILE" "SELECT type, file_path, description, rotation_interval FROM secrets WHERE name='$name' AND status='active'")
    
    if [[ -z "$secret_info" ]]; then
        error "Secret '$name' not found for rotation"
        return 1
    fi
    
    IFS='|' read -r secret_type file_path description rotation_interval <<< "$secret_info"
    
    # Backup old secret
    local backup_file="$BACKUP_DIR/${name}_$(date +%Y%m%d_%H%M%S).age"
    cp "$file_path" "$backup_file"
    
    # Store new secret
    local public_key
    public_key=$(cat "$VAULT_DIR/master.pub")
    echo "$new_value" | age -r "$public_key" > "$file_path"
    
    # Update database
    sqlite3 "$SECRETS_DB_FILE" << EOF
UPDATE secrets 
SET last_rotated = CURRENT_TIMESTAMP 
WHERE name='$name';
EOF
    
    # Log the rotation
    local new_value_hash
    new_value_hash=$(echo "$new_value" | sha256sum | cut -d' ' -f1)
    sqlite3 "$SECRETS_DB_FILE" << EOF
INSERT INTO rotation_log 
(secret_name, action, old_value_hash, new_value_hash, rotation_reason) 
VALUES ('$name', 'rotated', '$old_value_hash', '$new_value_hash', '$rotation_reason');
EOF
    
    success "Secret '$name' rotated successfully"
}

# Auto-generate honeypot secrets
generate_honeypot_secrets() {
    log "Generating honeypot-specific secrets..."
    
    # Generate fake API keys for different providers
    local fake_openai_key
    fake_openai_key=$(generate_api_key "openai")
    store_secret "fake_openai_api_key" "$fake_openai_key" "tokens" "Fake OpenAI API key for honeypot" "$HONEYPOT_TOKEN_ROTATION_INTERVAL"
    
    local fake_github_key
    fake_github_key=$(generate_api_key "github")
    store_secret "fake_github_token" "$fake_github_key" "tokens" "Fake GitHub token for honeypot" "$HONEYPOT_TOKEN_ROTATION_INTERVAL"
    
    local fake_aws_key
    fake_aws_key="AKIA$(tr -dc 'A-Z0-9' < /dev/urandom | head -c 16)"
    store_secret "fake_aws_access_key" "$fake_aws_key" "tokens" "Fake AWS access key for honeypot" "$HONEYPOT_TOKEN_ROTATION_INTERVAL"
    
    local fake_aws_secret
    fake_aws_secret=$(tr -dc 'A-Za-z0-9+/' < /dev/urandom | head -c 40)
    store_secret "fake_aws_secret_key" "$fake_aws_secret" "tokens" "Fake AWS secret key for honeypot" "$HONEYPOT_TOKEN_ROTATION_INTERVAL"
    
    # Generate fake database credentials
    local fake_db_pass
    fake_db_pass=$(generate_password 24 "medium")
    store_secret "fake_db_password" "$fake_db_pass" "passwords" "Fake database password for honeypot" "$DB_PASSWORD_ROTATION_INTERVAL"
    
    # Generate fake Redis password
    local fake_redis_pass
    fake_redis_pass=$(generate_password 32 "high")
    store_secret "fake_redis_password" "$fake_redis_pass" "passwords" "Fake Redis password for honeypot" "$REDIS_PASSWORD_ROTATION_INTERVAL"
    
    # Generate SSH host keys for honeypot
    local temp_dir
    temp_dir=$(mktemp -d)
    ssh-keygen -t rsa -b 4096 -f "$temp_dir/ssh_host_rsa_key" -N "" -C "honeypot@mirage" >/dev/null 2>&1
    store_secret "ssh_host_private_key" "$(cat "$temp_dir/ssh_host_rsa_key")" "certificates" "SSH host private key for honeypot" 0
    store_secret "ssh_host_public_key" "$(cat "$temp_dir/ssh_host_rsa_key.pub")" "certificates" "SSH host public key for honeypot" 0
    rm -rf "$temp_dir"
    
    success "Honeypot secrets generated"
}

# Generate production secrets
generate_production_secrets() {
    log "Generating production secrets..."
    
    # Real Redis password for production
    local redis_password
    redis_password=$(generate_password 32 "high")
    store_secret "redis_password" "$redis_password" "passwords" "Production Redis password" "$REDIS_PASSWORD_ROTATION_INTERVAL"
    
    # Database encryption key
    local db_encryption_key
    db_encryption_key=$(generate_password 64 "high")
    store_secret "db_encryption_key" "$db_encryption_key" "passwords" "Database encryption key" 0
    
    # JWT signing key
    local jwt_secret
    jwt_secret=$(generate_password 64 "high")
    store_secret "jwt_secret" "$jwt_secret" "passwords" "JWT signing secret" "$API_KEY_ROTATION_INTERVAL"
    
    # Session encryption key
    local session_key
    session_key=$(generate_password 32 "high")
    store_secret "session_encryption_key" "$session_key" "passwords" "Session encryption key" "$API_KEY_ROTATION_INTERVAL"
    
    success "Production secrets generated"
}

# Check secrets for rotation
check_rotation_schedule() {
    log "Checking secrets rotation schedule..."
    
    local secrets_to_rotate
    secrets_to_rotate=$(sqlite3 "$SECRETS_DB_FILE" << EOF
SELECT name, type, rotation_interval, 
       julianday('now') - julianday(last_rotated) as days_since_rotation
FROM secrets 
WHERE rotation_interval > 0 
  AND (julianday('now') - julianday(last_rotated)) >= rotation_interval
  AND status = 'active';
EOF
)
    
    if [[ -z "$secrets_to_rotate" ]]; then
        log "No secrets require rotation at this time"
        return
    fi
    
    while IFS='|' read -r name secret_type rotation_interval days_since; do
        warn "Secret '$name' requires rotation (last rotated $days_since days ago)"
        
        case $secret_type in
            "tokens")
                case $name in
                    fake_*)
                        # Rotate fake tokens
                        if [[ $name == *"openai"* ]]; then
                            new_value=$(generate_api_key "openai")
                        elif [[ $name == *"github"* ]]; then
                            new_value=$(generate_api_key "github")
                        elif [[ $name == *"aws_access"* ]]; then
                            new_value="AKIA$(tr -dc 'A-Z0-9' < /dev/urandom | head -c 16)"
                        elif [[ $name == *"aws_secret"* ]]; then
                            new_value=$(tr -dc 'A-Za-z0-9+/' < /dev/urandom | head -c 40)
                        else
                            new_value=$(generate_api_key)
                        fi
                        rotate_secret "$name" "$new_value" "automatic_rotation"
                        ;;
                esac
                ;;
            "passwords")
                # Rotate passwords
                local new_password
                new_password=$(generate_password 32 "high")
                rotate_secret "$name" "$new_password" "automatic_rotation"
                ;;
        esac
    done <<< "$secrets_to_rotate"
}

# Create environment file for Docker Compose
create_env_file() {
    log "Creating environment file for Docker Compose..."
    
    local env_file=".env.mirage"
    
    cat > "$env_file" << EOF
# Project Mirage Environment Variables
# Generated: $(date)
# WARNING: This file contains production secrets - keep secure!

# Database Configuration
DB_ENCRYPTION_KEY=$(get_secret "db_encryption_key" 2>/dev/null || echo "CHANGE_ME_IN_PRODUCTION")

# Redis Configuration  
REDIS_PASSWORD=$(get_secret "redis_password" 2>/dev/null || echo "honeypot_redis_2023")

# JWT and Session Security
JWT_SECRET=$(get_secret "jwt_secret" 2>/dev/null || echo "CHANGE_ME_IN_PRODUCTION")
SESSION_ENCRYPTION_KEY=$(get_secret "session_encryption_key" 2>/dev/null || echo "CHANGE_ME_IN_PRODUCTION")

# Honeypot Fake Credentials
FAKE_OPENAI_API_KEY=$(get_secret "fake_openai_api_key" 2>/dev/null || echo "sk-FAKE_DEV_KEY")
FAKE_GITHUB_TOKEN=$(get_secret "fake_github_token" 2>/dev/null || echo "ghp_FAKE_DEV_TOKEN")
FAKE_AWS_ACCESS_KEY=$(get_secret "fake_aws_access_key" 2>/dev/null || echo "AKIAFAKEACCESSKEY")
FAKE_AWS_SECRET_KEY=$(get_secret "fake_aws_secret_key" 2>/dev/null || echo "FakeSecretKeyForDevelopment")
FAKE_DB_PASSWORD=$(get_secret "fake_db_password" 2>/dev/null || echo "fake_db_password_123")

# Security Configuration
LOG_LEVEL=INFO
ENABLE_DEBUG=false
THREAT_THRESHOLD=medium
DATA_RETENTION_DAYS=90
ENABLE_ENCRYPTION=true

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
FALCO_ENABLED=true
EOF

    chmod 600 "$env_file"
    success "Environment file created: $env_file"
}

# Create secrets rotation cron job
setup_rotation_schedule() {
    log "Setting up automatic secrets rotation schedule..."
    
    # Create rotation script
    cat > /usr/local/bin/mirage-secrets-rotate.sh << 'EOF'
#!/bin/bash
# Automatic secrets rotation for Project Mirage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$(dirname "$0")/secrets_management.sh"

log "Running scheduled secrets rotation check..."
check_rotation_schedule

# Regenerate environment file if any secrets were rotated
if [[ -f "/tmp/secrets_rotated" ]]; then
    log "Secrets were rotated, regenerating environment file..."
    create_env_file
    
    # Restart services if needed (uncomment for production)
    # docker-compose -f docker-compose-security.yml restart
    
    rm -f "/tmp/secrets_rotated"
fi

log "Scheduled secrets rotation check completed"
EOF

    chmod +x /usr/local/bin/mirage-secrets-rotate.sh
    
    # Create cron job for daily rotation check
    echo "0 2 * * * root /usr/local/bin/mirage-secrets-rotate.sh >> /var/log/mirage-secrets-rotation.log 2>&1" > /etc/cron.d/mirage-secrets-rotation
    
    success "Automatic rotation schedule configured"
}

# Generate status report
generate_status_report() {
    log "Generating secrets management status report..."
    
    local total_secrets
    total_secrets=$(sqlite3 "$SECRETS_DB_FILE" "SELECT COUNT(*) FROM secrets WHERE status='active'")
    
    local secrets_by_type
    secrets_by_type=$(sqlite3 "$SECRETS_DB_FILE" "SELECT type, COUNT(*) FROM secrets WHERE status='active' GROUP BY type")
    
    local recent_rotations
    recent_rotations=$(sqlite3 "$SECRETS_DB_FILE" "SELECT COUNT(*) FROM rotation_log WHERE timestamp > datetime('now', '-7 days')")
    
    cat > /tmp/mirage-secrets-status.txt << EOF
Project Mirage Secrets Management Status Report
==============================================
Generated: $(date)
Host: $(hostname)

=== Summary ===
Total Active Secrets: $total_secrets
Recent Rotations (7 days): $recent_rotations
Master Key Location: $ENCRYPTION_KEY_FILE
Secrets Database: $SECRETS_DB_FILE

=== Secrets by Type ===
$secrets_by_type

=== Rotation Schedule ===
$(sqlite3 "$SECRETS_DB_FILE" "
SELECT name, type, 
       CASE 
         WHEN rotation_interval = 0 THEN 'Never'
         ELSE rotation_interval || ' days'
       END as interval,
       CASE 
         WHEN rotation_interval = 0 THEN 'N/A'
         ELSE CAST(julianday('now') - julianday(last_rotated) as INTEGER) || ' days ago'
       END as last_rotated
FROM secrets 
WHERE status='active' 
ORDER BY type, name")

=== Security Features ===
✓ AES-256 encryption for all secrets
✓ Age encryption with secure key management
✓ Automatic rotation scheduling
✓ Comprehensive audit logging
✓ Secure file permissions (600)
✓ Backup retention for rotated secrets
✓ Environment file generation
✓ Docker Compose integration

=== Recent Activity ===
$(sqlite3 "$SECRETS_DB_FILE" "
SELECT datetime(timestamp, 'localtime') as time, secret_name, action, rotation_reason
FROM rotation_log 
ORDER BY timestamp DESC 
LIMIT 10")

=== Maintenance Commands ===
List all secrets: sqlite3 $SECRETS_DB_FILE "SELECT * FROM secrets"
Check rotation schedule: $0 check-rotation
Rotate specific secret: $0 rotate-secret <name> <new_value>
Generate new environment: $0 create-env
View audit log: sqlite3 $SECRETS_DB_FILE "SELECT * FROM rotation_log ORDER BY timestamp DESC"

=== Security Recommendations ===
1. Regularly backup the master key and secrets database
2. Monitor rotation logs for unauthorized changes
3. Ensure proper file permissions are maintained
4. Test secret retrieval periodically
5. Keep the master key secure and offline when possible
6. Implement additional authentication for critical operations
EOF

    success "Status report generated: /tmp/mirage-secrets-status.txt"
    cat /tmp/mirage-secrets-status.txt
}

# Main execution function
main() {
    local action="${1:-init}"
    
    case $action in
        "init")
            log "Initializing Project Mirage secrets management system..."
            check_prerequisites
            init_secure_directories
            generate_master_key
            init_secrets_database
            generate_honeypot_secrets
            generate_production_secrets
            create_env_file
            setup_rotation_schedule
            generate_status_report
            success "Secrets management system initialized successfully!"
            ;;
        "check-rotation")
            check_rotation_schedule
            ;;
        "rotate-secret")
            if [[ $# -lt 3 ]]; then
                error "Usage: $0 rotate-secret <name> <new_value> [reason]"
                exit 1
            fi
            rotate_secret "$2" "$3" "${4:-manual_rotation}"
            ;;
        "get-secret")
            if [[ $# -lt 2 ]]; then
                error "Usage: $0 get-secret <name>"
                exit 1
            fi
            get_secret "$2"
            ;;
        "create-env")
            create_env_file
            ;;
        "status")
            generate_status_report
            ;;
        *)
            error "Unknown action: $action"
            echo "Usage: $0 {init|check-rotation|rotate-secret|get-secret|create-env|status}"
            exit 1
            ;;
    esac
}

# Execute main function with all arguments
main "$@"
