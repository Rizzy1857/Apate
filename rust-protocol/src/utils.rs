// Utility functions
// ----------------
// Common utility functions for the protocol library

use std::time::{SystemTime, UNIX_EPOCH};
use std::net::IpAddr;
use std::str::FromStr;

/// Get current timestamp in milliseconds
pub fn current_timestamp_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0) // Fallback to 0 if system time is before epoch (unlikely but safe)
}

/// Validate if a string is a valid IP address
pub fn is_valid_ip(ip_str: &str) -> bool {
    IpAddr::from_str(ip_str).is_ok()
}

/// Extract IP address from various formats
pub fn extract_ip(input: &str) -> Option<String> {
    // Try to extract IP from formats like "192.168.1.1:8080"
    if let Some(colon_pos) = input.find(':') {
        let ip_part = &input[..colon_pos];
        if is_valid_ip(ip_part) {
            return Some(ip_part.to_string());
        }
    }
    
    // Try the input as-is
    if is_valid_ip(input) {
        return Some(input.to_string());
    }
    
    None
}

/// Calculate entropy of a string (useful for detecting random/encrypted data)
pub fn calculate_entropy(data: &str) -> f64 {
    use std::collections::HashMap;
    
    if data.is_empty() {
        return 0.0;
    }
    
    let mut frequency = HashMap::new();
    for byte in data.bytes() {
        *frequency.entry(byte).or_insert(0) += 1;
    }
    
    let len = data.len() as f64;
    let mut entropy = 0.0;
    
    for count in frequency.values() {
        let probability = *count as f64 / len;
        entropy -= probability * probability.log2();
    }
    
    entropy
}

/// Check if data looks like base64 encoded content
pub fn is_likely_base64(data: &str) -> bool {
    if data.is_empty() || data.len() % 4 != 0 {
        return false;
    }
    
    // Check if all characters are valid base64 characters
    data.chars().all(|c| {
        c.is_ascii_alphanumeric() || c == '+' || c == '/' || c == '='
    })
}

/// Sanitize string for logging (remove potentially dangerous characters)
pub fn sanitize_for_log(input: &str) -> String {
    input
        .chars()
        .map(|c| {
            if c.is_control() {
                '.'
            } else {
                c
            }
        })
        .collect()
}

/// Extract domain from URL
pub fn extract_domain(url: &str) -> Option<String> {
    if let Ok(parsed_url) = url::Url::parse(url) {
        parsed_url.host_str().map(|s| s.to_string())
    } else {
        None
    }
}

/// Check if a port number is in a suspicious range
pub fn is_suspicious_port(port: u16) -> bool {
    match port {
        // Common backdoor/malware ports
        31337 | 12345 | 54321 | 9999 | 1337 => true,
        // Uncommon high ports that might indicate scanning
        port if port > 60000 => true,
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_valid_ip() {
        assert!(is_valid_ip("192.168.1.1"));
        assert!(is_valid_ip("::1"));
        assert!(!is_valid_ip("invalid.ip"));
    }

    #[test]
    fn test_extract_ip() {
        assert_eq!(extract_ip("192.168.1.1:8080"), Some("192.168.1.1".to_string()));
        assert_eq!(extract_ip("192.168.1.1"), Some("192.168.1.1".to_string()));
        assert_eq!(extract_ip("invalid"), None);
    }

    #[test]
    fn test_calculate_entropy() {
        assert!(calculate_entropy("aaaa") < calculate_entropy("abcd"));
        assert_eq!(calculate_entropy(""), 0.0);
    }

    #[test]
    fn test_is_likely_base64() {
        assert!(is_likely_base64("SGVsbG8gV29ybGQ="));
        assert!(!is_likely_base64("Hello World"));
    }

    #[test]
    fn test_is_suspicious_port() {
        assert!(is_suspicious_port(31337));
        assert!(is_suspicious_port(65000));
        assert!(!is_suspicious_port(80));
        assert!(!is_suspicious_port(443));
    }
}
