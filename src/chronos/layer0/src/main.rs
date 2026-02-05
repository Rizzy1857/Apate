// TCP Echo Server for Protocol-Level Realism
// ------------------------------------------
// Implements a low-level TCP server that can be harder to fingerprint.
// Supports adaptive protocol responses and realistic network behavior.

use std::io;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::Mutex;
use tokio::time::sleep;
use log::{info, warn, error, debug};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};
use socket2::{Socket, Domain, Type, Protocol};
use rand::Rng;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Connection {
    id: String,
    peer_addr: SocketAddr,
    connected_at: DateTime<Utc>,
    bytes_received: u64,
    bytes_sent: u64,
    last_activity: DateTime<Utc>,
}

#[derive(Debug, Clone)]
struct ServerStats {
    connections: Arc<Mutex<Vec<Connection>>>,
    total_connections: Arc<Mutex<u64>>,
    start_time: Instant,
}

impl ServerStats {
    fn new() -> Self {
        Self {
            connections: Arc::new(Mutex::new(Vec::new())),
            total_connections: Arc::new(Mutex::new(0)),
            start_time: Instant::now(),
        }
    }

    async fn add_connection(&self, peer_addr: SocketAddr) -> String {
        let connection_id = Uuid::new_v4().to_string();
        let connection = Connection {
            id: connection_id.clone(),
            peer_addr,
            connected_at: Utc::now(),
            bytes_received: 0,
            bytes_sent: 0,
            last_activity: Utc::now(),
        };

        {
            let mut connections = self.connections.lock().await;
            connections.push(connection);
        }

        {
            let mut total = self.total_connections.lock().await;
            *total += 1;
        }

        info!("New connection from {}: {}", peer_addr, connection_id);
        connection_id
    }

    async fn remove_connection(&self, connection_id: &str) {
        let mut connections = self.connections.lock().await;
        connections.retain(|conn| conn.id != connection_id);
        info!("Connection {} disconnected", connection_id);
    }

    async fn update_activity(&self, connection_id: &str, bytes_received: u64, bytes_sent: u64) {
        let mut connections = self.connections.lock().await;
        if let Some(conn) = connections.iter_mut().find(|c| c.id == connection_id) {
            conn.bytes_received += bytes_received;
            conn.bytes_sent += bytes_sent;
            conn.last_activity = Utc::now();
        }
    }

    async fn get_stats(&self) -> serde_json::Value {
        let connections = self.connections.lock().await;
        let total = *self.total_connections.lock().await;
        
        serde_json::json!({
            "uptime_seconds": self.start_time.elapsed().as_secs(),
            "active_connections": connections.len(),
            "total_connections": total,
            "connections": *connections
        })
    }
}

async fn handle_client(mut socket: TcpStream, peer_addr: SocketAddr, stats: Arc<ServerStats>) -> io::Result<()> {
    let connection_id = stats.add_connection(peer_addr).await;
    
    // Split socket for reading and writing
    let (mut reader, mut writer) = socket.split();
    let mut buffer = vec![0; 1024];
    
    info!("Handling client connection: {}", connection_id);
    
    loop {
        // Read data from client
        match reader.read(&mut buffer).await {
            Ok(0) => {
                // Client disconnected
                debug!("Client {} disconnected gracefully", connection_id);
                break;
            }
            Ok(n) => {
                let received_data = &buffer[..n];
                let received_str = String::from_utf8_lossy(received_data);
                
                debug!("Received from {}: {}", connection_id, received_str.trim());
                
                // Process the received data and generate response
                let response = process_data(&received_str, &connection_id, peer_addr).await;
                
                // Add randomized jitter to defeat timing analysis (1-5ms)
                let jitter = rand::thread_rng().gen_range(1..=5);
                sleep(Duration::from_millis(jitter)).await;

                // Echo back with potential modifications
                match writer.write_all(response.as_bytes()).await {
                    Ok(_) => {
                        debug!("Sent to {}: {}", connection_id, response.trim());
                        stats.update_activity(&connection_id, n as u64, response.len() as u64).await;
                    }
                    Err(e) => {
                        error!("Failed to write to {}: {}", connection_id, e);
                        break;
                    }
                }
                
                // Add small delay to prevent overwhelming
                sleep(Duration::from_millis(10)).await;
            }
            Err(e) => {
                error!("Failed to read from {}: {}", connection_id, e);
                break;
            }
        }
    }
    
    stats.remove_connection(&connection_id).await;
    Ok(())
}

async fn process_data(data: &str, connection_id: &str, peer_addr: SocketAddr) -> String {
    let data_trimmed = data.trim();
    
    // Log potential attack patterns
    if data_trimmed.contains("GET /") || data_trimmed.contains("POST /") {
        warn!("HTTP request detected on TCP port from {}: {}", peer_addr, data_trimmed);
        return format!("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n");
    }
    
    if data_trimmed.starts_with("SSH-") {
        warn!("SSH handshake attempt from {}: {}", peer_addr, data_trimmed);
        return format!("SSH-2.0-OpenSSH_8.9p1\r\n");
    }
    
    // Check for common network scanning patterns
    if data_trimmed.is_empty() {
        debug!("Empty probe from {}", peer_addr);
        return String::new();
    }
    
    if data_trimmed.len() == 1 && data_trimmed.as_bytes()[0] < 32 {
        debug!("Binary probe from {}", peer_addr);
        return format!("ECHO_SRV_v1.0\n");
    }
    
    // Check for malicious payloads
    let suspicious_patterns = [
        "shellcode", "exploit", "payload", "metasploit", 
        "reverse_shell", "bind_shell", "nc -", "bash -i"
    ];
    
    for pattern in &suspicious_patterns {
        if data_trimmed.to_lowercase().contains(pattern) {
            warn!("Suspicious payload detected from {}: {}", peer_addr, pattern);
            // Return misleading response to waste attacker time
            return format!("Command not recognized. Use 'help' for available commands.\n");
        }
    }
    
    // Handle specific commands that might be sent to probe services
    match data_trimmed.to_lowercase().as_str() {
        "help" => {
            format!("Available commands: echo, status, info, quit\n")
        }
        "status" => {
            format!("Server status: Online | Uptime: {} seconds\n", 
                   std::time::SystemTime::now()
                       .duration_since(std::time::UNIX_EPOCH)
                       .unwrap_or_default()
                       .as_secs() % 86400)
        }
        "info" => {
            format!("TCP Echo Server v1.0 | Connection: {}\n", connection_id)
        }
        "quit" | "exit" => {
            format!("Goodbye!\n")
        }
        _ => {
            // Default echo behavior with timestamp
            format!("[{}] ECHO: {}\n", 
                   chrono::Utc::now().format("%H:%M:%S"), 
                   data_trimmed)
        }
    }
}

async fn start_stats_server(stats: Arc<ServerStats>) -> io::Result<()> {
    let listener = TcpListener::bind("0.0.0.0:7879").await?;
    info!("Stats server listening on 0.0.0.0:7879");
    
    loop {
        match listener.accept().await {
            Ok((mut socket, peer_addr)) => {
                let stats = Arc::clone(&stats);
                tokio::spawn(async move {
                    let stats_json = stats.get_stats().await;
                    let response = format!(
                        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                        stats_json.to_string().len(),
                        stats_json
                    );
                    
                    if let Err(e) = socket.write_all(response.as_bytes()).await {
                        error!("Failed to send stats to {}: {}", peer_addr, e);
                    }
                });
            }
            Err(e) => {
                error!("Failed to accept stats connection: {}", e);
            }
        }
    }
}

#[tokio::main]
async fn main() -> io::Result<()> {
    // Initialize logging
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    
    let bind_addr = "0.0.0.0:7878";
    
    // Create a custom socket with specific TTL to mimic Linux kernel behavior
    // This defeats basic nmap OS fingerprinting which often flags default socket behavior
    let socket = Socket::new(Domain::IPV4, Type::STREAM, Some(Protocol::TCP))?;
    socket.set_ttl(64)?; // Linux default TTL
    socket.set_reuse_address(true)?;
    socket.set_nonblocking(true)?;
    
    let address: SocketAddr = bind_addr.parse().unwrap();
    socket.bind(&address.into())?;
    socket.listen(128)?;
    
    let listener = TcpListener::from_std(socket.into())?;
    
    let stats = Arc::new(ServerStats::new());
    
    info!("TCP Echo Server starting on {}", bind_addr);
    info!("Server stats available on http://0.0.0.0:7879");
    
    // Start stats server in background
    let stats_clone = Arc::clone(&stats);
    tokio::spawn(async move {
        if let Err(e) = start_stats_server(stats_clone).await {
            error!("Stats server error: {}", e);
        }
    });
    
    // Main server loop
    loop {
        match listener.accept().await {
            Ok((socket, peer_addr)) => {
                let stats = Arc::clone(&stats);
                tokio::spawn(async move {
                    if let Err(e) = handle_client(socket, peer_addr, stats).await {
                        error!("Error handling client {}: {}", peer_addr, e);
                    }
                });
            }
            Err(e) => {
                error!("Failed to accept connection: {}", e);
                sleep(Duration::from_millis(100)).await;
            }
        }
    }
}
