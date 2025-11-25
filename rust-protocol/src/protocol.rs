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

use regex::Regex;
use std::sync::OnceLock;

// Static Regex Patterns
fn sql_injection_regex() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| Regex::new(r"(?i)(union\s+select|select\s+.*\s+from|insert\s+into|delete\s+from|drop\s+table|update\s+.*\s+set)").unwrap())
}

fn directory_traversal_regex() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| Regex::new(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)").unwrap())
}

fn xss_regex() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| Regex::new(r"(?i)(<script|javascript:|onload=|onerror=|onclick=)").unwrap())
}

fn command_injection_regex() -> &'static Regex {
    static CELL: OnceLock<Regex> = OnceLock::new();
    CELL.get_or_init(|| Regex::new(r"(?i)(;|\||&|\$\(|\`|/bin/sh|/bin/bash)").unwrap())
}

/// Convert a ProtocolMessage to a ThreatEvent if it contains suspicious patterns
pub fn analyze_for_threats(message: &ProtocolMessage) -> Option<ThreatEvent> {
    // We don't need to lowercase manually as regexes are case-insensitive (?i)
    // This saves an allocation
    
    let payload = &message.payload;
    
    // Check for common attack patterns using Regex
    // The regex crate guarantees linear time execution (O(m * n)), preventing ReDoS
    
    let mut threat_type = None;
    let mut description = None;
    let mut severity = "low";

    if directory_traversal_regex().is_match(payload) {
        threat_type = Some("directory_traversal");
        description = Some("Potential directory traversal attack detected");
        severity = "high";
    } else if sql_injection_regex().is_match(payload) {
        threat_type = Some("sql_injection");
        description = Some("Potential SQL injection attempt detected");
        severity = "high";
    } else if xss_regex().is_match(payload) {
        threat_type = Some("xss_attempt");
        description = Some("Potential XSS attack detected");
        severity = "medium";
    } else if command_injection_regex().is_match(payload) {
        threat_type = Some("command_injection");
        description = Some("Potential command injection attempt detected");
        severity = "critical";
    }
    
    if let (Some(t_type), Some(desc)) = (threat_type, description) {
        return Some(ThreatEvent {
            event_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            source_ip: message.source.ip().to_string(),
            event_type: t_type.to_string(),
            description: desc.to_string(),
            severity: severity.to_string(),
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sql_injection_detection() {
        let msg = ProtocolMessage {
            id: "test".to_string(),
            timestamp: Utc::now(),
            source: "127.0.0.1:1234".parse().unwrap(),
            message_type: "http".to_string(),
            payload: "user=admin' UNION SELECT 1,2,3--".to_string(),
            fingerprint: None,
        };
        
        let threat = analyze_for_threats(&msg);
        assert!(threat.is_some());
        assert_eq!(threat.unwrap().event_type, "sql_injection");
    }

    #[test]
    fn test_directory_traversal_detection() {
        let msg = ProtocolMessage {
            id: "test".to_string(),
            timestamp: Utc::now(),
            source: "127.0.0.1:1234".parse().unwrap(),
            message_type: "http".to_string(),
            payload: "GET /../../etc/passwd HTTP/1.1".to_string(),
            fingerprint: None,
        };
        
        let threat = analyze_for_threats(&msg);
        assert!(threat.is_some());
        assert_eq!(threat.unwrap().event_type, "directory_traversal");
    }

    #[test]
    fn test_xss_detection() {
        let msg = ProtocolMessage {
            id: "test".to_string(),
            timestamp: Utc::now(),
            source: "127.0.0.1:1234".parse().unwrap(),
            message_type: "http".to_string(),
            payload: "<script>alert(1)</script>".to_string(),
            fingerprint: None,
        };
        
        let threat = analyze_for_threats(&msg);
        assert!(threat.is_some());
        assert_eq!(threat.unwrap().event_type, "xss_attempt");
    }

    #[test]
    fn test_command_injection_detection() {
        let msg = ProtocolMessage {
            id: "test".to_string(),
            timestamp: Utc::now(),
            source: "127.0.0.1:1234".parse().unwrap(),
            message_type: "ssh".to_string(),
            payload: "cat file; rm -rf /".to_string(),
            fingerprint: None,
        };
        
        let threat = analyze_for_threats(&msg);
        assert!(threat.is_some());
        assert_eq!(threat.unwrap().event_type, "command_injection");
    }

    #[test]
    fn test_safe_payload() {
        let msg = ProtocolMessage {
            id: "test".to_string(),
            timestamp: Utc::now(),
            source: "127.0.0.1:1234".parse().unwrap(),
            message_type: "http".to_string(),
            payload: "GET /index.html HTTP/1.1".to_string(),
            fingerprint: None,
        };
        
        let threat = analyze_for_threats(&msg);
        assert!(threat.is_none());
    }
}
