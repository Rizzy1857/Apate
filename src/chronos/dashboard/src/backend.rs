use redis::AsyncCommands;
use tokio_postgres::NoTls;
use std::time::Duration;
use chrono::NaiveDateTime;

#[derive(Debug, Clone)]
pub struct AuditEvent {
    pub id: i64,
    pub session_id: Option<String>,
    pub timestamp: NaiveDateTime,
    pub operation: Option<String>,
    pub path: Option<String>,
    pub inode: Option<i64>,
}

#[derive(Debug, Clone)]
pub enum BackendMessage {
    RedisConnected(bool),
    PostgresConnected(bool),
    AuditLogs(Vec<AuditEvent>),
    TotalFiles(i32),
}

pub async fn start_backend(tx: flume::Sender<BackendMessage>) {
    // Start postgres loop
    let tx_pg = tx.clone();
    tokio::spawn(async move {
        loop {
            match tokio_postgres::connect("host=127.0.0.1 port=5433 user=chronos password=chronos_dev_password dbname=chronos", NoTls).await {
                Ok((client, connection)) => {
                    let _ = tx_pg.send(BackendMessage::PostgresConnected(true));
                    
                    tokio::spawn(async move {
                        if let Err(e) = connection.await {
                            log::error!("connection error: {}", e);
                        }
                    });

                    let mut last_id = 0i64;
                    loop {
                        match client.query("SELECT id, session_id::text, timestamp, operation, path, inode FROM audit_log WHERE id > $1 ORDER BY id DESC LIMIT 50", &[&last_id]).await {
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
                                // If connection is broken, break loop to reconnect
                                if e.is_closed() {
                                    break;
                                }
                            }
                        }
                        tokio::time::sleep(Duration::from_secs(2)).await;
                    }
                    let _ = tx_pg.send(BackendMessage::PostgresConnected(false));
                },
                Err(e) => {
                    log::error!("Postgres connection failed: {:?}", e);
                    let _ = tx_pg.send(BackendMessage::PostgresConnected(false));
                    tokio::time::sleep(Duration::from_secs(5)).await;
                }
            }
        }
    });

    // Start redis loop
    let tx_rd = tx.clone();
    tokio::spawn(async move {
        loop {
            match redis::Client::open("redis://127.0.0.1:6379/") {
                Ok(client) => {
                    if let Ok(mut con) = client.get_multiplexed_tokio_connection().await {
                        let _ = tx_rd.send(BackendMessage::RedisConnected(true));
                        loop {
                            // Fetch total inodes
                            let count: redis::RedisResult<Option<i32>> = con.get("fs:next_inode").await;
                            match count {
                                Ok(c) => {
                                    let _ = tx_rd.send(BackendMessage::TotalFiles(c.unwrap_or(0)));
                                }
                                Err(e) => {
                                    log::error!("Redis query error: {}", e);
                                    break; // Connection error
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
