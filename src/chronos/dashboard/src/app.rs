use crate::backend::{
    AuditEvent, BackendMessage, BackendRequest, ExportMode, ProvenanceSummary, SessionDetail,
    SessionStats, SessionSummary,
};
use eframe::egui;
use egui_extras::{Column, TableBuilder};
use flume::{Receiver, Sender};
use std::collections::BTreeMap;

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
    open_session_count: i32,

    // View 1: Live Ops
    audit_logs: Vec<AuditEvent>,
    stream_paused: bool,
    paused_logs: Vec<AuditEvent>,
    filter_operation: String,

    // View 2: Sessions
    sessions: Vec<SessionSummary>,
    session_total: i64,
    session_offset: i64,
    session_limit: i64,
    session_snapshot_at: Option<chrono::NaiveDateTime>,
    session_page_loading: bool,
    session_page_error: Option<String>,
    session_stats: SessionStats,

    // View 3: Session Detail
    selected_session: Option<SessionDetail>,
    selected_session_id: Option<String>,
    detail_loading: bool,
    export_destination: String,
    export_busy: bool,
    export_status: String,

    // View 4: Provenance
    provenance_snapshot: Option<ProvenanceSummary>,
    selected_provenance_entry: Option<usize>,
}

impl ChronosDashboard {
    pub fn new(
        _cc: &eframe::CreationContext<'_>,
        rx: Receiver<BackendMessage>,
        tx_req: Sender<BackendRequest>,
    ) -> Self {
        // Apply dark theme
        let mut style = (*_cc.egui_ctx.style_of(egui::Theme::Dark)).clone();
        style.visuals = egui::Visuals::dark();
        _cc.egui_ctx.set_style_of(egui::Theme::Dark, style);
        _cc.egui_ctx.set_theme(egui::Theme::Dark);

        let session_limit = 50;
        let session_page_loading = tx_req
            .try_send(BackendRequest::FetchSessionPage {
                offset: 0,
                limit: session_limit,
                snapshot_at: None,
            })
            .is_ok();

        Self {
            rx,
            tx_req,
            active_tab: Tab::LiveOps,
            redis_connected: false,
            postgres_connected: false,
            total_files: 0,
            open_session_count: 0,
            audit_logs: Vec::new(),
            stream_paused: false,
            paused_logs: Vec::new(),
            filter_operation: "All".to_string(),
            sessions: Vec::new(),
            session_total: 0,
            session_offset: 0,
            session_limit,
            session_snapshot_at: None,
            session_page_loading,
            session_page_error: None,
            session_stats: SessionStats::default(),
            selected_session: None,
            selected_session_id: None,
            detail_loading: false,
            export_destination: String::new(),
            export_busy: false,
            export_status: String::new(),
            provenance_snapshot: None,
            selected_provenance_entry: None,
        }
    }

    fn update_state(&mut self) {
        while let Ok(msg) = self.rx.try_recv() {
            match msg {
                BackendMessage::RedisConnected(s) => {
                    self.redis_connected = s;
                    if !s {
                        self.total_files = 0;
                        self.provenance_snapshot = None;
                        self.selected_provenance_entry = None;
                    }
                }
                BackendMessage::PostgresConnected(s) => self.postgres_connected = s,
                BackendMessage::TotalFiles(c) => self.total_files = c,
                BackendMessage::OpenSessionCount(c) => self.open_session_count = c,
                BackendMessage::AuditLogs(mut events) => {
                    for event in events.drain(..) {
                        if !self
                            .audit_logs
                            .iter()
                            .any(|existing| existing.id == event.id)
                        {
                            self.audit_logs.push(event);
                        }
                    }
                    self.audit_logs
                        .sort_by_key(|event| std::cmp::Reverse(event.id));
                    if self.audit_logs.len() > 1000 {
                        self.audit_logs.truncate(1000);
                    }
                }
                BackendMessage::SessionPage {
                    sessions,
                    total,
                    offset,
                    limit,
                    snapshot_at,
                } => {
                    self.sessions = sessions;
                    self.session_total = total;
                    self.session_offset = offset;
                    self.session_limit = limit;
                    self.session_snapshot_at = Some(snapshot_at);
                    self.session_page_loading = false;
                    self.session_page_error = None;
                }
                BackendMessage::SessionPageError(message) => {
                    self.session_page_loading = false;
                    self.session_page_error = Some(message);
                }
                BackendMessage::SessionStats(stats) => {
                    let finalized_changed =
                        stats.finalized_count != self.session_stats.finalized_count;
                    self.session_stats = stats;
                    if finalized_changed && self.session_offset == 0 && !self.session_page_loading {
                        self.session_page_loading = self
                            .tx_req
                            .try_send(BackendRequest::FetchSessionPage {
                                offset: 0,
                                limit: self.session_limit,
                                snapshot_at: None,
                            })
                            .is_ok();
                    }
                }
                BackendMessage::ExportResult(result) => {
                    self.export_busy = false;
                    self.export_status = match result {
                        Ok(path) => format!(
                            "Export complete: {}. Inspect complete.json and report.md for artifact type and disclosure limits.",
                            path
                        ),
                        Err(message) => message,
                    };
                }
                BackendMessage::SessionDetailResult(detail) => {
                    self.selected_session = *detail;
                    self.detail_loading = false;
                }
                BackendMessage::ProvenanceSnapshot(snapshot) => {
                    self.provenance_snapshot = Some(snapshot);
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

    fn render_top_bar(&mut self, ui: &mut egui::Ui) {
        egui::Panel::top("top_bar").show(ui, |ui| {
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
                ui.label(
                    egui::RichText::new(format!("👤 {} recorded open", self.open_session_count))
                        .size(11.0),
                );
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
                    if ui
                        .selectable_label(selected, egui::RichText::new(label).size(12.0))
                        .clicked()
                    {
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

            let pause_label = if self.stream_paused {
                "▶ Resume"
            } else {
                "⏸ Pause"
            };
            if ui
                .button(egui::RichText::new(pause_label).size(12.0))
                .clicked()
            {
                self.stream_paused = !self.stream_paused;
                if self.stream_paused {
                    self.paused_logs = self.audit_logs.clone();
                } else {
                    self.paused_logs.clear();
                }
            }

            ui.separator();
            ui.label("Filter:");
            for filter in ["All", "READ", "WRITE", "CREATE"] {
                if ui
                    .selectable_label(self.filter_operation == filter, filter)
                    .clicked()
                {
                    self.filter_operation = filter.to_string();
                }
            }

            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.label(
                    egui::RichText::new(format!("{} events", self.audit_logs.len()))
                        .color(egui::Color32::GRAY)
                        .size(11.0),
                );
            });
        });

        ui.separator();

        ui.label("Live preview: newest 1,000 events, not a complete research export. Pause freezes the view only.");
        let visible_logs = if self.stream_paused {
            &self.paused_logs
        } else {
            &self.audit_logs
        };
        let filtered_logs: Vec<&AuditEvent> = visible_logs
            .iter()
            .filter(|e| {
                if self.filter_operation == "All" {
                    return true;
                }
                e.operation
                    .as_deref()
                    .is_some_and(|op| op.eq_ignore_ascii_case(&self.filter_operation))
            })
            .collect();

        let available_height = ui.available_height();
        TableBuilder::new(ui)
            .striped(true)
            .resizable(true)
            .min_scrolled_height(available_height)
            .max_scroll_height(available_height)
            .column(Column::initial(140.0).at_least(100.0)) // Timestamp
            .column(Column::initial(80.0).at_least(60.0)) // Operation
            .column(Column::initial(300.0).at_least(100.0)) // Path
            .column(Column::initial(60.0).at_least(40.0)) // Inode
            .column(Column::remainder()) // Session ID
            .header(18.0, |mut header| {
                header.col(|ui| {
                    ui.strong("Timestamp");
                });
                header.col(|ui| {
                    ui.strong("Operation");
                });
                header.col(|ui| {
                    ui.strong("Path");
                });
                header.col(|ui| {
                    ui.strong("Inode");
                });
                header.col(|ui| {
                    ui.strong("Session");
                });
            })
            .body(|body| {
                body.rows(18.0, filtered_logs.len(), |mut row| {
                    let event = &filtered_logs[row.index()];
                    row.col(|ui| {
                        ui.label(
                            egui::RichText::new(event.timestamp.format("%H:%M:%S").to_string())
                                .size(11.0),
                        );
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
                        ui.label(
                            egui::RichText::new(event.path.as_deref().unwrap_or("-")).size(11.0),
                        );
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
        let current_page = self.session_offset / self.session_limit + 1;
        let page_count =
            ((self.session_total + self.session_limit - 1) / self.session_limit).max(1);
        ui.horizontal(|ui| {
            ui.heading("Finalized Session History");
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.label(
                    egui::RichText::new(format!(
                        "{} total · page {} of {}",
                        self.session_total, current_page, page_count
                    ))
                    .color(egui::Color32::GRAY)
                    .size(11.0),
                );
            });
        });
        ui.horizontal(|ui| {
            let previous = ui.add_enabled(
                !self.session_page_loading && self.session_offset > 0,
                egui::Button::new("← Previous"),
            );
            if previous.clicked() {
                let offset = (self.session_offset - self.session_limit).max(0);
                self.session_page_loading = self
                    .tx_req
                    .try_send(BackendRequest::FetchSessionPage {
                        offset,
                        limit: self.session_limit,
                        snapshot_at: self.session_snapshot_at,
                    })
                    .is_ok();
            }
            let has_next = self.session_offset + (self.sessions.len() as i64) < self.session_total;
            let next = ui.add_enabled(
                !self.session_page_loading && has_next,
                egui::Button::new("Next →"),
            );
            if next.clicked() {
                let offset = self.session_offset + self.session_limit;
                self.session_page_loading = self
                    .tx_req
                    .try_send(BackendRequest::FetchSessionPage {
                        offset,
                        limit: self.session_limit,
                        snapshot_at: self.session_snapshot_at,
                    })
                    .is_ok();
            }
            if ui
                .add_enabled(!self.session_page_loading, egui::Button::new("Refresh"))
                .clicked()
            {
                self.session_page_loading = self
                    .tx_req
                    .try_send(BackendRequest::FetchSessionPage {
                        offset: 0,
                        limit: self.session_limit,
                        snapshot_at: None,
                    })
                    .is_ok();
            }
            if self.session_page_loading {
                ui.spinner();
            }
        });
        ui.separator();

        if let Some(message) = &self.session_page_error {
            ui.colored_label(egui::Color32::from_rgb(231, 76, 60), message);
        }

        if self.session_page_loading && self.sessions.is_empty() {
            ui.centered_and_justified(|ui| {
                ui.spinner();
            });
            return;
        }

        if self.sessions.is_empty() {
            ui.centered_and_justified(|ui| {
                ui.label(
                    egui::RichText::new("No sessions recorded yet.")
                        .color(egui::Color32::GRAY)
                        .size(14.0),
                );
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
            .column(Column::initial(80.0).at_least(60.0)) // Session ID
            .column(Column::initial(80.0).at_least(60.0)) // Duration
            .column(Column::initial(90.0).at_least(70.0)) // Status
            .column(Column::initial(80.0).at_least(50.0)) // Confidence
            .column(Column::initial(80.0).at_least(60.0)) // Exit
            .column(Column::remainder()) // First Suspicious
            .header(18.0, |mut header| {
                header.col(|ui| {
                    ui.strong("Session");
                });
                header.col(|ui| {
                    ui.strong("Duration");
                });
                header.col(|ui| {
                    ui.strong("Status");
                });
                header.col(|ui| {
                    ui.strong("Calibration");
                });
                header.col(|ui| {
                    ui.strong("Exit");
                });
                header.col(|ui| {
                    ui.strong("First Suspicious Cmd");
                });
            })
            .body(|body| {
                let sessions_clone = self.sessions.clone();
                body.rows(20.0, sessions_clone.len(), |mut row| {
                    let session = &sessions_clone[row.index()];
                    let sid = &session.session_id;
                    let mut open_detail = false;

                    row.col(|ui| {
                        let short = if sid.len() > 8 { &sid[..8] } else { sid };
                        open_detail = ui
                            .link(
                                egui::RichText::new(format!("{}…", short))
                                    .color(egui::Color32::from_rgb(52, 152, 219))
                                    .size(11.0),
                            )
                            .on_hover_text(format!("Open session {}", sid))
                            .clicked();
                    });
                    row.col(|ui| {
                        let text = match session.duration_seconds {
                            Some(dur) if dur > 60 => format!("{}m {}s", dur / 60, dur % 60),
                            Some(dur) => format!("{}s", dur),
                            None => "unknown".into(),
                        };
                        ui.label(egui::RichText::new(text).size(11.0));
                    });
                    row.col(|ui| {
                        let status = session.detection_status.as_deref().unwrap_or("unknown");
                        let color = match status {
                            "detected" => egui::Color32::from_rgb(231, 76, 60),
                            "undetected" | "undected" => egui::Color32::from_rgb(46, 204, 113),
                            _ => egui::Color32::GRAY,
                        };
                        ui.label(
                            egui::RichText::new(status.to_uppercase())
                                .color(color)
                                .size(11.0),
                        );
                    });
                    row.col(|ui| {
                        ui.label("Not calibrated");
                    });
                    row.col(|ui| {
                        ui.label(
                            egui::RichText::new(session.exit_reason.as_deref().unwrap_or("-"))
                                .size(11.0),
                        );
                    });
                    row.col(|ui| {
                        let cmd = session.first_suspicious_command.as_deref().unwrap_or("-");
                        let truncated = if cmd.chars().count() > 40 {
                            format!("{}…", cmd.chars().take(40).collect::<String>())
                        } else {
                            cmd.to_string()
                        };
                        ui.label(egui::RichText::new(truncated).size(11.0));
                    });

                    if open_detail || row.response().clicked() {
                        self.selected_session_id = Some(sid.clone());
                        self.detail_loading = self
                            .tx_req
                            .try_send(BackendRequest::FetchSessionDetail(sid.clone()))
                            .is_ok();
                        self.selected_session = None;
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
                    ui.label(
                        egui::RichText::new("Select a session from the Sessions tab.")
                            .color(egui::Color32::GRAY)
                            .size(14.0),
                    );
                });
                return;
            }
        };

        ui.horizontal(|ui| {
            ui.label("New export folder:");
            ui.text_edit_singleline(&mut self.export_destination);
            if ui
                .add_enabled(
                    !self.export_busy && !self.export_destination.trim().is_empty(),
                    egui::Button::new("Export private raw"),
                )
                .clicked()
            {
                self.export_busy = self
                    .tx_req
                    .try_send(BackendRequest::ExportSession {
                        session_id: detail.session_id.clone(),
                        destination: self.export_destination.clone(),
                        mode: ExportMode::Raw,
                    })
                    .is_ok();
                self.export_status = if self.export_busy {
                    "Exporting database snapshot…".into()
                } else {
                    "Export backend is unavailable.".into()
                };
            }
            if ui
                .add_enabled(
                    !self.export_busy && !self.export_destination.trim().is_empty(),
                    egui::Button::new("Export redacted copy"),
                )
                .clicked()
            {
                self.export_busy = self
                    .tx_req
                    .try_send(BackendRequest::ExportSession {
                        session_id: detail.session_id.clone(),
                        destination: self.export_destination.clone(),
                        mode: ExportMode::Redacted,
                    })
                    .is_ok();
                self.export_status = if self.export_busy {
                    "Exporting allowlist-redacted database snapshot…".into()
                } else {
                    "Export backend is unavailable.".into()
                };
            }
        });
        ui.label(&self.export_status);

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
                ui.label(
                    egui::RichText::new(status.to_uppercase())
                        .color(color)
                        .strong(),
                );
                ui.separator();
                ui.label("Rule-based flag; not a probability or evidence of honeypot discovery.");
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

                egui::ScrollArea::vertical()
                    .id_salt("session_command_timeline")
                    .max_height(available.y - 100.0)
                    .show(ui, |ui| {
                        for cmd in &detail.commands {
                            let risk = cmd.risk_score.unwrap_or(0);
                            let bg = if risk > 50 {
                                egui::Color32::from_rgba_premultiplied(231, 76, 60, 30)
                            } else if risk > 0 {
                                egui::Color32::from_rgba_premultiplied(241, 196, 15, 20)
                            } else {
                                egui::Color32::TRANSPARENT
                            };

                            egui::Frame::new()
                                .fill(bg)
                                .inner_margin(4.0)
                                .show(ui, |ui| {
                                    ui.horizontal(|ui| {
                                        // Timestamp
                                        let ts = cmd.timestamp.as_deref().unwrap_or("");
                                        let short_ts = ts.get(11..19).unwrap_or(ts);
                                        ui.label(
                                            egui::RichText::new(short_ts)
                                                .color(egui::Color32::GRAY)
                                                .size(10.0)
                                                .monospace(),
                                        );

                                        // Risk badge
                                        let risk_color = if risk > 50 {
                                            egui::Color32::from_rgb(231, 76, 60)
                                        } else if risk > 0 {
                                            egui::Color32::from_rgb(241, 196, 15)
                                        } else {
                                            egui::Color32::from_rgb(46, 204, 113)
                                        };
                                        ui.label(
                                            egui::RichText::new(format!("R:{}", risk))
                                                .color(risk_color)
                                                .size(10.0),
                                        );

                                        // Command
                                        ui.label(
                                            egui::RichText::new(
                                                cmd.command.as_deref().unwrap_or("-"),
                                            )
                                            .monospace()
                                            .size(11.0),
                                        );
                                    });

                                    // Techniques
                                    ui.horizontal(|ui| {
                                        ui.label(format!(
                                            "Outcome: {}",
                                            cmd.outcome
                                                .as_deref()
                                                .unwrap_or("unknown (legacy record)")
                                        ));
                                        if let Some(status) = cmd.exit_status {
                                            ui.label(format!("exit {}", status));
                                        }
                                        if let Some(seconds) = cmd.server_elapsed_seconds {
                                            ui.label(format!("server {:.3}s", seconds));
                                        }
                                        if let Some(bytes) = cmd.response_bytes {
                                            ui.label(format!("{} response bytes", bytes));
                                        }
                                        if let (Some(claimed), Some(effective)) =
                                            (&cmd.claimed_username, &cmd.effective_username)
                                        {
                                            ui.label(format!(
                                                "login {} → profile {}",
                                                claimed, effective
                                            ));
                                        }
                                    });
                                    if let Some(techniques) = &cmd.techniques {
                                        if !techniques.is_empty() {
                                            ui.horizontal(|ui| {
                                                ui.add_space(60.0);
                                                for t in techniques {
                                                    ui.label(
                                                        egui::RichText::new(format!("⚑ {}", t))
                                                            .color(egui::Color32::from_rgb(
                                                                155, 89, 182,
                                                            ))
                                                            .size(9.0),
                                                    );
                                                }
                                            });
                                        }
                                    }
                                });
                        }
                    });
            });

            ui.separator();

            // Right: Traversal Tree + evidence-linked pattern card
            ui.vertical(|ui| {
                ui.set_width(available.x * 0.35);

                // The database field retains its legacy name, but schema v2 is
                // explicitly an observation summary, not an expertise estimate.
                if let Some(patterns) = &detail.pattern_assessment {
                    ui.heading(egui::RichText::new("Observed Patterns").size(14.0));
                    ui.separator();
                    egui::Frame::group(ui.style()).show(ui, |ui| {
                        if patterns.get("assessment_type").and_then(|v| v.as_str())
                            != Some("observable_session_patterns")
                        {
                            ui.label(
                                egui::RichText::new(
                                    "Legacy expertise estimate suppressed; regenerate this session summary.",
                                )
                                .italics()
                                .color(egui::Color32::GRAY)
                                .size(9.0),
                            );
                        } else if let Some(labels) = patterns
                            .get("pattern_labels")
                            .and_then(|v| v.as_array())
                        {
                            for label in labels {
                                if let Some(text) = label.as_str() {
                                    ui.label(
                                        egui::RichText::new(format!(
                                            "• {}",
                                            text.replace('_', " ")
                                        ))
                                        .size(10.0),
                                    );
                                }
                            }
                        }
                        ui.add_space(4.0);
                        ui.label(
                            egui::RichText::new(
                                "Labels describe recorded text and rule matches; they do not infer expertise.",
                            )
                            .italics()
                            .color(egui::Color32::GRAY)
                            .size(9.0),
                        );
                    });
                    ui.add_space(8.0);
                }

                // Traversal Tree
                ui.heading(egui::RichText::new("Traversal Tree").size(14.0));
                ui.separator();
                egui::ScrollArea::vertical()
                    .id_salt("session_traversal_tree")
                    .max_height(200.0)
                    .show(ui, |ui| {
                        if let serde_json::Value::Object(map) = &detail.traversal_graph {
                            for (parent, children) in map {
                                ui.collapsing(
                                    egui::RichText::new(format!("📁 {}", parent)).monospace(),
                                    |ui| {
                                        if let serde_json::Value::Array(arr) = children {
                                            for child in arr {
                                                if let Some(name) = child.as_str() {
                                                    ui.label(
                                                        egui::RichText::new(format!(
                                                            "  📄 {}",
                                                            name
                                                        ))
                                                        .monospace()
                                                        .size(10.0),
                                                    );
                                                }
                                            }
                                        }
                                    },
                                );
                            }
                        }
                    });

                // Visited Files
                ui.add_space(8.0);
                ui.heading(egui::RichText::new("Visited Files").size(14.0));
                ui.separator();
                egui::ScrollArea::vertical()
                    .id_salt("session_visited_files")
                    .max_height(150.0)
                    .show(ui, |ui| {
                        for f in &detail.visited_files {
                            ui.label(egui::RichText::new(f).monospace().size(10.0));
                        }
                    });
            });
        });
    }

    fn render_metric_card(
        ui: &mut egui::Ui,
        label: &str,
        value: String,
        detail: String,
        color: egui::Color32,
    ) {
        egui::Frame::group(ui.style())
            .fill(egui::Color32::from_rgba_premultiplied(255, 255, 255, 8))
            .show(ui, |ui| {
                ui.set_min_width(170.0);
                ui.vertical(|ui| {
                    ui.label(
                        egui::RichText::new(label)
                            .color(egui::Color32::GRAY)
                            .size(11.0),
                    );
                    ui.label(egui::RichText::new(value).color(color).strong().size(20.0));
                    ui.label(
                        egui::RichText::new(detail)
                            .color(egui::Color32::GRAY)
                            .size(10.0),
                    );
                });
            });
    }

    fn render_threat_analytics(&mut self, ui: &mut egui::Ui) {
        let total_sessions = self.session_stats.finalized_count;
        let detected_sessions = self.session_stats.detected_count;
        let avg_duration = self.session_stats.average_duration_seconds.unwrap_or(0.0);
        let read_events = self
            .audit_logs
            .iter()
            .filter(|event| event.operation.as_deref() == Some("read"))
            .count();
        let write_events = self
            .audit_logs
            .iter()
            .filter(|event| {
                matches!(
                    event.operation.as_deref(),
                    Some("write") | Some("create") | Some("unlink")
                )
            })
            .count();

        ui.horizontal_wrapped(|ui| {
            Self::render_metric_card(
                ui,
                "Sessions",
                total_sessions.to_string(),
                "all finalized session_evidence rows".to_string(),
                egui::Color32::from_rgb(52, 152, 219),
            );
            Self::render_metric_card(
                ui,
                "Detected",
                format!("{}", detected_sessions),
                if total_sessions == 0 {
                    "no completed sessions yet".to_string()
                } else {
                    format!(
                        "{:.0}% detection rate",
                        (detected_sessions as f64 / total_sessions as f64) * 100.0
                    )
                },
                egui::Color32::from_rgb(231, 76, 60),
            );
            Self::render_metric_card(
                ui,
                "Avg Duration",
                if avg_duration >= 60.0 {
                    format!("{:0.1}m", avg_duration / 60.0)
                } else {
                    format!("{:0.0}s", avg_duration)
                },
                "mean session length".to_string(),
                egui::Color32::from_rgb(46, 204, 113),
            );
            Self::render_metric_card(
                ui,
                "Preview Events",
                self.audit_logs.len().to_string(),
                format!(
                    "newest 1,000 only · {} read / {} write-family",
                    read_events, write_events
                ),
                egui::Color32::from_rgb(241, 196, 15),
            );
        });

        ui.add_space(12.0);
        ui.heading(egui::RichText::new("Live Preview Operation Mix").size(14.0));
        ui.separator();

        let mut operation_counts: BTreeMap<String, usize> = BTreeMap::new();
        for event in &self.audit_logs {
            let key = event.operation.as_deref().unwrap_or("UNKNOWN").to_string();
            *operation_counts.entry(key).or_insert(0) += 1;
        }

        let mut operations: Vec<(String, usize)> = operation_counts.into_iter().collect();
        operations.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

        let available_height = ui.available_height() * 0.45;
        TableBuilder::new(ui)
            .striped(true)
            .resizable(true)
            .min_scrolled_height(available_height)
            .max_scroll_height(available_height)
            .column(Column::initial(160.0).at_least(100.0))
            .column(Column::initial(100.0).at_least(60.0))
            .column(Column::remainder())
            .header(18.0, |mut header| {
                header.col(|ui| {
                    ui.strong("Operation");
                });
                header.col(|ui| {
                    ui.strong("Count");
                });
                header.col(|ui| {
                    ui.strong("Share");
                });
            })
            .body(|body| {
                body.rows(20.0, operations.len(), |mut row| {
                    let (operation, count) = &operations[row.index()];
                    row.col(|ui| {
                        ui.label(egui::RichText::new(operation).monospace().size(11.0));
                    });
                    row.col(|ui| {
                        ui.label(egui::RichText::new(count.to_string()).size(11.0));
                    });
                    row.col(|ui| {
                        let share = if self.audit_logs.is_empty() {
                            0.0
                        } else {
                            (*count as f32 / self.audit_logs.len() as f32) * 100.0
                        };
                        ui.label(egui::RichText::new(format!("{:.1}%", share)).size(11.0));
                    });
                });
            });
    }

    fn render_ai_provenance(&mut self, ui: &mut egui::Ui) {
        ui.heading("AI Artifact Provenance");
        ui.label(
            egui::RichText::new(
                "How generated filesystem artifacts were produced and whether they passed validation."
            )
            .color(egui::Color32::GRAY)
            .size(12.0),
        );
        ui.add_space(8.0);

        let snapshot = match self.provenance_snapshot.clone() {
            Some(snapshot) => snapshot,
            None => {
                ui.centered_and_justified(|ui| {
                    ui.label(
                        egui::RichText::new("Waiting for artifact provenance…")
                            .color(egui::Color32::GRAY)
                            .size(14.0),
                    );
                });
                return;
            }
        };

        let fallback_total = snapshot.fallback_blobs + snapshot.template_blobs;
        let validation_rate = if snapshot.total_blobs > 0 {
            snapshot.validated_blobs as f32 / snapshot.total_blobs as f32
        } else {
            0.0
        };

        ui.columns(4, |columns| {
            let metrics = [
                (
                    "Tracked",
                    snapshot.total_blobs.to_string(),
                    egui::Color32::from_rgb(52, 152, 219),
                ),
                (
                    "Model output",
                    snapshot.llm_blobs.to_string(),
                    egui::Color32::from_rgb(155, 89, 182),
                ),
                (
                    "Validated",
                    snapshot.validated_blobs.to_string(),
                    egui::Color32::from_rgb(46, 204, 113),
                ),
                (
                    "Fallbacks",
                    fallback_total.to_string(),
                    egui::Color32::from_rgb(241, 196, 15),
                ),
            ];
            for (column, (label, value, color)) in columns.iter_mut().zip(metrics) {
                egui::Frame::group(column.style())
                    .inner_margin(egui::Margin::symmetric(12, 9))
                    .show(column, |ui| {
                        ui.label(
                            egui::RichText::new(label)
                                .color(egui::Color32::GRAY)
                                .size(11.0),
                        );
                        ui.label(egui::RichText::new(value).color(color).size(24.0).strong());
                    });
            }
        });

        ui.add_space(8.0);
        ui.horizontal(|ui| {
            ui.label(egui::RichText::new("Validation coverage").strong());
            ui.add(
                egui::ProgressBar::new(validation_rate)
                    .text(format!("{:.0}%", validation_rate * 100.0))
                    .desired_width(180.0),
            );
            ui.separator();
            ui.label(format!(
                "LLM {}  ·  fallback {}  ·  template {}",
                snapshot.llm_blobs, snapshot.fallback_blobs, snapshot.template_blobs
            ));
        });

        if !snapshot.by_file_class.is_empty() {
            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("File classes").strong());
                for (class, count) in &snapshot.by_file_class {
                    egui::Frame::group(ui.style())
                        .inner_margin(egui::Margin::symmetric(7, 3))
                        .show(ui, |ui| {
                            ui.label(format!("{}  {}", class.replace('_', " "), count));
                        });
                }
            });
        }

        ui.add_space(12.0);
        ui.horizontal(|ui| {
            ui.heading(egui::RichText::new("Recent artifacts").size(15.0));
            ui.label(
                egui::RichText::new("Select a row for full provenance")
                    .color(egui::Color32::GRAY)
                    .size(11.0),
            );
        });
        ui.separator();

        let mut selected = self.selected_provenance_entry;
        let table_height = (ui.available_height() * 0.55).clamp(150.0, 330.0);
        TableBuilder::new(ui)
            .striped(true)
            .resizable(true)
            .min_scrolled_height(table_height)
            .max_scroll_height(table_height)
            .column(Column::initial(90.0).at_least(72.0))
            .column(Column::initial(130.0).at_least(90.0))
            .column(Column::initial(140.0).at_least(90.0))
            .column(Column::initial(92.0).at_least(72.0))
            .column(Column::remainder())
            .header(24.0, |mut header| {
                header.col(|ui| {
                    ui.strong("Artifact");
                });
                header.col(|ui| {
                    ui.strong("Model");
                });
                header.col(|ui| {
                    ui.strong("File class");
                });
                header.col(|ui| {
                    ui.strong("Source");
                });
                header.col(|ui| {
                    ui.strong("Status");
                });
            })
            .body(|body| {
                body.rows(26.0, snapshot.recent_entries.len(), |mut row| {
                    let index = row.index();
                    let entry = &snapshot.recent_entries[index];
                    let mut open_details = false;
                    row.set_selected(selected == Some(index));
                    row.col(|ui| {
                        open_details = ui
                            .link(
                                egui::RichText::new(
                                    entry.blob_hash.chars().take(8).collect::<String>(),
                                )
                                .monospace(),
                            )
                            .on_hover_text("Open artifact provenance details")
                            .clicked();
                    });
                    row.col(|ui| {
                        ui.label(&entry.model);
                    });
                    row.col(|ui| {
                        ui.label(entry.file_class.replace('_', " "));
                    });
                    row.col(|ui| {
                        let color = match entry.generation_source.as_str() {
                            "llm" => egui::Color32::from_rgb(46, 204, 113),
                            "fallback" => egui::Color32::from_rgb(231, 76, 60),
                            "template" => egui::Color32::from_rgb(241, 196, 15),
                            "world" => egui::Color32::from_rgb(52, 152, 219),
                            _ => egui::Color32::GRAY,
                        };
                        ui.label(
                            egui::RichText::new(entry.generation_source.to_uppercase())
                                .color(color)
                                .strong()
                                .size(10.0),
                        );
                    });
                    row.col(|ui| {
                        let (label, color) = if entry.validated {
                            ("Validated", egui::Color32::from_rgb(46, 204, 113))
                        } else {
                            ("Not validated", egui::Color32::from_rgb(241, 196, 15))
                        };
                        ui.label(egui::RichText::new(label).color(color));
                    });
                    if open_details || row.response().clicked() {
                        selected = Some(index);
                    }
                });
            });
        self.selected_provenance_entry =
            selected.filter(|index| *index < snapshot.recent_entries.len());

        if let Some(index) = self.selected_provenance_entry {
            let entry = &snapshot.recent_entries[index];
            ui.add_space(10.0);
            egui::Frame::group(ui.style())
                .inner_margin(egui::Margin::same(12))
                .show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.heading(egui::RichText::new("Artifact details").size(14.0));
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            if ui.small_button("Close").clicked() {
                                self.selected_provenance_entry = None;
                            }
                        });
                    });
                    egui::Grid::new("provenance_details")
                        .num_columns(2)
                        .spacing([18.0, 5.0])
                        .show(ui, |ui| {
                            ui.strong("Blob hash");
                            ui.monospace(&entry.blob_hash);
                            ui.end_row();
                            ui.strong("Model");
                            ui.label(&entry.model);
                            ui.end_row();
                            ui.strong("Model digest");
                            if entry.model_digest.is_empty() {
                                ui.label("not recorded (legacy artifact)");
                            } else {
                                ui.monospace(&entry.model_digest);
                            }
                            ui.end_row();
                            ui.strong("File class");
                            ui.label(entry.file_class.replace('_', " "));
                            ui.end_row();
                            ui.strong("Generation source");
                            ui.label(&entry.generation_source);
                            ui.end_row();
                            ui.strong("Validation");
                            ui.label(if entry.validated {
                                "Passed"
                            } else {
                                "Not validated"
                            });
                            ui.end_row();
                            ui.strong("Prompt version");
                            ui.label(&entry.prompt_version);
                            ui.end_row();
                            ui.strong("Generated");
                            ui.label(&entry.generated_at);
                            ui.end_row();
                        });
                });
        } else if snapshot.recent_entries.is_empty() {
            ui.add_space(14.0);
            ui.label(
                egui::RichText::new(
                    "No generated artifacts yet. Read an AI-backed file through SSH to create provenance."
                )
                .color(egui::Color32::GRAY),
            );
        }
    }

    fn render_configuration(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.heading("Runtime Configuration");
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.label(
                    egui::RichText::new("Read-only operational summary")
                        .color(egui::Color32::GRAY)
                        .size(11.0),
                );
            });
        });
        ui.separator();

        let redis_host = std::env::var("REDIS_HOST").unwrap_or_else(|_| "localhost".to_string());
        let postgres_host =
            std::env::var("POSTGRES_HOST").unwrap_or_else(|_| "localhost".to_string());
        let postgres_user =
            std::env::var("POSTGRES_USER").unwrap_or_else(|_| "chronos".to_string());
        let inference_mode =
            std::env::var("CHRONOS_INFERENCE_MODE").unwrap_or_else(|_| "deterministic".to_string());
        let artifact_treatment = std::env::var("CHRONOS_ARTIFACT_TREATMENT")
            .unwrap_or_else(|_| "deterministic".to_string());
        let inference_detail = if inference_mode == "ollama" {
            format!(
                "optional local runtime at {}",
                std::env::var("OLLAMA_HOST").unwrap_or_else(|_| "localhost".to_string())
            )
        } else {
            "validated templates; no model dependency".to_string()
        };
        let mount_point =
            std::env::var("CHRONOS_MOUNT_POINT").unwrap_or_else(|_| "/mnt/honeypot".to_string());

        ui.horizontal_wrapped(|ui| {
            Self::render_metric_card(
                ui,
                "FUSE Mount",
                mount_point,
                "filesystem entrypoint".to_string(),
                egui::Color32::from_rgb(52, 152, 219),
            );
            Self::render_metric_card(
                ui,
                "Redis",
                redis_host,
                "state + provenance store".to_string(),
                egui::Color32::from_rgb(46, 204, 113),
            );
            Self::render_metric_card(
                ui,
                "Postgres",
                format!("{}@{}", postgres_user, postgres_host),
                "audit + session evidence".to_string(),
                egui::Color32::from_rgb(241, 196, 15),
            );
            Self::render_metric_card(
                ui,
                "Generation mode",
                inference_mode,
                inference_detail,
                egui::Color32::from_rgb(155, 89, 182),
            );
            Self::render_metric_card(
                ui,
                "Artifact treatment",
                artifact_treatment,
                "explicit deterministic or prepared baseline".to_string(),
                egui::Color32::from_rgb(52, 73, 94),
            );
        });

        ui.add_space(12.0);
        ui.heading(egui::RichText::new("Live Feature Matrix").size(14.0));
        ui.separator();

        let features = [
            ("SSH shell", "local dispatcher on the mounted honeypot root"),
            (
                "Generation",
                "deterministic baseline or optional bounded Ollama",
            ),
            ("Circuit breaker", "per-model degrade and backoff"),
            (
                "Entropy / aging",
                "runtime drift for logs, caches, and timestamps",
            ),
            ("Provenance", "Redis blob metadata snapshot"),
            ("Evidence", "session_evidence + audit_log persistence"),
        ];

        egui::Grid::new("feature_matrix")
            .striped(true)
            .num_columns(2)
            .show(ui, |ui| {
                for (name, description) in features {
                    ui.label(egui::RichText::new(name).strong().size(11.0));
                    ui.label(egui::RichText::new(description).size(11.0));
                    ui.end_row();
                }
            });
    }
}

// ── Main render loop ────────────────────────────────────────────────────────

impl eframe::App for ChronosDashboard {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        self.update_state();
        self.render_top_bar(ui);

        egui::CentralPanel::default().show(ui, |ui| match self.active_tab {
            Tab::LiveOps => self.render_live_ops(ui),
            Tab::Sessions => self.render_sessions(ui),
            Tab::SessionDetail => self.render_session_detail(ui),
            Tab::ThreatAnalytics => self.render_threat_analytics(ui),
            Tab::AIProvenance => self.render_ai_provenance(ui),
            Tab::Configuration => self.render_configuration(ui),
        });

        ui.ctx()
            .request_repaint_after(std::time::Duration::from_millis(100));
    }
}
