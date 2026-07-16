mod app;
mod backend;

use app::ChronosDashboard;
use eframe::egui;

fn main() -> eframe::Result<()> {
    env_logger::init();

    let (tx, rx) = flume::unbounded();

    // Spawn the tokio runtime in a background thread so it doesn't block the UI thread
    std::thread::spawn(move || {
        let rt = tokio::runtime::Runtime::new().expect("Failed to create Tokio runtime");
        rt.block_on(async {
            backend::start_backend(tx).await;
            std::future::pending::<()>().await;
        });
    });

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1000.0, 700.0])
            .with_min_inner_size([600.0, 400.0]),
        ..Default::default()
    };

    eframe::run_native(
        "Chronos Dashboard",
        options,
        Box::new(|_cc| Ok(Box::new(ChronosDashboard::new(_cc, rx)))),
    )
}
