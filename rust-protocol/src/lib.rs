// Rust Protocol Library
// --------------------
// Common utilities and types for the Rust protocol server

pub mod circuit_breaker;
pub mod protocol;
pub mod reducers;
pub mod utils;

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
    use crate::reducers::{classify_protocol_fast, NoiseDetector};
    use pyo3::types::PyDict;
    use std::panic;
    use std::sync::OnceLock;

    /// Static NoiseDetector instance
    static NOISE_DETECTOR: OnceLock<NoiseDetector> = OnceLock::new();

    fn get_noise_detector() -> &'static NoiseDetector {
        NOISE_DETECTOR.get_or_init(|| NoiseDetector::new())
    }

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
    fn detect_threats_py<'py>(
        py: Python<'py>,
        payload: &str,
        source_ip: &str,
    ) -> PyResult<Option<Bound<'py, PyDict>>> {
        // 1. Check Circuit Breaker
        if !CIRCUIT_BREAKER.check_allow() {
            return Ok(None);
        }

        if payload.len() > 1_000_000 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Payload too large for threat detection",
            ));
        }

        // Pre-calculation for Fast Classification & Noise (Low Latency)
        let payload_bytes = payload.as_bytes();
        let proto_guess = classify_protocol_fast(payload_bytes);
        let noise_hint = get_noise_detector().check_hint(payload_bytes).is_some();

        let payload_str = payload.to_string();
        let source_ip_str = source_ip.to_string();

        // Run deep analysis in threaded block
        let (threat, duration_ms) = py.allow_threads(move || {
            let start_time = std::time::Instant::now();

            let result = panic::catch_unwind(|| {
                // Create a dummy message for analysis
                let source_addr = format!("{}:0", source_ip_str)
                    .parse()
                    .unwrap_or_else(|_| "0.0.0.0:0".parse().unwrap());

                let message = ProtocolMessage {
                    id: "temp".to_string(),
                    timestamp: Utc::now(),
                    source: source_addr,
                    message_type: proto_guess.as_str().to_string(), // Use fast guess
                    payload: payload_str,
                    fingerprint: None,
                };

                protocol::analyze_for_threats(&message)
            });

            let duration = start_time.elapsed().as_millis() as u64;
            CIRCUIT_BREAKER.record_result(duration);

            match result {
                Ok(val) => (val, duration),
                Err(_) => (None, duration), // Swallow panic for now, or bubble up error
            }
        });

        // 3. Construct Python Dict Return
        // Return None if nothing interesting (no threat, no noise, known proto?)
        // Actually, we should return metadata if requested.
        // For now, if threat detected OR noise detected, return Struct.

        if threat.is_none() && !noise_hint {
            return Ok(None);
        }

        let dict = PyDict::new_bound(py);
        dict.set_item("protocol", proto_guess.as_str())?;
        dict.set_item("is_noise", noise_hint)?;
        dict.set_item("latency_ms", duration_ms)?;

        if let Some(t) = threat {
            // API schema: threat_detected (bool), severity (str), event_type (str), description (str)
            dict.set_item("threat_detected", true)?;
            dict.set_item("severity", t.severity)?;
            dict.set_item("event_type", t.event_type)?;
            dict.set_item("description", t.description)?;

            // Raw JSON for complex metadata if needed
            dict.set_item("raw_metadata", t.metadata.to_string())?;
        } else {
            dict.set_item("threat_detected", false)?;
        }

        Ok(Some(dict))
    }

    #[pyfunction]
    #[pyo3(name = "get_circuit_breaker_status")]
    fn get_circuit_breaker_status_py() -> String {
        CIRCUIT_BREAKER.get_state_name().to_string()
    }
} // end mod python_bindings
