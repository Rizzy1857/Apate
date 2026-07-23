use redis::AsyncCommands;
use tokio_postgres::NoTls;
use std::time::Duration;
use chrono::NaiveDateTime;
use serde::{Deserialize, Serialize};

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
    pub timestamp: Option<String>,
    pub command: Option<String>,
    pub techniques: Option<Vec<String>>,
    pub risk_score: Option<i64>,
    pub signatures: Option<Vec<String>>,
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
    RedisConnected(bool),
    PostgresConnected(bool),
    AuditLogs(Vec<AuditEvent>),
    TotalFiles(i32),
    ActiveSessionCount(i32),
    SessionList(Vec<SessionSummary>),
    SessionDetailResult(Box<Option<SessionDetail>>),
}

#[derive(Debug, Clone)]
pub enum BackendRequest {
    FetchSessionDetail(String),  // session_id
}

// ── Backend Loop ────────────────────────────────────────────────────────────

pub async fn start_backend(
    tx: flume::Sender<BackendMessage>,
    rx_req: flume::Receiver<BackendRequest>,
) {
    // ── Postgres: audit log stream ──────────────────────────────────────
    let tx_pg = tx.clone();
    tokio::spawn(async move {
        loop {
            match tokio_postgres::connect(
                "host=127.0.0.1 port=5433 user=chronos password=chronos_dev_password dbname=chronos",
                NoTls,
            ).await {
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
                             FROM audit_log WHERE id > $1 ORDER BY id DESC LIMIT 50",
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
    tokio::spawn(async move {
        loop {
            match tokio_postgres::connect(
                "host=127.0.0.1 port=5433 user=chronos password=chronos_dev_password dbname=chronos",
                NoTls,
            ).await {
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
                BackendRequest::FetchSessionDetail(session_id) => {
                    match tokio_postgres::connect(
                        "host=127.0.0.1 port=5433 user=chronos password=chronos_dev_password dbname=chronos",
                        NoTls,
                    ).await {
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
            match redis::Client::open("redis://127.0.0.1:6379/") {
                Ok(client) => {
                    if let Ok(mut con) = client.get_multiplexed_tokio_connection().await {
                        let _ = tx_rd.send(BackendMessage::RedisConnected(true));
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
