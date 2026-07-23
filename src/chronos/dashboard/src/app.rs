use eframe::egui;
use egui_extras::{Column, TableBuilder};
use flume::{Receiver, Sender};
use crate::backend::{
    AuditEvent, BackendMessage, BackendRequest,
    SessionSummary, SessionDetail,
};

// ── Tab Enum ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq)]
enum Tab {
    LiveOps,
    Sessions,
    SessionDetail,
    ThreatAnalytics,
    AIProvenance,
    Configuration,
}

// ── Dashboard State ─────────────────────────────────────────────────────────

pub struct ChronosDashboard {
    rx: Receiver<BackendMessage>,
    tx_req: Sender<BackendRequest>,

    active_tab: Tab,

    // Health
    redis_connected: bool,
    postgres_connected: bool,
    total_files: i32,
    active_session_count: i32,

    // View 1: Live Ops
    audit_logs: Vec<AuditEvent>,
    stream_paused: bool,
    filter_operation: String,

    // View 2: Sessions
    sessions: Vec<SessionSummary>,

    // View 3: Session Detail
    selected_session: Option<SessionDetail>,
    selected_session_id: Option<String>,
    detail_loading: bool,
}

impl ChronosDashboard {
    pub fn new(
        _cc: &eframe::CreationContext<'_>,
        rx: Receiver<BackendMessage>,
        tx_req: Sender<BackendRequest>,
    ) -> Self {
        // Apply dark theme
        let mut style = (*_cc.egui_ctx.style()).clone();
        style.visuals = egui::Visuals::dark();
        _cc.egui_ctx.set_style(style);

        Self {
            rx,
            tx_req,
            active_tab: Tab::LiveOps,
            redis_connected: false,
            postgres_connected: false,
            total_files: 0,
            active_session_count: 0,
            audit_logs: Vec::new(),
            stream_paused: false,
            filter_operation: "All".to_string(),
            sessions: Vec::new(),
            selected_session: None,
            selected_session_id: None,
            detail_loading: false,
        }
    }

    fn update_state(&mut self) {
        while let Ok(msg) = self.rx.try_recv() {
            match msg {
                BackendMessage::RedisConnected(s) => self.redis_connected = s,
                BackendMessage::PostgresConnected(s) => self.postgres_connected = s,
                BackendMessage::TotalFiles(c) => self.total_files = c,
                BackendMessage::ActiveSessionCount(c) => self.active_session_count = c,
                BackendMessage::AuditLogs(mut events) => {
                    if !self.stream_paused {
                        for event in events.drain(..).rev() {
                            self.audit_logs.insert(0, event);
                        }
                        if self.audit_logs.len() > 1000 {
                            self.audit_logs.truncate(1000);
                        }
                    }
                }
                BackendMessage::SessionList(sessions) => {
                    self.sessions = sessions;
                }
                BackendMessage::SessionDetailResult(detail) => {
                    self.selected_session = *detail;
                    self.detail_loading = false;
                }
            }
        }
    }

    // ── Status pill helper ──────────────────────────────────────────────

    fn status_pill(ui: &mut egui::Ui, label: &str, online: bool) {
        let color = if online {
            egui::Color32::from_rgb(46, 204, 113)
        } else {
            egui::Color32::from_rgb(231, 76, 60)
        };
        let text = if online { "ONLINE" } else { "OFFLINE" };

        ui.horizontal(|ui| {
            ui.label(egui::RichText::new("●").color(color).size(10.0));
            ui.label(egui::RichText::new(label).strong().size(11.0));
            ui.label(egui::RichText::new(text).color(color).size(11.0));
        });
    }

    // ── Top bar ─────────────────────────────────────────────────────────

    fn render_top_bar(&mut self, ctx: &egui::Context) {
        egui::TopBottomPanel::top("top_bar").show(ctx, |ui| {
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                ui.heading(egui::RichText::new("⎔ Chronos Overseer").strong());
                ui.separator();

                Self::status_pill(ui, "Redis", self.redis_connected);
                ui.separator();
                Self::status_pill(ui, "Postgres", self.postgres_connected);
                ui.separator();

                ui.label(egui::RichText::new(format!("📁 {} inodes", self.total_files)).size(11.0));
                ui.separator();
                ui.label(egui::RichText::new(format!("👤 {} active", self.active_session_count)).size(11.0));
            });
            ui.add_space(2.0);

            // Tab bar
            ui.horizontal(|ui| {
                let tabs = [
                    (Tab::LiveOps, "⚡ Live Ops"),
                    (Tab::Sessions, "📋 Sessions"),
                    (Tab::SessionDetail, "🔍 Detail"),
                    (Tab::ThreatAnalytics, "📊 Analytics"),
                    (Tab::AIProvenance, "🤖 AI Provenance"),
                    (Tab::Configuration, "⚙ Config"),
                ];
                for (tab, label) in tabs {
                    let selected = self.active_tab == tab;
                    if ui.selectable_label(selected, egui::RichText::new(label).size(12.0)).clicked() {
                        self.active_tab = tab;
                    }
                }
            });
            ui.add_space(2.0);
        });
    }

    // ── View 1: Live Ops ────────────────────────────────────────────────

    fn render_live_ops(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.heading("Live Audit Stream");
            ui.separator();

            let pause_label = if self.stream_paused { "▶ Resume" } else { "⏸ Pause" };
            if ui.button(egui::RichText::new(pause_label).size(12.0)).clicked() {
                self.stream_paused = !self.stream_paused;
            }

            ui.separator();
            ui.label("Filter:");
            for filter in ["All", "READ", "WRITE", "CREATE"] {
                if ui.selectable_label(self.filter_operation == filter, filter).clicked() {
                    self.filter_operation = filter.to_string();
                }
            }

            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.label(egui::RichText::new(format!("{} events", self.audit_logs.len()))
                    .color(egui::Color32::GRAY).size(11.0));
            });
        });

        ui.separator();

        let filtered_logs: Vec<&AuditEvent> = self.audit_logs.iter().filter(|e| {
            if self.filter_operation == "All" { return true; }
            e.operation.as_deref() == Some(self.filter_operation.as_str())
        }).collect();

        let available_height = ui.available_height();
        TableBuilder::new(ui)
            .striped(true)
            .resizable(true)
            .min_scrolled_height(available_height)
            .max_scroll_height(available_height)
            .column(Column::initial(140.0).at_least(100.0))  // Timestamp
            .column(Column::initial(80.0).at_least(60.0))    // Operation
            .column(Column::initial(300.0).at_least(100.0))  // Path
            .column(Column::initial(60.0).at_least(40.0))    // Inode
            .column(Column::remainder())                      // Session ID
            .header(18.0, |mut header| {
                header.col(|ui| { ui.strong("Timestamp"); });
                header.col(|ui| { ui.strong("Operation"); });
                header.col(|ui| { ui.strong("Path"); });
                header.col(|ui| { ui.strong("Inode"); });
                header.col(|ui| { ui.strong("Session"); });
            })
            .body(|body| {
                body.rows(18.0, filtered_logs.len(), |mut row| {
                    let event = &filtered_logs[row.index()];
                    row.col(|ui| {
                        ui.label(egui::RichText::new(
                            event.timestamp.format("%H:%M:%S").to_string()
                        ).size(11.0));
                    });
                    row.col(|ui| {
                        let op = event.operation.as_deref().unwrap_or("-");
                        let color = match op {
                            "CREATE" | "WRITE" => egui::Color32::from_rgb(231, 76, 60),
                            "READ" => egui::Color32::from_rgb(52, 152, 219),
                            "DELETE" => egui::Color32::from_rgb(241, 196, 15),
                            _ => egui::Color32::GRAY,
                        };
                        ui.label(egui::RichText::new(op).color(color).size(11.0));
                    });
                    row.col(|ui| {
                        ui.label(egui::RichText::new(
                            event.path.as_deref().unwrap_or("-")
                        ).size(11.0));
                    });
                    row.col(|ui| {
                        let text = event.inode.map_or("-".to_string(), |i| i.to_string());
                        ui.label(egui::RichText::new(text).size(11.0));
                    });
                    row.col(|ui| {
                        let sid = event.session_id.as_deref().unwrap_or("-");
                        let short = if sid.len() > 8 { &sid[..8] } else { sid };
                        ui.label(egui::RichText::new(short).size(11.0));
                    });
                });
            });
    }

    // ── View 2: Sessions ────────────────────────────────────────────────

    fn render_sessions(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.heading("Session History");
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.label(egui::RichText::new(format!("{} sessions", self.sessions.len()))
                    .color(egui::Color32::GRAY).size(11.0));
            });
        });
        ui.separator();

        if self.sessions.is_empty() {
            ui.centered_and_justified(|ui| {
                ui.label(egui::RichText::new("No sessions recorded yet.")
                    .color(egui::Color32::GRAY).size(14.0));
            });
            return;
        }

        let available_height = ui.available_height();
        TableBuilder::new(ui)
            .striped(true)
            .resizable(true)
            .min_scrolled_height(available_height)
            .max_scroll_height(available_height)
            .sense(egui::Sense::click())
            .column(Column::initial(80.0).at_least(60.0))    // Session ID
            .column(Column::initial(80.0).at_least(60.0))    // Duration
            .column(Column::initial(90.0).at_least(70.0))    // Status
            .column(Column::initial(80.0).at_least(50.0))    // Confidence
            .column(Column::initial(80.0).at_least(60.0))    // Exit
            .column(Column::remainder())                      // First Suspicious
            .header(18.0, |mut header| {
                header.col(|ui| { ui.strong("Session"); });
                header.col(|ui| { ui.strong("Duration"); });
                header.col(|ui| { ui.strong("Status"); });
                header.col(|ui| { ui.strong("Confidence"); });
                header.col(|ui| { ui.strong("Exit"); });
                header.col(|ui| { ui.strong("First Suspicious Cmd"); });
            })
            .body(|body| {
                let sessions_clone = self.sessions.clone();
                body.rows(20.0, sessions_clone.len(), |mut row| {
                    let session = &sessions_clone[row.index()];
                    let sid = &session.session_id;

                    row.col(|ui| {
                        let short = if sid.len() > 8 { &sid[..8] } else { sid };
                        ui.label(egui::RichText::new(format!("{}…", short))
                            .color(egui::Color32::from_rgb(52, 152, 219)).size(11.0));
                    });
                    row.col(|ui| {
                        let dur = session.duration_seconds.unwrap_or(0);
                        let text = if dur > 60 { format!("{}m {}s", dur / 60, dur % 60) } else { format!("{}s", dur) };
                        ui.label(egui::RichText::new(text).size(11.0));
                    });
                    row.col(|ui| {
                        let status = session.detection_status.as_deref().unwrap_or("unknown");
                        let color = match status {
                            "detected" => egui::Color32::from_rgb(231, 76, 60),
                            "undetected" | "undected" => egui::Color32::from_rgb(46, 204, 113),
                            _ => egui::Color32::GRAY,
                        };
                        ui.label(egui::RichText::new(status.to_uppercase()).color(color).size(11.0));
                    });
                    row.col(|ui| {
                        let conf = session.detection_confidence.unwrap_or(0.0);
                        let bar = egui::ProgressBar::new(conf as f32)
                            .text(format!("{:.0}%", conf * 100.0));
                        ui.add(bar);
                    });
                    row.col(|ui| {
                        ui.label(egui::RichText::new(
                            session.exit_reason.as_deref().unwrap_or("-")
                        ).size(11.0));
                    });
                    row.col(|ui| {
                        let cmd = session.first_suspicious_command.as_deref().unwrap_or("-");
                        let truncated = if cmd.len() > 40 { format!("{}…", &cmd[..40]) } else { cmd.to_string() };
                        ui.label(egui::RichText::new(truncated).size(11.0));
                    });

                    if row.response().clicked() {
                        self.selected_session_id = Some(sid.clone());
                        self.detail_loading = true;
                        self.selected_session = None;
                        let _ = self.tx_req.send(BackendRequest::FetchSessionDetail(sid.clone()));
                        self.active_tab = Tab::SessionDetail;
                    }
                });
            });
    }

    // ── View 3: Session Detail ──────────────────────────────────────────

    fn render_session_detail(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            if ui.button("← Back to Sessions").clicked() {
                self.active_tab = Tab::Sessions;
                self.selected_session = None;
                self.selected_session_id = None;
            }
            ui.heading("Session Detail");
        });
        ui.separator();

        if self.detail_loading {
            ui.centered_and_justified(|ui| {
                ui.spinner();
            });
            return;
        }

        let detail = match &self.selected_session {
            Some(d) => d,
            None => {
                ui.centered_and_justified(|ui| {
                    ui.label(egui::RichText::new("Select a session from the Sessions tab.")
                        .color(egui::Color32::GRAY).size(14.0));
                });
                return;
            }
        };

        // Header card
        egui::Frame::group(ui.style()).show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("Session:").strong());
                ui.label(&detail.session_id);
                ui.separator();
                ui.label(egui::RichText::new("Duration:").strong());
                let dur = detail.duration_seconds.unwrap_or(0);
                ui.label(format!("{}m {}s", dur / 60, dur % 60));
                ui.separator();
                let status = detail.detection_status.as_deref().unwrap_or("unknown");
                let color = if status == "detected" {
                    egui::Color32::from_rgb(231, 76, 60)
                } else {
                    egui::Color32::from_rgb(46, 204, 113)
                };
                ui.label(egui::RichText::new(status.to_uppercase()).color(color).strong());
                ui.separator();
                ui.label(egui::RichText::new("Confidence:").strong());
                let conf = detail.detection_confidence.unwrap_or(0.0);
                ui.add(egui::ProgressBar::new(conf as f32).text(format!("{:.0}%", conf * 100.0)).desired_width(80.0));
            });
        });

        ui.add_space(8.0);

        // Two-column layout: commands on left, tree + skill on right
        let available = ui.available_size();
        ui.horizontal(|ui| {
            // Left: Command Timeline
            ui.vertical(|ui| {
                ui.set_width(available.x * 0.6);
                ui.heading(egui::RichText::new("Command Timeline").size(14.0));
                ui.separator();

                egui::ScrollArea::vertical().max_height(available.y - 100.0).show(ui, |ui| {
                    for cmd in &detail.commands {
                        let risk = cmd.risk_score.unwrap_or(0);
                        let bg = if risk > 50 {
                            egui::Color32::from_rgba_premultiplied(231, 76, 60, 30)
                        } else if risk > 0 {
                            egui::Color32::from_rgba_premultiplied(241, 196, 15, 20)
                        } else {
                            egui::Color32::TRANSPARENT
                        };

                        egui::Frame::none().fill(bg).inner_margin(4.0).show(ui, |ui| {
                            ui.horizontal(|ui| {
                                // Timestamp
                                let ts = cmd.timestamp.as_deref().unwrap_or("");
                                let short_ts = if ts.len() > 19 { &ts[11..19] } else { ts };
                                ui.label(egui::RichText::new(short_ts)
                                    .color(egui::Color32::GRAY).size(10.0).monospace());

                                // Risk badge
                                let risk_color = if risk > 50 {
                                    egui::Color32::from_rgb(231, 76, 60)
                                } else if risk > 0 {
                                    egui::Color32::from_rgb(241, 196, 15)
                                } else {
                                    egui::Color32::from_rgb(46, 204, 113)
                                };
                                ui.label(egui::RichText::new(format!("R:{}", risk))
                                    .color(risk_color).size(10.0));

                                // Command
                                ui.label(egui::RichText::new(
                                    cmd.command.as_deref().unwrap_or("-")
                                ).monospace().size(11.0));
                            });

                            // Techniques
                            if let Some(techniques) = &cmd.techniques {
                                if !techniques.is_empty() {
                                    ui.horizontal(|ui| {
                                        ui.add_space(60.0);
                                        for t in techniques {
                                            ui.label(egui::RichText::new(format!("⚑ {}", t))
                                                .color(egui::Color32::from_rgb(155, 89, 182)).size(9.0));
                                        }
                                    });
                                }
                            }
                        });
                    }
                });
            });

            ui.separator();

            // Right: Traversal Tree + Skill Card
            ui.vertical(|ui| {
                ui.set_width(available.x * 0.35);

                // Skill Assessment Card
                if let Some(skill) = &detail.skill_assessment {
                    ui.heading(egui::RichText::new("Skill Assessment").size(14.0));
                    ui.separator();
                    egui::Frame::group(ui.style()).show(ui, |ui| {
                        if let Some(level) = skill.get("skill_level").and_then(|v| v.as_str()) {
                            let color = match level {
                                "expert" => egui::Color32::from_rgb(231, 76, 60),
                                "advanced" => egui::Color32::from_rgb(230, 126, 34),
                                "intermediate" => egui::Color32::from_rgb(241, 196, 15),
                                "opportunistic" => egui::Color32::from_rgb(52, 152, 219),
                                _ => egui::Color32::from_rgb(46, 204, 113),
                            };
                            ui.label(egui::RichText::new(level.to_uppercase()).color(color).strong().size(16.0));
                        }
                        if let Some(score) = skill.get("skill_score").and_then(|v| v.as_i64()) {
                            ui.label(format!("Score: {}", score));
                        }
                        if let Some(confidence) = skill.get("confidence").and_then(|v| v.as_str()) {
                            ui.label(format!("Confidence: {}", confidence));
                        }
                        if let Some(indicators) = skill.get("indicators").and_then(|v| v.as_array()) {
                            ui.add_space(4.0);
                            for ind in indicators {
                                if let Some(s) = ind.as_str() {
                                    ui.label(egui::RichText::new(format!("• {}", s)).size(10.0));
                                }
                            }
                        }
                    });
                    ui.add_space(8.0);
                }

                // Traversal Tree
                ui.heading(egui::RichText::new("Traversal Tree").size(14.0));
                ui.separator();
                egui::ScrollArea::vertical().max_height(200.0).show(ui, |ui| {
                    if let serde_json::Value::Object(map) = &detail.traversal_graph {
                        for (parent, children) in map {
                            ui.collapsing(egui::RichText::new(format!("📁 {}", parent)).monospace(), |ui| {
                                if let serde_json::Value::Array(arr) = children {
                                    for child in arr {
                                        if let Some(name) = child.as_str() {
                                            ui.label(egui::RichText::new(format!("  📄 {}", name)).monospace().size(10.0));
                                        }
                                    }
                                }
                            });
                        }
                    }
                });

                // Visited Files
                ui.add_space(8.0);
                ui.heading(egui::RichText::new("Visited Files").size(14.0));
                ui.separator();
                egui::ScrollArea::vertical().max_height(150.0).show(ui, |ui| {
                    for f in &detail.visited_files {
                        ui.label(egui::RichText::new(f).monospace().size(10.0));
                    }
                });
            });
        });
    }

    // ── Stub views ──────────────────────────────────────────────────────

    fn render_stub(ui: &mut egui::Ui, title: &str, description: &str) {
        ui.centered_and_justified(|ui| {
            ui.vertical_centered(|ui| {
                ui.add_space(80.0);
                ui.heading(egui::RichText::new(title).size(20.0));
                ui.add_space(8.0);
                ui.label(egui::RichText::new(description)
                    .color(egui::Color32::GRAY).size(13.0));
                ui.add_space(8.0);
                ui.label(egui::RichText::new("🚧 Coming soon")
                    .color(egui::Color32::from_rgb(241, 196, 15)).size(12.0));
            });
        });
    }
}

// ── Main render loop ────────────────────────────────────────────────────────

impl eframe::App for ChronosDashboard {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.update_state();
        self.render_top_bar(ctx);

        egui::CentralPanel::default().show(ctx, |ui| {
            match self.active_tab {
                Tab::LiveOps => self.render_live_ops(ui),
                Tab::Sessions => self.render_sessions(ui),
                Tab::SessionDetail => self.render_session_detail(ui),
                Tab::ThreatAnalytics => Self::render_stub(ui,
                    "Threat & Skill Analytics",
                    "Technique frequency, attack-phase funnels, and skill-level distributions.\nBlocked until SkillDetector persistence is verified with live data."
                ),
                Tab::AIProvenance => Self::render_stub(ui,
                    "AI Provenance",
                    "Track which files were AI-generated vs static template, model used,\nvalidation pass/fail, and generation latency."
                ),
                Tab::Configuration => Self::render_stub(ui,
                    "Configuration",
                    "Edit Ubuntu Profile (ubuntu.yaml) and Generation Policy (generation_policy.yaml).\nRequires core-engine restart to apply changes."
                ),
            }
        });

        ctx.request_repaint_after(std::time::Duration::from_millis(100));
    }
}
