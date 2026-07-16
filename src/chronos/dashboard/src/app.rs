use eframe::egui;
use egui_extras::{Column, TableBuilder};
use flume::Receiver;
use crate::backend::{AuditEvent, BackendMessage};

pub struct ChronosDashboard {
    rx: Receiver<BackendMessage>,
    redis_connected: bool,
    postgres_connected: bool,
    audit_logs: Vec<AuditEvent>,
    total_files: i32,
}

impl ChronosDashboard {
    pub fn new(_cc: &eframe::CreationContext<'_>, rx: Receiver<BackendMessage>) -> Self {
        Self {
            rx,
            redis_connected: false,
            postgres_connected: false,
            audit_logs: Vec::new(),
            total_files: 0,
        }
    }

    fn update_state(&mut self) {
        while let Ok(msg) = self.rx.try_recv() {
            match msg {
                BackendMessage::RedisConnected(status) => self.redis_connected = status,
                BackendMessage::PostgresConnected(status) => self.postgres_connected = status,
                BackendMessage::AuditLogs(mut events) => {
                    // Prepend new events and keep only the latest 1000
                    for event in events.drain(..).rev() {
                        self.audit_logs.insert(0, event);
                    }
                    if self.audit_logs.len() > 1000 {
                        self.audit_logs.truncate(1000);
                    }
                }
                BackendMessage::TotalFiles(count) => self.total_files = count,
            }
        }
    }
}

impl eframe::App for ChronosDashboard {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.update_state();

        // Top Panel for Status
        egui::TopBottomPanel::top("top_panel").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("Chronos Security Dashboard");
                ui.separator();
                
                ui.label("Redis: ");
                if self.redis_connected {
                    ui.label(egui::RichText::new("ONLINE").color(egui::Color32::GREEN));
                } else {
                    ui.label(egui::RichText::new("OFFLINE").color(egui::Color32::RED));
                }

                ui.separator();
                ui.label("Postgres: ");
                if self.postgres_connected {
                    ui.label(egui::RichText::new("ONLINE").color(egui::Color32::GREEN));
                } else {
                    ui.label(egui::RichText::new("OFFLINE").color(egui::Color32::RED));
                }

                ui.separator();
                ui.label(format!("Inodes tracked: {}", self.total_files));
            });
        });

        // Main Panel for Live Logs
        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("Live Audit Stream");
            ui.separator();

            TableBuilder::new(ui)
                .striped(true)
                .resizable(true)
                .column(Column::initial(150.0).at_least(100.0)) // Timestamp
                .column(Column::initial(100.0).at_least(80.0))  // Operation
                .column(Column::initial(300.0).at_least(100.0)) // Path
                .column(Column::initial(80.0).at_least(50.0))   // Inode
                .column(Column::remainder())                    // Session ID
                .header(20.0, |mut header| {
                    header.col(|ui| { ui.strong("Timestamp"); });
                    header.col(|ui| { ui.strong("Operation"); });
                    header.col(|ui| { ui.strong("Path"); });
                    header.col(|ui| { ui.strong("Inode"); });
                    header.col(|ui| { ui.strong("Session ID"); });
                })
                .body(|mut body| {
                    for event in &self.audit_logs {
                        body.row(20.0, |mut row| {
                            row.col(|ui| { ui.label(event.timestamp.format("%Y-%m-%d %H:%M:%S").to_string()); });
                            row.col(|ui| { 
                                let op = event.operation.as_deref().unwrap_or("-");
                                let color = match op {
                                    "CREATE" | "WRITE" => egui::Color32::RED,
                                    "READ" => egui::Color32::LIGHT_BLUE,
                                    _ => egui::Color32::GRAY,
                                };
                                ui.label(egui::RichText::new(op).color(color)); 
                            });
                            row.col(|ui| { ui.label(event.path.as_deref().unwrap_or("-")); });
                            row.col(|ui| { 
                                if let Some(inode) = event.inode {
                                    ui.label(inode.to_string());
                                } else {
                                    ui.label("-");
                                }
                            });
                            row.col(|ui| { ui.label(event.session_id.as_deref().unwrap_or("-")); });
                        });
                    }
                });
        });

        // Request repaint often since we are listening to real-time events
        ctx.request_repaint_after(std::time::Duration::from_millis(100));
    }
}
