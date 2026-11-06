#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod runtime;

use std::{path::PathBuf, sync::Mutex, time::{Duration, Instant}};
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

fn main() {
    if let Err(error) = run() {
        eprintln!("Rust prototype: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let started = Instant::now();
    let mut source = None;
    let mut backend = None;
    let mut exit_after = None;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        let value = args.next().ok_or("Every argument requires a value")?;
        match arg.as_str() {
            "--source-root" => source = Some(PathBuf::from(value)),
            "--backend" => backend = Some(PathBuf::from(value)),
            "--exit-after-ms" => exit_after = Some(value.parse::<u64>()?),
            _ => return Err(format!("Unknown argument: {arg}").into()),
        }
    }
    runtime::own_process_tree()?;
    let mut runtime = runtime::Runtime::start(source.as_deref(), backend.as_deref())?;
    let root = runtime.root.clone();
    let url = runtime.url();
    println!("PROTOTYPE_ROOT={}", root.display());
    runtime.wait_ready(Duration::from_secs(90))?;
    let health_ms = started.elapsed().as_secs_f64() * 1000.0;
    runtime::write_metrics(&root, &serde_json::json!({
        "backend_health_ms": health_ms,
        "backend_pid": runtime.child.id(),
        "shell_pid": std::process::id(),
        "url": url,
        "backend_mode": if source.is_some() { "source" } else { "packaged" }
    }))?;
    let allowed = url.parse::<tauri::Url>()?;
    let destination = allowed.clone();
    tauri::Builder::default()
        .manage(Mutex::new(runtime))
        .setup(move |app| {
            let metrics_root = root.clone();
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(destination))
                .title("Rasputin — Rust Prototype")
                .inner_size(1440.0, 940.0)
                .min_inner_size(1000.0, 680.0)
                .data_directory(root.join("webview"))
                // No IPC commands or remote capabilities. Untrusted links cannot
                // navigate the privileged desktop window to another origin.
                .on_navigation(move |target| target.origin() == allowed.origin())
                .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
                .on_page_load(move |_, event| {
                    if event.event() == tauri::webview::PageLoadEvent::Finished {
                        let _ = runtime::write_metrics(&metrics_root, &serde_json::json!({
                            "backend_health_ms": health_ms,
                            "navigation_finished_ms": started.elapsed().as_secs_f64() * 1000.0,
                            "shell_pid": std::process::id(),
                            "url": event.url().as_str(),
                            "note": "Navigation finished is not React/application readiness"
                        }));
                    }
                })
                .build()?;
            if let Some(milliseconds) = exit_after {
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(Duration::from_millis(milliseconds));
                    handle.exit(0);
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!())?
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                // Stop only the backend created by this process. Job teardown
                // also covers crashes and any descendant model processes.
                if let Some(state) = app.try_state::<Mutex<runtime::Runtime>>() {
                    if let Ok(mut runtime) = state.lock() {
                        let _ = runtime.child.kill();
                        let _ = runtime.child.wait();
                        let _ = std::fs::remove_file(runtime.root.join("desktop-runtime.json"));
                    }
                }
            }
        });
    Ok(())
}
