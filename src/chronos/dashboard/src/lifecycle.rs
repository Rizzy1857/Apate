//! Local Compose lifecycle. Never removes volumes or adopts an existing stack.
use crate::backend::BackendMessage;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

const PROJECT: &str = "chronos-gui";

fn compose(root: &Path) -> Command {
    let mut command = Command::new("docker");
    command
        .args(["compose", "--project-name", PROJECT, "--project-directory"])
        .arg(root)
        .arg("--file")
        .arg(root.join("docker-compose.yml"))
        .arg("--file")
        .arg(root.join("config/compose.gui.yml"));
    command
}

fn run(mut command: Command, timeout: Duration) -> Result<(), String> {
    run_cancellable(&mut command, timeout, None)
}

fn run_cancellable(
    command: &mut Command,
    timeout: Duration,
    cancel: Option<&AtomicBool>,
) -> Result<(), String> {
    // Docker errors may contain interpolated configuration; do not relay them
    // into UI/evidence. Operators can inspect their local Docker logs separately.
    let mut child = command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "Cannot start Docker; check installation and PATH".to_string())?;
    wait_child(&mut child, timeout, cancel)
}

fn wait_child(
    child: &mut Child,
    timeout: Duration,
    cancel: Option<&AtomicBool>,
) -> Result<(), String> {
    let start = Instant::now();
    loop {
        if cancel.is_some_and(|flag| flag.load(Ordering::Relaxed)) {
            let _ = child.kill();
            let _ = child.wait();
            return Err("Startup cancelled".into());
        }
        match child.try_wait() {
            Ok(Some(status)) if status.success() => return Ok(()),
            Ok(Some(_)) => {
                return Err(
                    "Docker operation failed; check Docker and required configuration".into(),
                )
            }
            Err(_) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("Cannot observe Docker operation".into());
            }
            _ => {}
        }
        if start.elapsed() > timeout {
            let _ = child.kill();
            let _ = child.wait();
            return Err("Docker operation timed out".into());
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

pub struct ManagedStack {
    root: PathBuf,
    _lock: std::fs::File,
}

fn capture(
    command: &mut Command,
    timeout: Duration,
    cancel: &AtomicBool,
) -> Result<String, String> {
    let mut child = command
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "Cannot start Docker inspection")?;
    wait_child(&mut child, timeout, Some(cancel))?;
    let mut output = String::new();
    child
        .stdout
        .take()
        .ok_or("Docker inspection has no output")?
        .take(8193)
        .read_to_string(&mut output)
        .map_err(|_| "Invalid Docker inspection output")?;
    if output.len() > 8192 {
        return Err("Docker inspection output exceeds its budget".into());
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compose_is_explicitly_scoped() {
        let command = compose(Path::new("/tmp/research project"));
        let args: Vec<_> = command
            .get_args()
            .map(|s| s.to_string_lossy().into_owned())
            .collect();
        assert_eq!(
            args,
            vec![
                "compose",
                "--project-name",
                "chronos-gui",
                "--project-directory",
                "/tmp/research project",
                "--file",
                "/tmp/research project/docker-compose.yml",
                "--file",
                "/tmp/research project/config/compose.gui.yml"
            ]
        );
    }

    #[test]
    fn nonzero_exit_is_not_ready() {
        let mut command = Command::new("/bin/sh");
        command.args(["-c", "exit 7"]);
        assert!(run(command, Duration::from_secs(2)).is_err());
    }

    #[test]
    fn stalled_child_is_bounded() {
        let mut command = Command::new("/bin/sleep");
        command.arg("10");
        let started = Instant::now();
        assert!(run(command, Duration::from_millis(100)).is_err());
        assert!(started.elapsed() < Duration::from_secs(3));
    }

    #[test]
    fn cancellation_stops_startup_child() {
        let mut command = Command::new("/bin/sleep");
        command.arg("10");
        let cancel = AtomicBool::new(true);
        let started = Instant::now();
        assert_eq!(
            run_cancellable(&mut command, Duration::from_secs(30), Some(&cancel)),
            Err("Startup cancelled".into())
        );
        assert!(started.elapsed() < Duration::from_secs(3));
    }

    #[test]
    fn inspection_output_and_cancellation_are_bounded() {
        let cancel = AtomicBool::new(false);
        assert_eq!(
            capture(
                Command::new("/usr/bin/printf").arg("safe-label"),
                Duration::from_secs(2),
                &cancel
            )
            .unwrap(),
            "safe-label"
        );
        cancel.store(true, Ordering::Relaxed);
        assert!(capture(
            Command::new("/bin/sleep").arg("10"),
            Duration::from_secs(30),
            &cancel
        )
        .is_err());
    }

    #[test]
    fn supervisor_os_lock_is_exclusive_and_recovers_without_file_deletion() {
        let path = std::env::temp_dir().join(format!(
            "mirage-lock-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let first = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)
            .unwrap();
        first.try_lock().unwrap();
        let second = std::fs::OpenOptions::new().write(true).open(&path).unwrap();
        assert!(second.try_lock().is_err());
        drop(first);
        // Parallel process-spawning tests may briefly inherit the first file
        // description between fork and close-on-exec. Recovery is eventual,
        // not guaranteed in the very next instruction after drop.
        let deadline = Instant::now() + Duration::from_secs(2);
        loop {
            match second.try_lock() {
                Ok(()) => break,
                Err(error) => {
                    assert!(Instant::now() < deadline, "Lock did not recover: {error}");
                    std::thread::sleep(Duration::from_millis(10));
                }
            }
        }
        drop(second);
        std::fs::remove_file(path).unwrap();
    }
}

impl ManagedStack {
    pub fn start(
        tx: &flume::Sender<BackendMessage>,
        cancel: &AtomicBool,
    ) -> Result<Option<Self>, String> {
        if cancel.load(Ordering::Relaxed) {
            return Err("Startup cancelled".into());
        }
        if std::env::var("CHRONOS_MANAGE_STACK").as_deref() == Ok("0") {
            let _ = tx.send(BackendMessage::StackStatus(
                "Connect-only mode; services are externally managed".into(),
            ));
            return Ok(None);
        }
        for name in ["POSTGRES_PASSWORD", "GRAFANA_PASSWORD", "REDIS_PASSWORD"] {
            if std::env::var(name).unwrap_or_default().is_empty() {
                return Err(format!("Set {name} before starting the managed stack"));
            }
        }
        let root = std::env::var_os("CHRONOS_PROJECT_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.."));
        let root = root
            .canonicalize()
            .map_err(|_| "Project directory is unavailable")?;
        if !root.join("docker-compose.yml").is_file() {
            return Err("Project has no docker-compose.yml".into());
        }
        let folder = root.join(".local-deploy");
        std::fs::create_dir_all(&folder).map_err(|_| "Cannot create local supervisor directory")?;
        let lock = folder.join("gui.owner");
        let lock = std::fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(false)
            .open(&lock)
            .map_err(|_| "Cannot open supervisor lock")?;
        lock.try_lock()
            .map_err(|_| "Another GUI supervisor is running for this project")?;
        let stack = Self { root, _lock: lock };
        // A crashed GUI can leave containers behind. Resume only services whose
        // Docker-authenticated Compose labels match this repository/project.
        let output = capture(
            Command::new("docker").args([
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=chronos-gui",
            ]),
            Duration::from_secs(5),
            cancel,
        )?;
        for id in output.split_whitespace() {
            let identity = capture(Command::new("docker").args(["inspect", "--format",
                "{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}|{{ index .Config.Labels \"com.docker.compose.service\" }}", id])
                , Duration::from_secs(5), cancel)?;
            let expected_root = stack.root.to_string_lossy();
            let parts: Vec<_> = identity.trim().split('|').collect();
            if parts.len() != 2
                || parts[0] != expected_root
                || !["core-engine", "redis-store", "db-store", "desktop-relay"].contains(&parts[1])
            {
                return Err("Existing managed project has a different owner or service; inspect it before startup".into());
            }
        }
        let _ = tx.send(BackendMessage::StackStatus(
            "Starting isolated services…".into(),
        ));
        let mut up = compose(&stack.root);
        up.args([
            "up",
            "--build",
            "--detach",
            "--wait",
            "--wait-timeout",
            "90",
            "redis-store",
            "db-store",
            "core-engine",
            "desktop-relay",
        ]);
        if let Err(error) = run_cancellable(&mut up, Duration::from_secs(300), Some(cancel)) {
            stack.stop();
            return Err(error);
        }
        let _ = tx.send(BackendMessage::StackStatus(
            "Containers started; checking database, Redis and SSH readiness".into(),
        ));
        let mut ready = compose(&stack.root);
        ready.args(["exec", "-T", "core-engine", "python3", "-c",
            "import socket,time; from pathlib import Path; deadline=time.monotonic()+30\nwhile True:\n try:\n  assert any(line.split()[1]=='/mnt/honeypot' and line.split()[2].startswith('fuse') for line in Path('/proc/mounts').read_text().splitlines())\n  s=socket.create_connection(('127.0.0.1',2222),2); s.settimeout(2); banner=s.recv(255); s.close(); assert banner.startswith(b'SSH-2.0-'); break\n except Exception:\n  if time.monotonic()>deadline: raise\n  time.sleep(0.5)"]);
        if let Err(error) = run_cancellable(&mut ready, Duration::from_secs(40), Some(cancel)) {
            stack.stop();
            return Err(format!("Fake-system readiness failed: {error}"));
        }
        let _ = tx.send(BackendMessage::StackStatus(
            "Managed fake system ready; SSH on 127.0.0.1:2222".into(),
        ));
        Ok(Some(stack))
    }

    pub fn stop(self) {
        let mut stop = compose(&self.root);
        stop.args([
            "stop",
            "--timeout",
            "15",
            "desktop-relay",
            "core-engine",
            "db-store",
            "redis-store",
        ]);
        if run(stop, Duration::from_secs(60)).is_ok() {
            let mut remove = compose(&self.root);
            remove.args([
                "rm",
                "--force",
                "desktop-relay",
                "core-engine",
                "db-store",
                "redis-store",
            ]);
            // Remove only our stopped service containers, never their volumes.
            // A failed cleanup retains the lock for explicit recovery.
            let _ = run(remove, Duration::from_secs(30));
            // The stable lock inode remains. Dropping the file releases the
            // OS lock, including on process exit; no stale-file recovery race.
        }
    }
}
