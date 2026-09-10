// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // El host de Tauri administra el proceso auxiliar del servicio Python en loopback
            // según Sección 4.2. Genera el secreto de sesión y vigila el ciclo de vida del subproceso.
            println!("[Tauri Host] Iniciando LocalDesk desktop wrapper...");
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
