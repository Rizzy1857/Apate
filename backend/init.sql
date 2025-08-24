-- Database initialization for Apate Honeypot
-- Creates necessary tables and indexes for development

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    source_ip INET NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_suspicious BOOLEAN DEFAULT FALSE,
    threat_score FLOAT DEFAULT 0.0,
    user_agent TEXT,
    metadata JSONB
);

-- Honeytokens table
CREATE TABLE IF NOT EXISTS honeytokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_id VARCHAR(255) UNIQUE NOT NULL,
    token_type VARCHAR(100) NOT NULL,
    token_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    triggered_at TIMESTAMP WITH TIME ZONE,
    trigger_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- Interactions table
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    interaction_type VARCHAR(100) NOT NULL,
    command TEXT,
    response TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by VARCHAR(255)
);

-- Threat intelligence table
CREATE TABLE IF NOT EXISTS threat_intel (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    indicator_type VARCHAR(50) NOT NULL,
    indicator_value VARCHAR(255) NOT NULL,
    threat_type VARCHAR(100),
    confidence_score FLOAT,
    source VARCHAR(255),
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    UNIQUE(indicator_type, indicator_value)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_sessions_source_ip ON sessions(source_ip);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_service_type ON sessions(service_type);
CREATE INDEX IF NOT EXISTS idx_honeytokens_token_id ON honeytokens(token_id);
CREATE INDEX IF NOT EXISTS idx_honeytokens_token_type ON honeytokens(token_type);
CREATE INDEX IF NOT EXISTS idx_interactions_session_id ON interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_session_id ON alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_threat_intel_indicator ON threat_intel(indicator_type, indicator_value);

-- Insert some sample data for development
INSERT INTO honeytokens (token_id, token_type, token_data) VALUES 
('ht_admin_001', 'credential', '{"username": "backup_admin", "password": "B@ckup2023!", "service": "ssh"}'),
('ht_api_001', 'api_key', '{"key": "sk-1234567890abcdef", "service": "openai", "permissions": ["read", "write"]}'),
('ht_aws_001', 'aws_key', '{"access_key": "AKIA1234567890ABCDEF", "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "region": "us-east-1"}')
ON CONFLICT (token_id) DO NOTHING;
