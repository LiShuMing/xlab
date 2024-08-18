#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;

#[tauri::command]
async fn get_app_version(app: tauri::Window) -> Result<String, String> {
    let info = app.package_info();
    Ok(format!("{}", info.version))
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_app_version])
        .setup(|app| {
            #[cfg(target_os = "macos")]
            {
                app.set_activation_policy(tauri::ActivationPolicy::Regular);
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
