use chrono::NaiveDateTime;
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{BTreeMap, HashMap};
use std::time::Duration;
use tokio_postgres::NoTls;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ProvenanceEntry {
    pub blob_hash: String,
    pub model: String,
    pub model_digest: String,
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
    pub claimed_username: Option<String>,
    pub effective_username: Option<String>,
    pub identity_mismatch: Option<bool>,
    pub identity_policy: Option<String>,
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
    use super::{blob_hash_from_key, CommandEntry, ExportMode};

    #[test]
    fn export_modes_are_explicit_cli_values() {
        assert_eq!(ExportMode::Raw.as_arg(), "raw");
        assert_eq!(ExportMode::Redacted.as_arg(), "redacted");
    }

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

    #[test]
    fn scoped_provenance_key_exposes_blob_hash_only() {
        assert_eq!(
            blob_hash_from_key("session:abc:fs:blob_meta:deadbeef"),
            "deadbeef"
        );
        assert_eq!(blob_hash_from_key("fs:blob_meta:cafebabe"), "cafebabe");
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
    pub pattern_assessment: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Default)]
pub struct SessionStats {
    pub finalized_count: i64,
    pub detected_count: i64,
    pub average_duration_seconds: Option<f64>,
}

#[derive(Debug, Clone, Copy)]
pub enum ExportMode {
    Raw,
    Redacted,
}

impl ExportMode {
    fn as_arg(self) -> &'static str {
        match self {
            Self::Raw => "raw",
            Self::Redacted => "redacted",
        }
    }
}

// ── Messages ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub enum BackendMessage {
    RunSnapshot {
        runs: Vec<HashMap<String, String>>,
        armed: Option<String>,
    },
    RunActionResult(Result<String, String>),
    RunSnapshotError,
    OperationalSnapshot {
        health: HashMap<String, String>,
        jobs: Vec<HashMap<String, String>>,
    },
    OperationalUnavailable,
    ProvenanceUnavailable,
    StackStatus(String),
    LiveContexts(Result<Vec<HashMap<String, String>>, String>),
    ExportResult(Result<String, String>),
    RedisConnected(bool),
    PostgresConnected(bool),
    AuditLogs(Vec<AuditEvent>),
    TotalFiles(i32),
    OpenSessionCount(i32),
    SessionPage {
        sessions: Vec<SessionSummary>,
        total: i64,
        offset: i64,
        limit: i64,
        snapshot_at: NaiveDateTime,
    },
    SessionPageError(String),
    SessionStats(SessionStats),
    SessionDetailResult(Box<Option<SessionDetail>>),
    ProvenanceSnapshot(ProvenanceSummary),
}

#[derive(Debug, Clone)]
pub enum BackendRequest {
    ArmRun(Option<String>),
    ExportSession {
        session_id: String,
        destination: String,
        mode: ExportMode,
    },
    FetchSessionDetail(String), // session_id
    FetchSessionPage {
        offset: i64,
        limit: i64,
        snapshot_at: Option<NaiveDateTime>,
    },
}

// ── Backend Loop ────────────────────────────────────────────────────────────

fn database_config() -> Result<tokio_postgres::Config, String> {
    let password = std::env::var("POSTGRES_PASSWORD")
        .map_err(|_| "Set POSTGRES_PASSWORD for the research database".to_string())?;
    let port = std::env::var("POSTGRES_PORT")
        .unwrap_or_else(|_| "5433".into())
        .parse::<u16>()
        .map_err(|_| "POSTGRES_PORT must be a valid port".to_string())?;
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
                    tokio::spawn(async move {
                        if let Err(e) = connection.await {
                            log::error!("connection error: {}", e);
                        }
                    });

                    let mut last_id = 0i64;
                    loop {
                        // Fetch new audit events
                        match client
                            .query(
                                "SELECT id, session_id::text, timestamp, operation, path, inode \
                             FROM audit_log WHERE id > $1 ORDER BY id ASC LIMIT 1000",
                                &[&last_id],
                            )
                            .await
                        {
                            Ok(rows) => {
                                let _ = tx_pg.send(BackendMessage::PostgresConnected(true));
                                let mut events = Vec::new();
                                for row in rows {
                                    let id: i64 = row.get(0);
                                    if id > last_id {
                                        last_id = id;
                                    }
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
                                let _ = tx_pg.send(BackendMessage::PostgresConnected(false));
                                break;
                            }
                        }
                        tokio::time::sleep(Duration::from_secs(2)).await;
                    }
                    let _ = tx_pg.send(BackendMessage::PostgresConnected(false));
                    tokio::time::sleep(Duration::from_secs(5)).await;
                }
                Err(e) => {
                    log::error!("Postgres connection failed: {:?}", e);
                    let _ = tx_pg.send(BackendMessage::PostgresConnected(false));
                    tokio::time::sleep(Duration::from_secs(5)).await;
                }
            }
        }
    });

    // ── Postgres: lifecycle and all-finalized-session statistics ────────
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
                        // These aggregates cover all finalized rows, not a UI page.
                        match client
                            .query_one(
                                "SELECT COUNT(*), \
                                 COUNT(*) FILTER (WHERE detection_status = 'detected'), \
                                 AVG(duration_seconds)::float8 \
                                 FROM session_evidence WHERE end_time IS NOT NULL",
                                &[],
                            )
                            .await
                        {
                            Ok(row) => {
                                let _ =
                                    tx_sessions.send(BackendMessage::SessionStats(SessionStats {
                                        finalized_count: row.get(0),
                                        detected_count: row.get(1),
                                        average_duration_seconds: row.get(2),
                                    }));
                            }
                            Err(e) => {
                                log::error!("Session statistics query error: {}", e);
                                if e.is_closed() {
                                    break;
                                }
                            }
                        }

                        // Recorded lifecycle state: latest open/close event wins.
                        match client
                            .query_one(
                                "WITH latest AS ( \
                                   SELECT DISTINCT ON (session_id) session_id, operation \
                                   FROM audit_log \
                                   WHERE session_id IS NOT NULL \
                                     AND operation IN ('ssh_session_opened', 'ssh_disconnect') \
                                   ORDER BY session_id, id DESC \
                                 ) SELECT COUNT(*) FROM latest \
                                   WHERE operation = 'ssh_session_opened'",
                                &[],
                            )
                            .await
                        {
                            Ok(row) => {
                                let count: i64 = row.get(0);
                                let _ = tx_sessions
                                    .send(BackendMessage::OpenSessionCount(count as i32));
                            }
                            Err(e) => {
                                log::error!("Active session count error: {}", e);
                                if e.is_closed() {
                                    break;
                                }
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
                BackendRequest::ArmRun(run_id) => {
                    let result = tokio::time::timeout(Duration::from_secs(5), arm_run(run_id))
                        .await
                        .unwrap_or_else(|_| Err("Run selection timed out".into()));
                    let _ = tx_detail.send(BackendMessage::RunActionResult(result));
                }
                BackendRequest::ExportSession {
                    session_id,
                    destination,
                    mode,
                } => {
                    if std::env::var("CHRONOS_MANAGE_STACK").as_deref() != Ok("0") {
                        let result =
                            crate::managed_export::export(&session_id, &destination, mode.as_arg())
                                .await;
                        let _ = tx_detail.send(BackendMessage::ExportResult(result));
                        continue;
                    }
                    // Operator-side helper only; never executed by a honeypot worker.
                    // Argument arrays avoid shell interpretation of paths or identifiers.
                    let python = std::env::var("APATE_PYTHON").unwrap_or_else(|_| "python3".into());
                    let mut child = tokio::process::Command::new(python);
                    child.args([
                        "-m",
                        "chronos.watcher.export_report",
                        "--session-id",
                        &session_id,
                        "--output",
                        &destination,
                        "--mode",
                        mode.as_arg(),
                    ]);
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
                BackendRequest::FetchSessionPage {
                    offset,
                    limit,
                    snapshot_at,
                } => {
                    let offset = offset.max(0);
                    let limit = limit.clamp(1, 200);
                    match pg_config.connect(NoTls).await {
                        Ok((client, connection)) => {
                            tokio::spawn(async move {
                                if let Err(e) = connection.await {
                                    log::error!("session page connection error: {}", e);
                                }
                            });
                            let snapshot = match snapshot_at {
                                Some(value) => Ok(value),
                                None => client
                                    .query_one("SELECT CURRENT_TIMESTAMP::timestamp", &[])
                                    .await
                                    .map(|row| row.get::<_, NaiveDateTime>(0)),
                            };
                            let total = match snapshot {
                                Ok(snapshot_at) => client.query_one(
                                    "SELECT COUNT(*) FROM session_evidence WHERE end_time IS NOT NULL AND finalized_at <= $1",
                                    &[&snapshot_at],
                                ).await.map(|row| (row.get::<_, i64>(0), snapshot_at)),
                                Err(error) => Err(error),
                            };
                            let rows = client.query(
                                "SELECT session_id::text, start_time, end_time, duration_seconds, \
                                 detection_status, detection_confidence, exit_reason, \
                                 first_suspicious_command \
                                 FROM session_evidence WHERE end_time IS NOT NULL AND finalized_at <= $3 \
                                 ORDER BY start_time DESC NULLS LAST, session_id DESC \
                                 LIMIT $1 OFFSET $2",
                                &[&limit, &offset, &total.as_ref().map(|(_, value)| *value).unwrap_or_else(|_| chrono::Utc::now().naive_utc())],
                            ).await;
                            match (total, rows) {
                                (Ok((total, snapshot_at)), Ok(rows)) => {
                                    let sessions = rows
                                        .iter()
                                        .map(|row| SessionSummary {
                                            session_id: row
                                                .get::<_, Option<String>>(0)
                                                .unwrap_or_default(),
                                            start_time: row.get(1),
                                            end_time: row.get(2),
                                            duration_seconds: row.get(3),
                                            detection_status: row.get(4),
                                            detection_confidence: row.get(5),
                                            exit_reason: row.get(6),
                                            first_suspicious_command: row.get(7),
                                        })
                                        .collect();
                                    let _ = tx_detail.send(BackendMessage::SessionPage {
                                        sessions,
                                        total,
                                        offset,
                                        limit,
                                        snapshot_at,
                                    });
                                }
                                (Err(e), _) | (_, Err(e)) => {
                                    log::error!("Session page query error: {}", e);
                                    let _ = tx_detail.send(BackendMessage::SessionPageError(
                                        "Unable to load finalized session history.".into(),
                                    ));
                                }
                            }
                        }
                        Err(e) => {
                            log::error!("Session page connection failed: {:?}", e);
                            let _ = tx_detail.send(BackendMessage::SessionPageError(
                                "Research database is unavailable.".into(),
                            ));
                        }
                    }
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
                                        pattern_assessment: row.get(11),
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
                            let _ =
                                tx_detail.send(BackendMessage::SessionDetailResult(Box::new(None)));
                        }
                    }
                }
            }
        }
    });

    // ── Redis: inode count ──────────────────────────────────────────────
    let tx_rd = tx.clone();
    tokio::spawn(async move {
        let redis_url = match std::env::var("REDIS_URL") {
            Ok(url) => url,
            Err(_) => {
                let _ = tx_rd.send(BackendMessage::RedisConnected(false));
                return; // Never inspect an unrelated host Redis by default.
            }
        };
        loop {
            match redis::Client::open(redis_url.clone()) {
                Ok(client) => {
                    if let Ok(mut con) = client.get_multiplexed_tokio_connection().await {
                        let _ = tx_rd.send(BackendMessage::RedisConnected(true));
                        let mut provenance_tick = 0u32;
                        loop {
                            let count: redis::RedisResult<Option<i32>> =
                                con.get("fs:next_inode").await;
                            match count {
                                Ok(c) => {
                                    let _ = tx_rd.send(BackendMessage::TotalFiles(c.unwrap_or(0)));
                                }
                                Err(e) => {
                                    log::error!("Redis query error: {}", e);
                                    break;
                                }
                            }

                            let contexts = tokio::time::timeout(
                                Duration::from_secs(3),
                                collect_live_contexts(&mut con),
                            )
                            .await;
                            let contexts = match contexts {
                                Ok(Ok(rows)) => Ok(rows),
                                Ok(Err(_)) => Err("Session context query failed".into()),
                                Err(_) => Err("Session context query timed out".into()),
                            };
                            if tx_rd
                                .send_async(BackendMessage::LiveContexts(contexts))
                                .await
                                .is_err()
                            {
                                return;
                            }
                            provenance_tick = provenance_tick.wrapping_add(1);
                            let operational = tokio::time::timeout(Duration::from_secs(3), async {
                                let health: HashMap<String, String> =
                                    con.hgetall("chronos:operational_health").await?;
                                let mut jobs =
                                    collect_hashes(&mut con, "session:*:generation:*", 2000)
                                        .await?;
                                jobs.sort_by(|a, b| b.get("updated_at").cmp(&a.get("updated_at")));
                                jobs.truncate(50);
                                Ok::<_, redis::RedisError>((health, jobs))
                            })
                            .await;
                            match operational {
                                Ok(Ok((health, jobs))) => {
                                    let _ = tx_rd
                                        .send_async(BackendMessage::OperationalSnapshot {
                                            health,
                                            jobs,
                                        })
                                        .await;
                                }
                                _ => {
                                    let _ = tx_rd
                                        .send_async(BackendMessage::OperationalUnavailable)
                                        .await;
                                }
                            }
                            let snapshot = tokio::time::timeout(Duration::from_secs(3), async {
                                let ids: Vec<String> =
                                    con.zrevrange("chronos:runs:index", 0, 199).await?;
                                let mut runs = Vec::new();
                                for id in ids {
                                    let fields =
                                        ["run_id", "status", "cwd", "device_id", "updated_at"];
                                    let values: Vec<Option<String>> = redis::cmd("HMGET")
                                        .arg(format!("chronos:run:{id}"))
                                        .arg(&fields)
                                        .query_async(&mut con)
                                        .await?;
                                    let row: HashMap<String, String> = fields
                                        .into_iter()
                                        .zip(values)
                                        .filter_map(|(key, value)| {
                                            value.map(|value| (key.into(), value))
                                        })
                                        .collect();
                                    runs.push(row);
                                }
                                let armed: Option<String> = con.get("chronos:runs:next").await?;
                                Ok::<_, redis::RedisError>((runs, armed))
                            })
                            .await;
                            if let Ok(Ok((runs, armed))) = snapshot {
                                let _ = tx_rd
                                    .send_async(BackendMessage::RunSnapshot { runs, armed })
                                    .await;
                            } else {
                                let _ = tx_rd.send_async(BackendMessage::RunSnapshotError).await;
                            }
                            if provenance_tick % 5 == 0 {
                                match tokio::time::timeout(
                                    Duration::from_secs(3),
                                    collect_provenance_snapshot(&mut con),
                                )
                                .await
                                {
                                    Ok(Ok(snapshot)) => {
                                        let _ = tx_rd
                                            .send(BackendMessage::ProvenanceSnapshot(snapshot));
                                    }
                                    _ => {
                                        let _ = tx_rd
                                            .send_async(BackendMessage::ProvenanceUnavailable)
                                            .await;
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

async fn arm_run(run_id: Option<String>) -> Result<String, String> {
    let url = std::env::var("REDIS_URL").map_err(|_| "Redis is not configured")?;
    let mut connection = redis::Client::open(url)
        .map_err(|_| "Invalid Redis configuration")?
        .get_multiplexed_tokio_connection()
        .await
        .map_err(|_| "Redis unavailable")?;
    match run_id {
        None => {
            let _: i32 = connection
                .del("chronos:runs:next")
                .await
                .map_err(|_| "Cannot select fresh run")?;
            Ok("Next connection starts fresh; retained runs are preserved".into())
        }
        Some(id) => {
            if id.len() != 36
                || !id.chars().enumerate().all(|(i, c)| {
                    if [8, 13, 18, 23].contains(&i) {
                        c == '-'
                    } else {
                        c.is_ascii_digit() || ('a'..='f').contains(&c)
                    }
                })
            {
                return Err("Select a valid run UUID".into());
            }
            let script = redis::Script::new("if redis.call('HGET', KEYS[1], 'status') ~= 'paused' then return redis.error_reply('Run must be paused') end; redis.call('SET', KEYS[2], ARGV[1], 'EX', 60); return 1");
            let _: i32 = script
                .key(format!("chronos:run:{id}"))
                .key("chronos:runs:next")
                .arg(&id)
                .invoke_async(&mut connection)
                .await
                .map_err(|_| "Run must be paused and Redis available")?;
            Ok(format!(
                "Run {id} selected for the next shell; selection expires in 60 seconds"
            ))
        }
    }
}

async fn collect_live_contexts(
    con: &mut redis::aio::MultiplexedConnection,
) -> redis::RedisResult<Vec<HashMap<String, String>>> {
    collect_hashes(con, "session:*:context", 1000).await
}

async fn scan_keys(
    con: &mut redis::aio::MultiplexedConnection,
    pattern: &str,
    capacity: usize,
) -> redis::RedisResult<std::collections::BTreeSet<String>> {
    let mut cursor = 0u64;
    let mut keys = std::collections::BTreeSet::new();
    loop {
        let (next, batch): (u64, Vec<String>) = redis::cmd("SCAN")
            .arg(cursor)
            .arg("MATCH")
            .arg(pattern)
            .arg("COUNT")
            .arg(100)
            .query_async(con)
            .await?;
        keys.extend(batch);
        if keys.len() > capacity {
            return Err((redis::ErrorKind::ResponseError, "Context capacity exceeded").into());
        }
        cursor = next;
        if cursor == 0 {
            break;
        }
    }
    Ok(keys)
}

async fn collect_hashes(
    con: &mut redis::aio::MultiplexedConnection,
    pattern: &str,
    capacity: usize,
) -> redis::RedisResult<Vec<HashMap<String, String>>> {
    let keys = scan_keys(con, pattern, capacity).await?;
    let mut rows = Vec::new();
    for key in keys {
        let row: HashMap<String, String> = con.hgetall(&key).await?;
        if !row.is_empty() {
            rows.push(row);
        }
    }
    Ok(rows)
}

async fn collect_provenance_snapshot(
    con: &mut redis::aio::MultiplexedConnection,
) -> redis::RedisResult<ProvenanceSummary> {
    let mut keys = scan_keys(con, "session:*:fs:blob_meta:*", 10000).await?;
    keys.extend(scan_keys(con, "run:*:fs:blob_meta:*", 10000).await?);

    let mut by_file_class: BTreeMap<String, i32> = BTreeMap::new();
    let mut entries: Vec<(f64, ProvenanceEntry)> = Vec::new();
    let mut total_blobs = 0i32;
    let mut validated_blobs = 0i32;
    let mut llm_blobs = 0i32;
    let mut fallback_blobs = 0i32;
    let mut template_blobs = 0i32;

    for key in keys {
        let meta: HashMap<String, String> = con.hgetall(&key).await?;
        if meta.is_empty() {
            continue;
        }

        total_blobs += 1;
        let validated = meta
            .get("validated")
            .map(|value| value == "true")
            .unwrap_or(false);
        if validated {
            validated_blobs += 1;
        }

        match meta
            .get("generation_source")
            .map(|s| s.as_str())
            .unwrap_or("llm")
        {
            "llm" => llm_blobs += 1,
            "fallback" => fallback_blobs += 1,
            "template" => template_blobs += 1,
            _ => {}
        }

        let file_class = meta
            .get("file_class")
            .cloned()
            .unwrap_or_else(|| "unknown".to_string());
        *by_file_class.entry(file_class.clone()).or_insert(0) += 1;

        let generated_at = meta.get("generated_at").cloned().unwrap_or_default();
        let generated_at_ts = generated_at.parse::<f64>().unwrap_or(0.0);
        let blob_hash = blob_hash_from_key(&key);

        entries.push((
            generated_at_ts,
            ProvenanceEntry {
                blob_hash,
                model: meta.get("model").cloned().unwrap_or_default(),
                model_digest: meta.get("model_digest").cloned().unwrap_or_default(),
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
        recent_entries: entries
            .into_iter()
            .take(12)
            .map(|(_, entry)| entry)
            .collect(),
    })
}

fn blob_hash_from_key(key: &str) -> String {
    key.split_once(":fs:blob_meta:")
        .map(|(_, hash)| hash)
        .or_else(|| key.strip_prefix("fs:blob_meta:"))
        .unwrap_or(key)
        .to_string()
}
