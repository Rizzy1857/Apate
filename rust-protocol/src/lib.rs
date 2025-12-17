// Rust Protocol Library
// --------------------
// Common utilities and types for the Rust protocol server

pub mod circuit_breaker;
pub mod protocol;
pub mod utils;
pub mod reducers;

use chrono::{DateTime, Utc};
#[cfg(feature = "pyo3")]
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;

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

#[cfg(feature = "pyo3")]
mod python_bindings {
    use super::*;
    use std::panic;

    /// Python module for the Rust protocol library
    #[pymodule]
    fn rust_protocol(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
        // Expose utility functions
        m.add_function(wrap_pyfunction!(validate_ip_py, m)?)?;
        m.add_function(wrap_pyfunction!(calculate_entropy_py, m)?)?;
        m.add_function(wrap_pyfunction!(generate_fingerprint_py, m)?)?;
        m.add_function(wrap_pyfunction!(detect_threats_py, m)?)?;
        m.add_function(wrap_pyfunction!(get_circuit_breaker_status_py, m)?)?;

        Ok(())
    }

    #[pyfunction]
    #[pyo3(name = "validate_ip")]
    fn validate_ip_py(ip: &str) -> PyResult<bool> {
        let result = panic::catch_unwind(|| {
            if ip.len() > 45 {
                // Max IPv6 length
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "IP address too long",
                ));
            }
            Ok(utils::is_valid_ip(ip))
        });

        match result {
            Ok(val) => val,
            Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Rust panic in validate_ip",
            )),
        }
    }

    #[pyfunction]
    #[pyo3(name = "calculate_entropy")]
    fn calculate_entropy_py(py: Python, data: &str) -> PyResult<f64> {
        if data.len() > 1_000_000 {
            // 1MB limit for entropy calculation
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Input data too large for entropy calculation",
            ));
        }

        // Release GIL for potentially expensive calculation
        py.allow_threads(|| {
            let result = panic::catch_unwind(|| Ok(utils::calculate_entropy(data)));

            match result {
                Ok(val) => val,
                Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
                    "Rust panic in calculate_entropy",
                )),
            }
        })
    }

    #[pyfunction]
    #[pyo3(name = "generate_fingerprint")]
    fn generate_fingerprint_py(data: &str) -> PyResult<String> {
        let result = panic::catch_unwind(|| {
            if data.len() > 1_000_000 {
                // 1MB limit
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Input data too large for fingerprinting",
                ));
            }
            Ok(generate_fingerprint(data.as_bytes()))
        });

        match result {
            Ok(val) => val,
            Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Rust panic in generate_fingerprint",
            )),
        }
    }

    use crate::circuit_breaker::CircuitBreaker;

    static CIRCUIT_BREAKER: CircuitBreaker = CircuitBreaker::new();

    #[pyfunction]
    #[pyo3(name = "detect_threats")]
    fn detect_threats_py(py: Python, payload: &str, source_ip: &str) -> PyResult<Option<String>> {
        // 1. Check Circuit Breaker
        if !CIRCUIT_BREAKER.check_allow() {
            // Fail open: Return None (no threat detected) to avoid blocking traffic
            // In a real system, we might want to log this bypass
            return Ok(None);
        }

        if payload.len() > 1_000_000 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Payload too large for threat detection",
            ));
        }

        let payload = payload.to_string();
        let source_ip = source_ip.to_string();

        py.allow_threads(move || {
            let start_time = std::time::Instant::now();

            let result = panic::catch_unwind(|| {
                // Create a dummy message for analysis
                let source_addr = format!("{}:0", source_ip)
                    .parse()
                    .unwrap_or_else(|_| "0.0.0.0:0".parse().unwrap());

                let message = ProtocolMessage {
                    id: "temp".to_string(),
                    timestamp: Utc::now(),
                    source: source_addr,
                    message_type: "unknown".to_string(),
                    payload,
                    fingerprint: None,
                };

                let threat = protocol::analyze_for_threats(&message);

                // Return JSON representation of the threat
                if let Some(t) = &threat {
                    Ok(Some(serde_json::to_string(t).unwrap_or_default()))
                } else {
                    Ok(None)
                }
            });

            // 2. Record Latency
            let duration = start_time.elapsed().as_millis() as u64;
            CIRCUIT_BREAKER.record_result(duration);

            match result {
                Ok(val) => val,
                Err(_) => Err(pyo3::exceptions::PyRuntimeError::new_err(
                    "Rust panic in detect_threats",
                )),
            }
        })
    }

    #[pyfunction]
    #[pyo3(name = "get_circuit_breaker_status")]
    fn get_circuit_breaker_status_py() -> String {
        CIRCUIT_BREAKER.get_state_name().to_string()
    }
} // end mod python_bindings
