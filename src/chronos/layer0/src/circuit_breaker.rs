use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

// Constants
#[cfg(not(test))]
const FAILURE_THRESHOLD: usize = 10;
#[cfg(test)]
const FAILURE_THRESHOLD: usize = 3; // Faster trip for tests

#[cfg(not(test))]
const RESET_TIMEOUT_MS: u64 = 30_000; // 30 seconds
#[cfg(test)]
const RESET_TIMEOUT_MS: u64 = 500; // Faster recovery for tests

#[cfg(not(test))]
const LATENCY_THRESHOLD_MS: u64 = 5;
#[cfg(test)]
const LATENCY_THRESHOLD_MS: u64 = 1; // Allow quick pass/fail in tests

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum CircuitState {
    Closed = 0,   // Normal operation
    Open = 1,     // Tripped, failing fast
    HalfOpen = 2, // Recovering, allowing one test request
}

impl From<usize> for CircuitState {
    fn from(value: usize) -> Self {
        match value {
            0 => CircuitState::Closed,
            1 => CircuitState::Open,
            2 => CircuitState::HalfOpen,
            _ => CircuitState::Closed,
        }
    }
}

pub struct CircuitBreaker {
    state: AtomicUsize,
    failure_count: AtomicUsize,
    last_failure_time: AtomicU64,
}

impl CircuitBreaker {
    pub const fn new() -> Self {
        Self {
            state: AtomicUsize::new(0), // Closed
            failure_count: AtomicUsize::new(0),
            last_failure_time: AtomicU64::new(0),
        }
    }

    /// Check if a request should be allowed to proceed
    pub fn check_allow(&self) -> bool {
        let state = CircuitState::from(self.state.load(Ordering::Acquire));

        match state {
            CircuitState::Closed => true,
            CircuitState::Open => {
                // Check if reset timeout has passed
                let now = current_time_ms();
                let last_fail = self.last_failure_time.load(Ordering::Acquire);
                
                if now >= last_fail + RESET_TIMEOUT_MS {
                    // Try to transition to HalfOpen
                    // CompareExchange ensures only one thread does this
                    self.state.compare_exchange(
                        CircuitState::Open as usize,
                        CircuitState::HalfOpen as usize,
                        Ordering::SeqCst,
                        Ordering::Relaxed
                    ).is_ok()
                } else {
                    false
                }
            }
            CircuitState::HalfOpen => {
                // In HalfOpen, we only allow one request at a time (conceptually).
                // For simplicity here, we allow it. If it fails, we go back to Open.
                // If it succeeds, we go to Closed.
                true
            }
        }
    }

    /// Record the result of an operation
    pub fn record_result(&self, duration_ms: u64) {
        let state = CircuitState::from(self.state.load(Ordering::Acquire));

        if duration_ms > LATENCY_THRESHOLD_MS {
            self.handle_failure(state);
        } else {
            self.handle_success(state);
        }
    }

    fn handle_failure(&self, state: CircuitState) {
        match state {
            CircuitState::Closed => {
                let count = self.failure_count.fetch_add(1, Ordering::SeqCst) + 1;
                if count >= FAILURE_THRESHOLD {
                    self.trip_circuit();
                }
            }
            CircuitState::HalfOpen => {
                // If we fail in HalfOpen, go back to Open immediately
                self.trip_circuit();
            }
            CircuitState::Open => {
                // Already open, just update time
                self.last_failure_time.store(current_time_ms(), Ordering::Release);
            }
        }
    }

    fn handle_success(&self, state: CircuitState) {
        match state {
            CircuitState::HalfOpen => {
                // Success in HalfOpen -> Reset to Closed
                self.reset_circuit();
            }
            CircuitState::Closed => {
                // Optional: Decay failure count over time?
                // For now, we just reset it on success to be forgiving
                self.failure_count.store(0, Ordering::Relaxed);
            }
            CircuitState::Open => {
                // Should not happen often if check_allow is respected, 
                // but if a request slipped through and succeeded, good for us.
            }
        }
    }

    fn trip_circuit(&self) {
        self.state.store(CircuitState::Open as usize, Ordering::SeqCst);
        self.last_failure_time.store(current_time_ms(), Ordering::SeqCst);
    }

    fn reset_circuit(&self) {
        self.state.store(CircuitState::Closed as usize, Ordering::SeqCst);
        self.failure_count.store(0, Ordering::SeqCst);
    }

    #[cfg(test)]
    fn set_state_for_test(&self, state: CircuitState) {
        self.state.store(state as usize, Ordering::SeqCst);
    }

    #[cfg(test)]
    fn set_last_failure_for_test(&self, millis: u64) {
        self.last_failure_time.store(millis, Ordering::SeqCst);
    }
    
    pub fn get_state_name(&self) -> &'static str {
        match CircuitState::from(self.state.load(Ordering::Relaxed)) {
            CircuitState::Closed => "Closed",
            CircuitState::Open => "Open",
            CircuitState::HalfOpen => "HalfOpen",
        }
    }
}

fn current_time_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_millis() as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trip_and_recover_flow() {
        let cb = CircuitBreaker::new();

        // Start Closed
        assert_eq!(cb.get_state_name(), "Closed");

        // Trip to Open
        for _ in 0..FAILURE_THRESHOLD {
            cb.record_result(LATENCY_THRESHOLD_MS + 10);
        }
        assert_eq!(cb.get_state_name(), "Open");

        // Force timeout to elapse
        let past = current_time_ms().saturating_sub(RESET_TIMEOUT_MS + 1);
        cb.set_last_failure_for_test(past);

        // Next allow should transition to HalfOpen
        assert!(cb.check_allow());
        assert_eq!(cb.get_state_name(), "HalfOpen");

        // Success in HalfOpen should reset to Closed
        cb.record_result(LATENCY_THRESHOLD_MS - 1);
        assert_eq!(cb.get_state_name(), "Closed");
    }

    #[test]
    fn half_open_failure_reopens() {
        let cb = CircuitBreaker::new();

        cb.set_state_for_test(CircuitState::HalfOpen);
        cb.record_result(LATENCY_THRESHOLD_MS + 10);

        assert_eq!(cb.get_state_name(), "Open");
    }
}
