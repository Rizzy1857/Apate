// Rust Protocol Library
// --------------------
// Common utilities and types for the Rust protocol server

pub mod protocol;
pub mod utils;

use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtocolMessage {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub source: SocketAddr,
    pub message_type: String,
    pub payload: String,
    pub fingerprint: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThreatEvent {
    pub event_id: String,
    pub timestamp: DateTime<Utc>,
    pub source_ip: String,
    pub event_type: String,
    pub description: String,
    pub severity: String,
    pub metadata: serde_json::Value,
}

pub fn generate_fingerprint(data: &[u8]) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    
    let mut hasher = DefaultHasher::new();
    data.hash(&mut hasher);
    format!("{:x}", hasher.finish())
}
