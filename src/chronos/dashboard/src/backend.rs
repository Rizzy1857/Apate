use redis::AsyncCommands;
use tokio_postgres::NoTls;
use std::time::Duration;
use chrono::NaiveDateTime;
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{BTreeMap, HashMap};

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ProvenanceEntry {
    pub blob_hash: String,
    pub model: String,
    pub file_class: String,
    pub generation_source: String,
    pub prompt_version: String,
    pub generated_at: String,
    pub validated: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ProvenanceSummary {
    pub total_blobs: i32,
    pub validated_blobs: i32,
    pub llm_blobs: i32,
    pub fallback_blobs: i32,
    pub template_blobs: i32,
    pub by_file_class: Vec<(String, i32)>,
    pub recent_entries: Vec<ProvenanceEntry>,
}

// ── Data Structures ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct AuditEvent {
    pub id: i64,
    pub session_id: Option<String>,
    pub timestamp: NaiveDateTime,
    pub operation: Option<String>,
    pub path: Option<String>,
    pub inode: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandEntry {
    pub command_id: Option<String>,
    pub outcome: Option<String>,
    pub exit_status: Option<i32>,
    pub server_elapsed_seconds: Option<f64>,
    pub response_bytes: Option<u64>,
    pub timestamp: Option<String>,
    pub command: Option<String>,
    pub techniques: Option<Vec<String>>,
    pub risk_score: Option<i64>,
    pub signatures: Option<Vec<String>>,
}

#[cfg(test)]
mod research_tests {
    use super::CommandEntry;

    #[test]
    fn legacy_command_is_not_assumed_successful() {
        let command: CommandEntry = serde_json::from_str(r#"{"command":"id"}"#).unwrap();
        assert!(command.outcome.is_none());
        assert!(command.server_elapsed_seconds.is_none());
    }

    #[test]
    fn measured_outcome_survives_deserialization() {
        let command: CommandEntry = serde_json::from_str(
            r#"{"command":"id","command_id":"a","outcome":"emulated_success","exit_status":0,"server_elapsed_seconds":0.125,"response_bytes":42}"#
        ).unwrap();
        assert_eq!(command.outcome.as_deref(), Some("emulated_success"));
        assert_eq!(command.server_elapsed_seconds, Some(0.125));
        assert_eq!(command.response_bytes, Some(42));
    }
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct SessionSummary {
    pub session_id: String,
    pub start_time: Option<NaiveDateTime>,
    pub end_time: Option<NaiveDateTime>,
    pub duration_seconds: Option<i32>,
    pub detection_status: Option<String>,
    pub detection_confidence: Option<f64>,
    pub exit_reason: Option<String>,
    pub first_suspicious_command: Option<String>,
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct SessionDetail {
    pub session_id: String,
    pub start_time: Option<NaiveDateTime>,
    pub end_time: Option<NaiveDateTime>,
    pub duration_seconds: Option<i32>,
    pub detection_status: Option<String>,
    pub detection_confidence: Option<f64>,
    pub exit_reason: Option<String>,
    pub first_suspicious_command: Option<String>,
    pub commands: Vec<CommandEntry>,
    pub visited_files: Vec<String>,
    pub traversal_graph: serde_json::Value,
    pub skill_assessment: Option<serde_json::Value>,
}

// ── Messages ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub enum BackendMessage {
    ExportResult(Result<String, String>),
    RedisConnected(bool),
    PostgresConnected(bool),
    AuditLogs(Vec<AuditEvent>),
    TotalFiles(i32),
    ActiveSessionCount(i32),
    SessionList(Vec<SessionSummary>),
    SessionDetailResult(Box<Option<SessionDetail>>),
    ProvenanceSnapshot(ProvenanceSummary),
}

#[derive(Debug, Clone)]
pub enum BackendRequest {
    ExportSession { session_id: String, destination: String },
    FetchSessionDetail(String),  // session_id
}

// ── Backend Loop ────────────────────────────────────────────────────────────

fn database_config() -> Result<tokio_postgres::Config, String> {
    let password = std::env::var("POSTGRES_PASSWORD")
        .map_err(|_| "Set POSTGRES_PASSWORD for the research database".to_string())?;
    let port = std::env::var("POSTGRES_PORT").unwrap_or_else(|_| "5433".into())
        .parse::<u16>().map_err(|_| "POSTGRES_PORT must be a valid port".to_string())?;
    let mut config = tokio_postgres::Config::new();
    config.host(&std::env::var("POSTGRES_HOST").unwrap_or_else(|_| "127.0.0.1".into()));
    config.port(port);
    config.user(&std::env::var("POSTGRES_USER").unwrap_or_else(|_| "chronos".into()));
    config.dbname(&std::env::var("POSTGRES_DB").unwrap_or_else(|_| "chronos".into()));
    config.password(password);
    config.connect_timeout(Duration::from_secs(5));
    Ok(config)
}

pub async fn start_backend(
    tx: flume::Sender<BackendMessage>,
    rx_req: flume::Receiver<BackendRequest>,
) {
    let pg_config = match database_config() {
        Ok(config) => config,
        Err(message) => {
            log::error!("Research database configuration: {}", message);
            let _ = tx.send(BackendMessage::PostgresConnected(false));
            return;
        }
    };
    // ── Postgres: audit log stream ──────────────────────────────────────
    let tx_pg = tx.clone();
    let audit_config = pg_config.clone();
    tokio::spawn(async move {
        loop {
            match audit_config.connect(NoTls).await {
                Ok((client, connection)) => {
                    let _ = tx_pg.send(BackendMessage::PostgresConnected(true));

                    tokio::spawn(async move {
                        if let Err(e) = connection.await {
                            log::error!("connection error: {}", e);
                        }
                    });

                    let mut last_id = 0i64;
                    loop {
                        // Fetch new audit events
                        match client.query(
                            "SELECT id, session_id::text, timestamp, operation, path, inode \
                             FROM audit_log WHERE id > $1 ORDER BY id ASC LIMIT 1000",
                            &[&last_id],
                        ).await {
                            Ok(rows) => {
                                let mut events = Vec::new();
                                for row in rows {
                                    let id: i64 = row.get(0);
                                    if id > last_id { last_id = id; }
                                    events.push(AuditEvent {
                                        id,
                                        session_id: row.get(1),
                                        timestamp: row.get(2),
                                        operation: row.get(3),
                                        path: row.get(4),
                                        inode: row.get(5),
                                    });
                                }
                                if !events.is_empty() {
                                    let _ = tx_pg.send(BackendMessage::AuditLogs(events));
                                }
                            }
                            Err(e) => {
                                log::error!("Postgres query error: {}", e);
                                if e.is_closed() { break; }
                            }
                        }
                        tokio::time::sleep(Duration::from_secs(2)).await;
                    }
                    let _ = tx_pg.send(BackendMessage::PostgresConnected(false));
                }
                Err(e) => {
                    log::error!("Postgres connection failed: {:?}", e);
                    let _ = tx_pg.send(BackendMessage::PostgresConnected(false));
                    tokio::time::sleep(Duration::from_secs(5)).await;
                }
            }
        }
    });

    // ── Postgres: session list + active count (5s poll) ─────────────────
    let tx_sessions = tx.clone();
    let sessions_config = pg_config.clone();
    tokio::spawn(async move {
        loop {
            match sessions_config.connect(NoTls).await {
                Ok((client, connection)) => {
                    tokio::spawn(async move {
                        if let Err(e) = connection.await {
                            log::error!("session connection error: {}", e);
                        }
                    });

                    loop {
                        // Session list
                        match client.query(
                            "SELECT session_id::text, start_time, end_time, duration_seconds, \
                             detection_status, detection_confidence, exit_reason, \
                             first_suspicious_command \
                             FROM session_evidence ORDER BY start_time DESC LIMIT 100",
                            &[],
                        ).await {
                            Ok(rows) => {
                                let sessions: Vec<SessionSummary> = rows.iter().map(|row| {
                                    SessionSummary {
                                        session_id: row.get::<_, Option<String>>(0).unwrap_or_default(),
                                        start_time: row.get(1),
                                        end_time: row.get(2),
                                        duration_seconds: row.get(3),
                                        detection_status: row.get(4),
                                        detection_confidence: row.get(5),
                                        exit_reason: row.get(6),
                                        first_suspicious_command: row.get(7),
                                    }
                                }).collect();
                                let _ = tx_sessions.send(BackendMessage::SessionList(sessions));
                            }
                            Err(e) => {
                                log::error!("Session list query error: {}", e);
                                if e.is_closed() { break; }
                            }
                        }

                        // Active session count
                        match client.query_one(
                            "SELECT COUNT(DISTINCT session_id) FROM audit_log \
                             WHERE timestamp > NOW() - INTERVAL '10 minutes'",
                            &[],
                        ).await {
                            Ok(row) => {
                                let count: i64 = row.get(0);
                                let _ = tx_sessions.send(BackendMessage::ActiveSessionCount(count as i32));
                            }
                            Err(e) => {
                                log::error!("Active session count error: {}", e);
                                if e.is_closed() { break; }
                            }
                        }

                        tokio::time::sleep(Duration::from_secs(5)).await;
                    }
                }
                Err(e) => {
                    log::error!("Session postgres connection failed: {:?}", e);
                    tokio::time::sleep(Duration::from_secs(5)).await;
                }
            }
        }
    });

    // ── Postgres: on-demand session detail ──────────────────────────────
    let tx_detail = tx.clone();
    tokio::spawn(async move {
        loop {
            // Wait for a request from the UI
            let req = match rx_req.recv_async().await {
                Ok(r) => r,
                Err(_) => break,
            };

            match req {
                BackendRequest::ExportSession { session_id, destination } => {
                    // Operator-side helper only; never executed by a honeypot worker.
                    // Argument arrays avoid shell interpretation of paths or identifiers.
                    let python = std::env::var("APATE_PYTHON").unwrap_or_else(|_| "python3".into());
                    let mut child = tokio::process::Command::new(python);
                    child.args(["-m", "chronos.watcher.export_report", "--session-id",
                                &session_id, "--output", &destination]);
                    child.kill_on_drop(true);
                    child.stdout(std::process::Stdio::null());
                    child.stderr(std::process::Stdio::null());
                    let result = match tokio::time::timeout(Duration::from_secs(90), child.status()).await {
                        Ok(Ok(status)) if status.success() => Ok(destination),
                        Ok(Ok(_)) => Err("Export failed. Check database settings, Python module availability, and choose a new output directory. Partial bundles lack complete.json.".into()),
                        Ok(Err(_)) => Err("Could not launch APATE_PYTHON. Configure a Python environment with Apate installed.".into()),
                        Err(_) => Err("Export exceeded 90 seconds; incomplete output must not be used as evidence.".into()),
                    };
                    let _ = tx_detail.send(BackendMessage::ExportResult(result));
                }
                BackendRequest::FetchSessionDetail(session_id) => {
                    match pg_config.connect(NoTls).await {
                        Ok((client, connection)) => {
                            tokio::spawn(async move {
                                if let Err(e) = connection.await {
                                    log::error!("detail connection error: {}", e);
                                }
                            });

                            match client.query_opt(
                                "SELECT session_id::text, start_time, end_time, duration_seconds, \
                                 detection_status, detection_confidence, exit_reason, \
                                 first_suspicious_command, commands, visited_files, \
                                 traversal_graph, skill_assessment \
                                 FROM session_evidence WHERE session_id::text = $1",
                                &[&session_id],
                            ).await {
                                Ok(Some(row)) => {
                                    let commands_json: Option<serde_json::Value> = row.get(8);
                                    let commands: Vec<CommandEntry> = commands_json
                                        .and_then(|v| serde_json::from_value(v).ok())
                                        .unwrap_or_default();

                                    let visited_json: Option<serde_json::Value> = row.get(9);
                                    let visited_files: Vec<String> = visited_json
                                        .and_then(|v| serde_json::from_value(v).ok())
                                        .unwrap_or_default();

                                    let traversal_graph: serde_json::Value = row.get::<_, Option<serde_json::Value>>(10)
                                        .unwrap_or(serde_json::Value::Object(serde_json::Map::new()));

                                    let detail = SessionDetail {
                                        session_id: row.get::<_, Option<String>>(0).unwrap_or_default(),
                                        start_time: row.get(1),
                                        end_time: row.get(2),
                                        duration_seconds: row.get(3),
                                        detection_status: row.get(4),
                                        detection_confidence: row.get(5),
                                        exit_reason: row.get(6),
                                        first_suspicious_command: row.get(7),
                                        commands,
                                        visited_files,
                                        traversal_graph,
                                        skill_assessment: row.get(11),
                                    };
                                    let _ = tx_detail.send(BackendMessage::SessionDetailResult(Box::new(Some(detail))));
                                }
                                Ok(None) => {
                                    let _ = tx_detail.send(BackendMessage::SessionDetailResult(Box::new(None)));
                                }
                                Err(e) => {
                                    log::error!("Session detail query error: {}", e);
                                    let _ = tx_detail.send(BackendMessage::SessionDetailResult(Box::new(None)));
                                }
                            }
                        }
                        Err(e) => {
                            log::error!("Detail postgres connection failed: {:?}", e);
                            let _ = tx_detail.send(BackendMessage::SessionDetailResult(Box::new(None)));
                        }
                    }
                }
            }
        }
    });

    // ── Redis: inode count ──────────────────────────────────────────────
    let tx_rd = tx.clone();
    tokio::spawn(async move {
        loop {
            match redis::Client::open(std::env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://127.0.0.1:6379/".into())) {
                Ok(client) => {
                    if let Ok(mut con) = client.get_multiplexed_tokio_connection().await {
                        let _ = tx_rd.send(BackendMessage::RedisConnected(true));
                        let mut provenance_tick = 0u32;
                        loop {
                            let count: redis::RedisResult<Option<i32>> = con.get("fs:next_inode").await;
                            match count {
                                Ok(c) => {
                                    let _ = tx_rd.send(BackendMessage::TotalFiles(c.unwrap_or(0)));
                                }
                                Err(e) => {
                                    log::error!("Redis query error: {}", e);
                                    break;
                                }
                            }

                            provenance_tick = provenance_tick.wrapping_add(1);
                            if provenance_tick % 5 == 0 {
                                match collect_provenance_snapshot(&mut con).await {
                                    Ok(snapshot) => {
                                        let _ = tx_rd.send(BackendMessage::ProvenanceSnapshot(snapshot));
                                    }
                                    Err(e) => {
                                        log::error!("Provenance snapshot error: {}", e);
                                    }
                                }
                            }

                            tokio::time::sleep(Duration::from_secs(2)).await;
                        }
                    }
                }
                Err(e) => log::error!("Redis init error: {}", e),
            }
            let _ = tx_rd.send(BackendMessage::RedisConnected(false));
            tokio::time::sleep(Duration::from_secs(5)).await;
        }
    });
}

async fn collect_provenance_snapshot(
    con: &mut redis::aio::MultiplexedConnection,
) -> redis::RedisResult<ProvenanceSummary> {
    let keys: Vec<String> = con.keys("session:*:fs:blob_meta:*").await?;

    let mut by_file_class: BTreeMap<String, i32> = BTreeMap::new();
    let mut entries: Vec<(f64, ProvenanceEntry)> = Vec::new();
    let mut total_blobs = 0i32;
    let mut validated_blobs = 0i32;
    let mut llm_blobs = 0i32;
    let mut fallback_blobs = 0i32;
    let mut template_blobs = 0i32;

    for key in keys {
        let meta: HashMap<String, String> = con.hgetall(&key).await.unwrap_or_default();
        if meta.is_empty() {
            continue;
        }

        total_blobs += 1;
        let validated = meta.get("validated").map(|value| value == "true").unwrap_or(false);
        if validated {
            validated_blobs += 1;
        }

        match meta.get("generation_source").map(|s| s.as_str()).unwrap_or("llm") {
            "llm" => llm_blobs += 1,
            "fallback" => fallback_blobs += 1,
            "template" => template_blobs += 1,
            _ => {}
        }

        let file_class = meta.get("file_class").cloned().unwrap_or_else(|| "unknown".to_string());
        *by_file_class.entry(file_class.clone()).or_insert(0) += 1;

        let generated_at = meta.get("generated_at").cloned().unwrap_or_default();
        let generated_at_ts = generated_at.parse::<f64>().unwrap_or(0.0);
        let blob_hash = key.strip_prefix("fs:blob_meta:").unwrap_or(&key).to_string();

        entries.push((
            generated_at_ts,
            ProvenanceEntry {
                blob_hash,
                model: meta.get("model").cloned().unwrap_or_default(),
                file_class,
                generation_source: meta.get("generation_source").cloned().unwrap_or_default(),
                prompt_version: meta.get("prompt_version").cloned().unwrap_or_default(),
                generated_at,
                validated,
            },
        ));
    }

    entries.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(Ordering::Equal));

    Ok(ProvenanceSummary {
        total_blobs,
        validated_blobs,
        llm_blobs,
        fallback_blobs,
        template_blobs,
        by_file_class: by_file_class.into_iter().collect(),
        recent_entries: entries.into_iter().take(12).map(|(_, entry)| entry).collect(),
    })
}
