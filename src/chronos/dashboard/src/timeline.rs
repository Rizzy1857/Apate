use crate::backend::{CommandEntry, SessionDetail};
use chrono::{DateTime, NaiveDateTime};
use eframe::egui;

#[derive(Default)]
pub struct TimelineView {
    search: String,
    flagged_only: bool,
    selected: Option<usize>,
}

fn timestamp(command: &CommandEntry) -> Option<NaiveDateTime> {
    let value = command.timestamp.as_deref()?;
    DateTime::parse_from_rfc3339(value)
        .map(|date| date.naive_utc())
        .ok()
        .or_else(|| NaiveDateTime::parse_from_str(value, "%Y-%m-%dT%H:%M:%S%.f").ok())
        .or_else(|| NaiveDateTime::parse_from_str(value, "%Y-%m-%d %H:%M:%S%.f").ok())
}

fn flagged(command: &CommandEntry) -> bool {
    command.risk_score.is_some_and(|score| score > 0)
        || command
            .signatures
            .as_ref()
            .is_some_and(|items| !items.is_empty())
}

fn matching_indices(commands: &[CommandEntry], search: &str, flagged_only: bool) -> Vec<usize> {
    let query = search.trim().to_lowercase();
    let mut indices: Vec<_> = commands
        .iter()
        .enumerate()
        .filter(|(_, command)| {
            (!flagged_only || flagged(command))
                && (query.is_empty()
                    || command
                        .command
                        .as_deref()
                        .unwrap_or("")
                        .to_lowercase()
                        .contains(&query)
                    || command
                        .techniques
                        .iter()
                        .flatten()
                        .chain(command.signatures.iter().flatten())
                        .any(|label| label.to_lowercase().contains(&query)))
        })
        .map(|(index, _)| index)
        .collect();
    // Stable ordering preserves collection order for ties; undated legacy entries follow.
    indices.sort_by_key(|&index| {
        (
            timestamp(&commands[index]).is_none(),
            timestamp(&commands[index]),
        )
    });
    indices
}

fn action_color(command: &CommandEntry) -> egui::Color32 {
    if flagged(command) {
        egui::Color32::from_rgb(245, 185, 95)
    } else {
        egui::Color32::from_rgb(100, 205, 230)
    }
}

fn detail_field(ui: &mut egui::Ui, label: &str, value: &str) {
    ui.horizontal_top(|ui| {
        ui.add_sized(
            [100.0, 18.0],
            egui::Label::new(egui::RichText::new(label).weak()),
        );
        ui.add(egui::Label::new(value).wrap());
    });
}

impl TimelineView {
    fn render_activity(&mut self, ui: &mut egui::Ui, detail: &SessionDetail, indices: &[usize]) {
        ui.add_space(12.0);
        ui.heading("Action activity graph");
        ui.weak("Time →  ·  Rule score ↑  ·  Click a point to inspect an action. Amber = flagged; cyan = other recorded action.");
        let points: Vec<_> = indices
            .iter()
            .filter_map(|&index| timestamp(&detail.commands[index]).map(|time| (index, time)))
            .collect();
        if points.is_empty() {
            ui.label("No valid timestamps available for the time graph. Actions remain available in the sequence diagram.");
            return;
        }
        let first = points[0].1;
        let last = points[points.len() - 1].1;
        let span = (last - first).num_milliseconds().max(1) as f64;
        let max_score = points
            .iter()
            .filter_map(|&(i, _)| detail.commands[i].risk_score)
            .max()
            .unwrap_or(0)
            .max(1) as f64;
        let (response, painter) = ui.allocate_painter(
            egui::vec2(ui.available_width(), 230.0),
            egui::Sense::hover(),
        );
        let rect = response.rect;
        let plot = egui::Rect::from_min_max(
            rect.min + egui::vec2(48.0, 12.0),
            rect.max - egui::vec2(18.0, 48.0),
        );
        let muted = egui::Color32::from_rgb(143, 161, 183);
        for step in 0..=4 {
            let y = egui::lerp(plot.bottom()..=plot.top(), step as f32 / 4.0);
            painter.line_segment(
                [egui::pos2(plot.left(), y), egui::pos2(plot.right(), y)],
                egui::Stroke::new(1.0, egui::Color32::from_rgb(45, 58, 74)),
            );
            painter.text(
                egui::pos2(plot.left() - 8.0, y),
                egui::Align2::RIGHT_CENTER,
                format!("{:.1}", max_score * step as f64 / 4.0),
                egui::FontId::proportional(11.0),
                muted,
            );
        }
        for step in 0..=4 {
            let x = egui::lerp(plot.left()..=plot.right(), step as f32 / 4.0);
            painter.text(
                egui::pos2(x, plot.bottom() + 26.0),
                egui::Align2::CENTER_TOP,
                format!("+{:.1}s", span * step as f64 / 4000.0),
                egui::FontId::proportional(11.0),
                muted,
            );
        }
        for &(index, time) in &points {
            let command = &detail.commands[index];
            let x = egui::lerp(
                plot.left()..=plot.right(),
                ((time - first).num_milliseconds() as f64 / span) as f32,
            );
            let y = command
                .risk_score
                .map(|score| {
                    egui::lerp(
                        plot.bottom()..=plot.top(),
                        (score.max(0) as f64 / max_score) as f32,
                    )
                })
                .unwrap_or(plot.bottom() + 12.0);
            let point = egui::pos2(x, y);
            let color = action_color(command);
            painter.line_segment(
                [egui::pos2(x, plot.bottom()), point],
                egui::Stroke::new(1.0, color.gamma_multiply(0.4)),
            );
            painter.circle_filled(
                point,
                if self.selected == Some(index) {
                    7.0
                } else {
                    4.5
                },
                color,
            );
            let hit = ui.interact(
                egui::Rect::from_center_size(point, egui::vec2(14.0, 14.0)),
                ui.id().with(("action_point", index)),
                egui::Sense::click(),
            );
            if hit.clicked() {
                self.selected = Some(index);
            }
            hit.on_hover_text(format!(
                "Record {} · {} UTC\n{}\nRule score: {}",
                index + 1,
                time,
                command.command.as_deref().unwrap_or("Unknown command"),
                command
                    .risk_score
                    .map(|v| v.to_string())
                    .unwrap_or_else(|| "Not recorded".into())
            ));
        }
        ui.small(format!("Origin: {first} UTC · {} undated actions omitted · missing scores appear below the baseline. Overlapping points can be selected individually in the sequence below.", indices.len() - points.len()));
    }

    fn render_sequence(&mut self, ui: &mut egui::Ui, detail: &SessionDetail, indices: &[usize]) {
        ui.add_space(12.0);
        ui.heading("Attacker action sequence");
        ui.weak("Arrows show recorded order, not causation. Scroll horizontally and select a node to inspect it. Undated actions follow dated actions.");
        egui::ScrollArea::horizontal()
            .id_salt(("action_sequence", &detail.session_id))
            .show(ui, |ui| {
                let (response, painter) = ui.allocate_painter(
                    egui::vec2(indices.len() as f32 * 200.0, 112.0),
                    egui::Sense::hover(),
                );
                let origin = response.rect.min;
                let visible = ui.clip_rect();
                for (position, &index) in indices.iter().enumerate() {
                    let node = egui::Rect::from_min_size(
                        origin + egui::vec2(position as f32 * 200.0, 8.0),
                        egui::vec2(170.0, 88.0),
                    );
                    if !visible.intersects(node.expand(30.0)) {
                        continue;
                    }
                    let command = &detail.commands[index];
                    let color = action_color(command);
                    if position + 1 < indices.len() {
                        painter.arrow(
                            node.right_center(),
                            egui::vec2(28.0, 0.0),
                            egui::Stroke::new(1.5, color),
                        );
                    }
                    painter.rect_filled(
                        node,
                        8.0,
                        if self.selected == Some(index) {
                            egui::Color32::from_rgb(30, 79, 107)
                        } else {
                            egui::Color32::from_rgb(23, 32, 45)
                        },
                    );
                    painter.rect_stroke(
                        node,
                        8.0,
                        egui::Stroke::new(1.0, color),
                        egui::StrokeKind::Inside,
                    );
                    painter.text(
                        node.min + egui::vec2(10.0, 10.0),
                        egui::Align2::LEFT_TOP,
                        format!(
                            "{} · {}",
                            index + 1,
                            if flagged(command) {
                                "FLAGGED"
                            } else {
                                "ACTION"
                            }
                        ),
                        egui::FontId::proportional(11.0),
                        color,
                    );
                    let text = command.command.as_deref().unwrap_or("Unknown command");
                    let label: String = text.chars().take(19).collect();
                    painter.text(
                        node.min + egui::vec2(10.0, 34.0),
                        egui::Align2::LEFT_TOP,
                        format!(
                            "{}{}",
                            label,
                            if text.chars().count() > 19 { "…" } else { "" }
                        ),
                        egui::FontId::monospace(12.0),
                        egui::Color32::WHITE,
                    );
                    painter.text(
                        node.min + egui::vec2(10.0, 62.0),
                        egui::Align2::LEFT_TOP,
                        timestamp(command)
                            .map(|t| t.format("%H:%M:%S UTC").to_string())
                            .unwrap_or_else(|| "Time unavailable".into()),
                        egui::FontId::proportional(11.0),
                        egui::Color32::GRAY,
                    );
                    let hit = ui.interact(
                        node,
                        ui.id().with(("action_node", index)),
                        egui::Sense::click(),
                    );
                    if hit.clicked() {
                        self.selected = Some(index);
                    }
                    hit.on_hover_text(text);
                }
            });
    }

    pub fn show(&mut self, ui: &mut egui::Ui, detail: &SessionDetail) {
        ui.heading("Attacker action timeline");
        ui.label(egui::RichText::new("Recorded SSH commands, oldest first · timestamps in UTC · rule flags are observations, not intent").weak());
        ui.horizontal_wrapped(|ui| {
            ui.add(
                egui::TextEdit::singleline(&mut self.search)
                    .hint_text("Search commands, techniques or signatures…")
                    .desired_width(300.0),
            );
            ui.checkbox(&mut self.flagged_only, "Flagged actions only");
            if ui.button("Clear filters").clicked() {
                self.search.clear();
                self.flagged_only = false;
            }
        });
        let indices = matching_indices(&detail.commands, &self.search, self.flagged_only);
        ui.horizontal_wrapped(|ui| {
            ui.strong(format!(
                "{} of {} actions",
                indices.len(),
                detail.commands.len()
            ));
            ui.label(format!(
                "{} flagged",
                detail.commands.iter().filter(|c| flagged(c)).count()
            ));
            ui.label(format!(
                "Started: {}",
                detail
                    .start_time
                    .map(|t| t.to_string())
                    .unwrap_or_else(|| "Unknown".into())
            ));
            ui.label(format!(
                "Ended: {}",
                detail
                    .end_time
                    .map(|t| t.to_string())
                    .unwrap_or_else(|| "Not recorded".into())
            ));
        });
        if indices.is_empty() {
            ui.label(if detail.commands.is_empty() {
                "No attacker commands were recorded for this session."
            } else {
                "No actions match these filters. Clear filters to see the full timeline."
            });
            return;
        }
        if !self.selected.is_some_and(|index| indices.contains(&index)) {
            self.selected = indices.first().copied();
        }
        self.render_activity(ui, detail, &indices);
        self.render_sequence(ui, detail, &indices);
        ui.add_space(8.0);
        ui.heading("Selected action");
        if let Some(index) = self.selected {
            let command = &detail.commands[index];
            let color = if flagged(command) {
                egui::Color32::from_rgb(245, 185, 95)
            } else {
                egui::Color32::from_rgb(100, 205, 230)
            };
            egui::Frame::group(ui.style())
                .fill(egui::Color32::from_rgb(23, 32, 45))
                .inner_margin(12.0)
                .show(ui, |ui| {
                    ui.set_width(ui.available_width());
                    ui.horizontal_wrapped(|ui| {
                        ui.colored_label(
                            color,
                            if flagged(command) {
                                "● FLAGGED"
                            } else {
                                "● ACTION"
                            },
                        );
                        ui.weak(format!("Record {}", index + 1));
                        let time = timestamp(command);
                        ui.monospace(
                            time.map(|t| t.to_string())
                                .unwrap_or_else(|| "Timestamp unavailable".into()),
                        );
                        if let (Some(time), Some(start)) = (time, detail.start_time) {
                            ui.weak(format!(
                                "{:+.3}s from start",
                                (time - start).num_milliseconds() as f64 / 1000.0
                            ));
                        }
                    });
                    ui.add(
                        egui::Label::new(
                            egui::RichText::new(
                                command
                                    .command
                                    .as_deref()
                                    .unwrap_or("Command text unavailable"),
                            )
                            .monospace()
                            .size(14.0),
                        )
                        .wrap(),
                    );
                    ui.separator();
                    detail_field(
                        ui,
                        "Outcome",
                        command
                            .outcome
                            .as_deref()
                            .unwrap_or("Unknown (legacy record)"),
                    );
                    detail_field(
                        ui,
                        "Exit status",
                        &command
                            .exit_status
                            .map(|v| v.to_string())
                            .unwrap_or_else(|| "Not recorded".into()),
                    );
                    detail_field(
                        ui,
                        "Rule score",
                        &command
                            .risk_score
                            .map(|v| v.to_string())
                            .unwrap_or_else(|| "Not recorded".into()),
                    );
                    detail_field(
                        ui,
                        "Techniques",
                        &command
                            .techniques
                            .as_ref()
                            .filter(|v| !v.is_empty())
                            .map(|v| v.join(", "))
                            .unwrap_or_else(|| "None recorded".into()),
                    );
                    detail_field(
                        ui,
                        "Command ID",
                        command.command_id.as_deref().unwrap_or("Not recorded"),
                    );
                    detail_field(
                        ui,
                        "Claimed user",
                        command
                            .claimed_username
                            .as_deref()
                            .unwrap_or("Not recorded"),
                    );
                    detail_field(
                        ui,
                        "Effective user",
                        command
                            .effective_username
                            .as_deref()
                            .unwrap_or("Not recorded"),
                    );
                    detail_field(
                        ui,
                        "Server elapsed",
                        &command
                            .server_elapsed_seconds
                            .map(|v| format!("{v:.3}s"))
                            .unwrap_or_else(|| "Not recorded".into()),
                    );
                    detail_field(
                        ui,
                        "Response size",
                        &command
                            .response_bytes
                            .map(|v| format!("{v} bytes"))
                            .unwrap_or_else(|| "Not recorded".into()),
                    );
                    detail_field(
                        ui,
                        "Signatures",
                        &command
                            .signatures
                            .as_ref()
                            .filter(|v| !v.is_empty())
                            .map(|v| v.join(", "))
                            .unwrap_or_else(|| "None recorded".into()),
                    );
                });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn command(value: serde_json::Value) -> CommandEntry {
        serde_json::from_value(value).unwrap()
    }

    #[test]
    fn graphs_render_empty_legacy_and_filtered_sessions_at_multiple_widths() {
        let mut detail = SessionDetail {
            session_id: "test-session".into(),
            start_time: None,
            end_time: None,
            duration_seconds: None,
            detection_status: None,
            detection_confidence: None,
            exit_reason: None,
            first_suspicious_command: None,
            commands: vec![],
            visited_files: vec![],
            traversal_graph: serde_json::json!({}),
            pattern_assessment: None,
        };
        for width in [400.0, 800.0, 1200.0] {
            let context = egui::Context::default();
            let mut view = TimelineView::default();
            for variant in 0..4 {
                detail.commands = match variant {
                    0 => vec![],
                    1 => vec![command(serde_json::json!({"command":"id"}))],
                    _ => vec![
                        command(
                            serde_json::json!({"command":"id", "timestamp":"2026-10-30T10:00:00Z", "risk_score":0}),
                        ),
                        command(
                            serde_json::json!({"command":"cat /etc/passwd", "timestamp":"2026-10-30T10:00:00Z", "risk_score":50}),
                        ),
                    ],
                };
                if variant == 2 {
                    detail.commands = (0..48).map(|index| command(serde_json::json!({
                        "command": format!("cat /var/www/application/configuration/long-directory-{index}/settings.conf"),
                        "timestamp": format!("2026-10-30T10:00:{index:02}Z"),
                        "risk_score": index,
                        "outcome": "unknown (legacy record)",
                        "command_id": "91129fb4-3d50-42fc-856b-b8e66fd221c0"
                    }))).collect();
                }
                view.flagged_only = variant == 3;
                let mut output = context.run_ui(
                    egui::RawInput {
                        screen_rect: Some(egui::Rect::from_min_size(
                            egui::Pos2::ZERO,
                            egui::vec2(width, 1000.0),
                        )),
                        ..Default::default()
                    },
                    |ui| {
                        egui::CentralPanel::default().show(ui, |ui| {
                            let available = ui.available_width();
                            let area = egui::ScrollArea::vertical().show(ui, |ui| {
                                view.show(ui, &detail);
                            });
                            assert!(area.content_size.x <= available + 1.0,
                                "width {width}, variant {variant}: content {} exceeds viewport {available}", area.content_size.x);
                        });
                    },
                );
                output.textures_delta.clear();
                assert!(!output.shapes.is_empty());
                if variant == 3 {
                    assert_eq!(view.selected, Some(1));
                }
                for shape in output.shapes {
                    assert!(shape.clip_rect.is_finite());
                }
            }
        }
    }

    #[test]
    fn timeline_orders_offsets_ties_and_missing_timestamps() {
        let commands = vec![
            command(serde_json::json!({"timestamp":"2026-10-30T12:00:00+02:00"})),
            command(serde_json::json!({"timestamp":"invalid"})),
            command(serde_json::json!({"timestamp":"2026-10-30 09:00:00"})),
            command(serde_json::json!({"timestamp":"2026-10-30T10:00:00Z"})),
        ];
        assert_eq!(matching_indices(&commands, "", false), vec![2, 0, 3, 1]);
    }

    #[test]
    fn filters_include_signatures_without_assuming_legacy_risk() {
        let commands = vec![
            command(serde_json::json!({"command":"id"})),
            command(serde_json::json!({"command":"cat /etc/passwd", "signatures":["SIG-1"]})),
            command(
                serde_json::json!({"command":"whoami", "risk_score":10, "techniques":["Discovery"]}),
            ),
        ];
        assert_eq!(matching_indices(&commands, "", true), vec![1, 2]);
        assert_eq!(matching_indices(&commands, " SIG-1 ", true), vec![1]);
        assert_eq!(matching_indices(&commands, "DISCOVERY", false), vec![2]);
        assert!(matching_indices(&commands, "missing", false).is_empty());
    }
}
