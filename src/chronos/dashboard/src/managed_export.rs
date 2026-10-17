//! Export with the core's Python runtime and verify before marking completion.
use sha2::{Digest, Sha256};
use std::io::Write;
#[cfg(unix)]
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::io::AsyncReadExt;

fn sha256(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

async fn copy_from_core(directory: &str, stage: &Path) -> Result<(), String> {
    let mut child = tokio::process::Command::new("docker")
        .args(["exec", "mirage-gui-core", "python3", "-c",
            "import sys; from pathlib import Path\nout=sys.stdout.buffer; out.write(b'MIRAGE_EXPORT_V1\\n')\nfor p in sorted(Path(sys.argv[1]).iterdir()):\n if not p.is_file() or p.is_symlink(): raise ValueError('Invalid member')\n name=p.name.encode(); data=p.read_bytes(); out.write(len(name).to_bytes(2,'big')+len(data).to_bytes(8,'big')+name+data)\nout.flush()",
            directory])
        .stdin(std::process::Stdio::null()).stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null()).kill_on_drop(true)
        .spawn().map_err(|_| "Cannot start private export transfer")?;
    let transfer = async {
        let mut bytes = Vec::new();
        child
            .stdout
            .take()
            .ok_or("Export transfer has no output")?
            .take(128 * 1024 * 1024 + 1)
            .read_to_end(&mut bytes)
            .await
            .map_err(|_| "Export transfer failed")?;
        if bytes.len() > 128 * 1024 * 1024 {
            return Err("Export transfer exceeds its byte budget".into());
        }
        if !child
            .wait()
            .await
            .map_err(|_| "Cannot observe export transfer")?
            .success()
        {
            return Err("Core could not stream the export".into());
        }
        unpack_stream(&bytes, stage)
    };
    tokio::time::timeout(Duration::from_secs(30), transfer)
        .await
        .map_err(|_| "Export transfer timed out".to_string())?
}

fn unpack_stream(bytes: &[u8], stage: &Path) -> Result<(), String> {
    let magic = b"MIRAGE_EXPORT_V1\n";
    if !bytes.starts_with(magic) {
        return Err("Invalid export transfer header".into());
    }
    let mut offset = magic.len();
    let mut members = 0;
    while offset < bytes.len() {
        if bytes.len() - offset < 10 {
            return Err("Truncated export member header".into());
        }
        let name_len = u16::from_be_bytes(bytes[offset..offset + 2].try_into().unwrap()) as usize;
        let size = usize::try_from(u64::from_be_bytes(
            bytes[offset + 2..offset + 10].try_into().unwrap(),
        ))
        .map_err(|_| "Invalid export member size")?;
        offset += 10;
        if name_len == 0
            || name_len > 256
            || size > 64 * 1024 * 1024
            || members >= 33
            || name_len + size > bytes.len() - offset
        {
            return Err("Invalid or truncated export member".into());
        }
        let name = std::str::from_utf8(&bytes[offset..offset + name_len])
            .map_err(|_| "Invalid export filename")?;
        let path = Path::new(name);
        if path.components().count() != 1 || path.file_name().and_then(|v| v.to_str()) != Some(name)
        {
            return Err("Export transfer tried to leave its staging directory".into());
        }
        offset += name_len;
        save_new(&stage.join(name), &bytes[offset..offset + size])?;
        offset += size;
        members += 1;
    }
    if members == 0 {
        return Err("Empty export transfer".into());
    }
    Ok(())
}

async fn docker(args: &[&str], seconds: u64) -> Result<(), String> {
    let mut command = tokio::process::Command::new("docker");
    command
        .args(args)
        .kill_on_drop(true)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    match tokio::time::timeout(Duration::from_secs(seconds), command.status()).await {
        Ok(Ok(status)) if status.success() => Ok(()),
        Ok(_) => Err(
            "Managed export failed; check the running core and choose a new output directory"
                .into(),
        ),
        Err(_) => Err("Managed export timed out; partial output is not complete evidence".into()),
    }
}

fn private_dir(path: &Path) -> Result<(), String> {
    let mut builder = std::fs::DirBuilder::new();
    #[cfg(unix)]
    builder.mode(0o700);
    builder
        .create(path)
        .map_err(|_| "Choose a new output directory with an existing writable parent".into())
}

fn save_new(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    options.mode(0o600);
    let mut file = options
        .open(path)
        .map_err(|_| "Cannot create export file without overwriting existing data")?;
    file.write_all(bytes)
        .and_then(|_| file.sync_all())
        .map_err(|_| "Cannot finish export file".into())
}

fn install_bundle(stage: &Path, destination: &Path, mode: &str) -> Result<(), String> {
    let complete = std::fs::read(stage.join("complete.json"))
        .map_err(|_| "Export has no completion marker")?;
    let manifest: serde_json::Value =
        serde_json::from_slice(&complete).map_err(|_| "Invalid export manifest")?;
    if manifest["artifact_type"].as_str() != Some(&format!("{mode}_evidence_bundle")) {
        return Err("Export mode does not match its manifest".into());
    }
    let hashes = manifest["sha256"]
        .as_object()
        .ok_or("Export manifest has no file hashes")?;
    if hashes.is_empty() || hashes.len() > 32 {
        return Err("Invalid export file count".into());
    }
    let mut files = Vec::new();
    let mut total = 0usize;
    for (name, digest) in hashes {
        let path = Path::new(name);
        if path.components().count() != 1
            || path.file_name().and_then(|v| v.to_str()) != Some(name)
            || name == "complete.json"
        {
            return Err("Invalid export member path".into());
        }
        let path = stage.join(path);
        let metadata = std::fs::symlink_metadata(&path).map_err(|_| "Missing export member")?;
        if !metadata.is_file()
            || metadata.file_type().is_symlink()
            || metadata.len() > 64 * 1024 * 1024
        {
            return Err("Invalid or oversized export member".into());
        }
        let bytes = std::fs::read(path).map_err(|_| "Cannot verify export member")?;
        total += bytes.len();
        if total > 128 * 1024 * 1024 {
            return Err("Export exceeds desktop copy budget".into());
        }
        if digest.as_str() != Some(sha256(&bytes).as_str()) {
            return Err("Export file failed SHA-256 verification".into());
        }
        files.push((name, bytes));
    }
    private_dir(destination)?; // Exclusive creation prevents overwriting an existing bundle.
    for (name, bytes) in files {
        save_new(&destination.join(name), &bytes)?;
    }
    save_new(&destination.join("complete.json"), &complete)?; // Always last.
    Ok(())
}

pub async fn export(session: &str, destination: &str, mode: &str) -> Result<String, String> {
    let destination = PathBuf::from(destination);
    if !destination.is_absolute() || destination.exists() || !["raw", "redacted"].contains(&mode) {
        return Err(
            "Choose a new absolute output path; existing directories are never overwritten".into(),
        );
    }
    let parent = destination.parent().ok_or("Output path has no parent")?;
    let nonce = format!(
        "{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| "Clock unavailable")?
            .as_nanos()
    );
    let stage = parent.join(format!(".mirage-export-{nonce}"));
    private_dir(&stage)?;
    let container_dir = format!("/tmp/mirage-export-{nonce}");
    let result = async {
        docker(
            &[
                "exec",
                "--env",
                "POSTGRES_PORT=5432",
                "mirage-gui-core",
                "python3",
                "-m",
                "chronos.watcher.export_report",
                "--session-id",
                session,
                "--output",
                &container_dir,
                "--mode",
                mode,
            ],
            90,
        )
        .await?;
        copy_from_core(&container_dir, &stage).await?;
        install_bundle(&stage, &destination, mode)?;
        Ok(destination.to_string_lossy().into_owned())
    }
    .await;
    // Both targets are generated here, below specific private temporary paths.
    let _ = docker(
        &[
            "exec",
            "mirage-gui-core",
            "python3",
            "-c",
            "import shutil,sys; shutil.rmtree(sys.argv[1], ignore_errors=True)",
            &container_dir,
        ],
        10,
    )
    .await;
    let _ = std::fs::remove_dir_all(&stage);
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn export_copy_verifies_hashes_refuses_overwrite_and_completes_last() {
        let root = std::env::temp_dir().join(format!(
            "mirage-export-test-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        private_dir(&root).unwrap();
        let stage = root.join("stage");
        private_dir(&stage).unwrap();
        let bytes = b"synthetic evidence";
        save_new(&stage.join("events.json"), bytes).unwrap();
        let manifest = serde_json::json!({"artifact_type": "raw_evidence_bundle", "sha256": {
            "events.json": sha256(bytes)}});
        save_new(
            &stage.join("complete.json"),
            &serde_json::to_vec(&manifest).unwrap(),
        )
        .unwrap();
        let destination = root.join("result");
        install_bundle(&stage, &destination, "raw").unwrap();
        assert!(destination.join("complete.json").is_file());
        assert!(install_bundle(&stage, &destination, "raw").is_err());
        std::fs::write(stage.join("events.json"), b"corrupted").unwrap();
        assert!(install_bundle(&stage, &root.join("corrupted"), "raw").is_err());
        assert!(!root.join("corrupted").exists());
        assert!(install_bundle(&stage, &root.join("wrong-mode"), "redacted").is_err());
        let transfer = root.join("transport");
        private_dir(&transfer).unwrap();
        let mut stream = b"MIRAGE_EXPORT_V1\n".to_vec();
        for (name, data) in [
            ("events.json", bytes.to_vec()),
            ("complete.json", serde_json::to_vec(&manifest).unwrap()),
        ] {
            stream.extend((name.len() as u16).to_be_bytes());
            stream.extend((data.len() as u64).to_be_bytes());
            stream.extend(name.as_bytes());
            stream.extend(data);
        }
        unpack_stream(&stream, &transfer).unwrap();
        install_bundle(&transfer, &root.join("stream-result"), "raw").unwrap();
        let mut malicious = b"MIRAGE_EXPORT_V1\n".to_vec();
        malicious.extend(9u16.to_be_bytes());
        malicious.extend(1u64.to_be_bytes());
        malicious.extend(b"../escape");
        malicious.push(0);
        assert!(unpack_stream(&malicious, &transfer).is_err());
        assert!(!root.join("escape").exists());
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                std::fs::metadata(destination.join("events.json"))
                    .unwrap()
                    .permissions()
                    .mode()
                    & 0o777,
                0o600
            );
        }
        std::fs::remove_dir_all(root).unwrap();
    }

    #[tokio::test]
    #[ignore = "Requires GUI-owned core and APATE_EXPORT_TEST_SESSION"]
    async fn actual_core_export_transfer() {
        let session =
            std::env::var("APATE_EXPORT_TEST_SESSION").expect("Set synthetic fixture session UUID");
        let root = std::env::temp_dir().join(format!(
            "mirage-container-export-test-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        private_dir(&root).unwrap();
        let result = root.join("raw");
        export(&session, result.to_str().unwrap(), "raw")
            .await
            .unwrap();
        let record: serde_json::Value =
            serde_json::from_slice(&std::fs::read(result.join("run_record.json")).unwrap())
                .unwrap();
        assert_eq!(record["session_id"].as_str(), Some(session.as_str()));
        assert_eq!(record["reproducibility_metadata_complete"], true);
        std::fs::remove_dir_all(root).unwrap();
    }
}
