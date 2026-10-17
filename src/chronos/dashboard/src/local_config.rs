//! Private first-run credentials for the GUI-owned local deployment.
use serde::{Deserialize, Serialize};
use std::io::{Read, Write};
#[cfg(unix)]
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};

#[derive(Serialize, Deserialize, PartialEq)]
struct Credentials {
    postgres: String,
    grafana: String,
}

pub fn project_root() -> Result<PathBuf, String> {
    std::env::var_os("CHRONOS_PROJECT_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.."))
        .canonicalize()
        .map_err(|_| "Project directory is unavailable".into())
}

#[cfg(unix)]
fn random_secret() -> Result<String, String> {
    let mut bytes = [0u8; 32];
    std::fs::File::open("/dev/urandom")
        .and_then(|mut f| f.read_exact(&mut bytes))
        .map_err(|_| "Operating-system randomness unavailable")?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

#[cfg(unix)]
fn load_or_create(
    root: &Path,
    postgres: Option<String>,
    grafana: Option<String>,
) -> Result<Credentials, String> {
    let folder = root.join(".local-deploy");
    if !folder.exists() {
        let mut builder = std::fs::DirBuilder::new();
        builder.mode(0o700);
        match builder.create(&folder) {
            Ok(()) => {}
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {}
            Err(_) => return Err("Cannot create private configuration directory".into()),
        }
    }
    let metadata =
        std::fs::symlink_metadata(&folder).map_err(|_| "Cannot inspect configuration directory")?;
    if !metadata.is_dir() || metadata.file_type().is_symlink() {
        return Err("Configuration directory must be a real directory".into());
    }
    // Never silently change permissions on an existing operator directory.
    // Files are independently private even if an older supervisor made 0755.
    let path = folder.join("gui-credentials.json");
    if path.exists() {
        let metadata =
            std::fs::symlink_metadata(&path).map_err(|_| "Cannot inspect credentials")?;
        if !metadata.is_file()
            || metadata.file_type().is_symlink()
            || metadata.permissions().mode() & 0o077 != 0
        {
            return Err("Credentials must be a private regular file (mode 0600)".into());
        }
        let bytes = std::fs::read(&path).map_err(|_| "Cannot read local credentials")?;
        let saved: Credentials = serde_json::from_slice(&bytes).map_err(|_| "Local credential file is incomplete or invalid; do not reset it while retaining database volumes")?;
        if saved.postgres.is_empty() || saved.grafana.is_empty() {
            return Err("Local credentials are empty".into());
        }
        if postgres.as_ref().is_some_and(|v| v != &saved.postgres)
            || grafana.as_ref().is_some_and(|v| v != &saved.grafana)
        {
            return Err("Environment credentials differ from the saved managed deployment; use connect-only mode for another stack".into());
        }
        return Ok(saved);
    }
    let saved = Credentials {
        postgres: match postgres {
            Some(value) => value,
            None => random_secret()?,
        },
        grafana: match grafana {
            Some(value) => value,
            None => random_secret()?,
        },
    };
    if saved.postgres.is_empty() || saved.grafana.is_empty() {
        return Err("Credentials must not be empty".into());
    }
    let bytes = serde_json::to_vec(&saved).map_err(|_| "Cannot encode credentials")?;
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .map_err(|_| "Cannot create credentials; another launch may be initializing")?;
    file.write_all(&bytes)
        .and_then(|_| file.sync_all())
        .map_err(|_| "Cannot persist credentials")?;
    Ok(saved)
}

/// Called once, on the main thread before any application threads start.
#[cfg(unix)]
pub fn prepare() -> Result<(), String> {
    if std::env::var("CHRONOS_MANAGE_STACK").as_deref() == Ok("0") {
        return Ok(());
    }
    let root = project_root()?;
    if !root.join("docker-compose.yml").is_file() {
        return Err("Project has no Compose definition".into());
    }
    let saved = load_or_create(
        &root,
        std::env::var("POSTGRES_PASSWORD").ok(),
        std::env::var("GRAFANA_PASSWORD").ok(),
    )?;
    std::env::set_var("POSTGRES_PASSWORD", saved.postgres);
    std::env::set_var("GRAFANA_PASSWORD", saved.grafana);
    // Managed mode always targets its own local mapped services, never an
    // unrelated database selected by inherited shell configuration.
    std::env::set_var("POSTGRES_HOST", "127.0.0.1");
    std::env::set_var("POSTGRES_PORT", "15433");
    std::env::set_var("POSTGRES_USER", "chronos");
    std::env::set_var("POSTGRES_DB", "chronos");
    std::env::set_var("REDIS_URL", "redis://127.0.0.1:16379/");
    Ok(())
}

#[cfg(not(unix))]
pub fn prepare() -> Result<(), String> {
    Err("Managed deployment currently requires Linux or macOS with Docker Desktop".into())
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    #[test]
    fn private_credentials_are_reused_and_never_silently_rotated() {
        let root =
            std::env::temp_dir().join(format!("chronos-config-{}", random_secret().unwrap()));
        std::fs::create_dir(&root).unwrap();
        let first = load_or_create(&root, None, None).unwrap();
        assert_eq!(first.postgres.len(), 64);
        assert!(first.postgres != first.grafana);
        let second = load_or_create(&root, None, None).unwrap();
        assert!(first == second);
        assert!(load_or_create(&root, Some("different".into()), None).is_err());
        let path = root.join(".local-deploy/gui-credentials.json");
        assert_eq!(
            std::fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o644)).unwrap();
        assert!(load_or_create(&root, None, None).is_err());
        std::fs::remove_file(path).unwrap();
        std::fs::remove_dir(root.join(".local-deploy")).unwrap();
        std::fs::remove_dir(root).unwrap();
    }
}
