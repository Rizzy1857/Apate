mod app;
mod backend;
mod lifecycle;
mod local_config;
mod managed_export;

use app::ChronosDashboard;
use eframe::egui;

fn main() -> eframe::Result<()> {
    env_logger::init();
    let configuration = local_config::prepare();

    // Backend → UI message channel
    let (tx, rx) = flume::bounded(32);

    // UI → Backend request channel
    let (tx_req, rx_req) = flume::bounded(32);

    let (shutdown_tx, shutdown_rx) = std::sync::mpsc::channel::<()>();
    let cancelled = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    let worker_cancelled = cancelled.clone();
    // Lifecycle runs outside the UI and only owns the stack it created.
    let worker = std::thread::spawn(move || {
        if let Err(error) = configuration {
            let _ = tx.send(backend::BackendMessage::StackStatus(error));
            return;
        }
        let managed = match lifecycle::ManagedStack::start(&tx, &worker_cancelled) {
            Ok(stack) => stack,
            Err(error) => {
                let _ = tx.send(backend::BackendMessage::StackStatus(error));
                return;
            }
        };
        let rt = tokio::runtime::Runtime::new().expect("Failed to create Tokio runtime");
        rt.block_on(async {
            backend::start_backend(tx, rx_req).await;
        });
        let _ = shutdown_rx.recv();
        if let Some(stack) = managed {
            stack.stop();
        }
    });
    let worker = std::sync::Arc::new(std::sync::Mutex::new(Some(worker)));
    let exit_worker = worker.clone();
    let exit_cancelled = cancelled.clone();
    let exit_tx = shutdown_tx.clone();

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1200.0, 800.0])
            .with_min_inner_size([800.0, 500.0]),
        ..Default::default()
    };

    let result = eframe::run_native(
        "Chronos Overseer",
        options,
        Box::new(move |cc| {
            Ok(Box::new(
                ChronosDashboard::new(cc, rx, tx_req).with_shutdown(move || {
                    exit_cancelled.store(true, std::sync::atomic::Ordering::Relaxed);
                    let _ = exit_tx.send(());
                    if let Some(worker) = exit_worker.lock().unwrap().take() {
                        let _ = worker.join();
                    }
                }),
            ))
        }),
    );
    cancelled.store(true, std::sync::atomic::Ordering::Relaxed);
    let _ = shutdown_tx.send(());
    if let Some(worker) = worker.lock().unwrap().take() {
        let _ = worker.join();
    }
    result
}
