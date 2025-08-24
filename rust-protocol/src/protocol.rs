// Protocol handling utilities
// -------------------------
// Core protocol parsing and message handling functionality

use crate::{ProtocolMessage, ThreatEvent, generate_fingerprint};
use serde_json;
use std::net::SocketAddr;
use chrono::Utc;
use uuid::Uuid;

/// Parse incoming protocol data and create a ProtocolMessage
pub fn parse_message(data: &[u8], source: SocketAddr) -> Result<ProtocolMessage, Box<dyn std::error::Error>> {
    let payload = String::from_utf8_lossy(data);
    let fingerprint = generate_fingerprint(data);
    
    // Detect message type based on content patterns
    let message_type = detect_message_type(&payload);
    
    Ok(ProtocolMessage {
        id: Uuid::new_v4().to_string(),
        timestamp: Utc::now(),
        source,
        message_type,
        payload: payload.to_string(),
        fingerprint: Some(fingerprint),
    })
}

/// Detect the type of protocol message based on content
fn detect_message_type(payload: &str) -> String {
    if payload.contains("SSH-") {
        "ssh_handshake".to_string()
    } else if payload.contains("HTTP/") {
        "http_request".to_string()
    } else if payload.contains("FTP") {
        "ftp_command".to_string()
    } else if payload.contains("SMTP") {
        "smtp_command".to_string()
    } else {
        "unknown".to_string()
    }
}

/// Convert a ProtocolMessage to a ThreatEvent if it contains suspicious patterns
pub fn analyze_for_threats(message: &ProtocolMessage) -> Option<ThreatEvent> {
    let payload_lower = message.payload.to_lowercase();
    
    // Check for common attack patterns
    if payload_lower.contains("../../") || payload_lower.contains("..\\") {
        return Some(ThreatEvent {
            event_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            source_ip: message.source.ip().to_string(),
            event_type: "directory_traversal".to_string(),
            description: "Potential directory traversal attack detected".to_string(),
            severity: "high".to_string(),
            metadata: serde_json::json!({
                "message_id": message.id,
                "message_type": message.message_type,
                "fingerprint": message.fingerprint
            }),
        });
    }
    
    if payload_lower.contains("select") && payload_lower.contains("union") {
        return Some(ThreatEvent {
            event_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            source_ip: message.source.ip().to_string(),
            event_type: "sql_injection".to_string(),
            description: "Potential SQL injection attempt detected".to_string(),
            severity: "high".to_string(),
            metadata: serde_json::json!({
                "message_id": message.id,
                "message_type": message.message_type,
                "fingerprint": message.fingerprint
            }),
        });
    }
    
    if payload_lower.contains("<script") || payload_lower.contains("javascript:") {
        return Some(ThreatEvent {
            event_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            source_ip: message.source.ip().to_string(),
            event_type: "xss_attempt".to_string(),
            description: "Potential XSS attack detected".to_string(),
            severity: "medium".to_string(),
            metadata: serde_json::json!({
                "message_id": message.id,
                "message_type": message.message_type,
                "fingerprint": message.fingerprint
            }),
        });
    }
    
    None
}

/// Serialize a ProtocolMessage to JSON
pub fn serialize_message(message: &ProtocolMessage) -> Result<String, serde_json::Error> {
    serde_json::to_string(message)
}

/// Deserialize JSON to ProtocolMessage
pub fn deserialize_message(json: &str) -> Result<ProtocolMessage, serde_json::Error> {
    serde_json::from_str(json)
}
