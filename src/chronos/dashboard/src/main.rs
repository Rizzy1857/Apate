mod app;
mod backend;

use app::ChronosDashboard;
use eframe::egui;

fn main() -> eframe::Result<()> {
    env_logger::init();

    // Backend → UI message channel
    let (tx, rx) = flume::unbounded();

    // UI → Backend request channel
    let (tx_req, rx_req) = flume::unbounded();

    // Spawn the tokio runtime in a background thread so it doesn't block the UI thread
    std::thread::spawn(move || {
        let rt = tokio::runtime::Runtime::new().expect("Failed to create Tokio runtime");
        rt.block_on(async {
            backend::start_backend(tx, rx_req).await;
            std::future::pending::<()>().await;
        });
    });

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1200.0, 800.0])
            .with_min_inner_size([800.0, 500.0]),
        ..Default::default()
    };

    eframe::run_native(
        "Chronos Overseer",
        options,
        Box::new(|cc| Ok(Box::new(ChronosDashboard::new(cc, rx, tx_req)))),
    )
}
