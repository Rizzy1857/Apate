"""Create a deterministic, self-verifying release-candidate evidence bundle."""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


ROOT = Path(__file__).resolve().parents[2]
TOP_LEVEL = (
    ".github",
    "config",
    "docs",
    "src",
    "tests",
    ".dockerignore",
    ".gitignore",
    "Dockerfile",
    "Makefile",
    "README.md",
    "LICENSE",
    "docker-compose.yml",
    "requirements.txt",
)
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", "target"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {".DS_Store"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def included_files():
    files = []
    for name in TOP_LEVEL:
        item = ROOT / name
        if not item.exists():
            continue
        candidates = [item] if item.is_file() else item.rglob("*")
        for path in candidates:
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(ROOT)
            if (relative.parent == Path("docs")
                    and relative.name.startswith("RELEASE_EVIDENCE_INDEX_")
                    and relative.suffix == ".md"):
                continue
            if EXCLUDED_PARTS.intersection(relative.parts):
                continue
            if path.name in EXCLUDED_NAMES:
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            files.append(relative)
    return sorted(set(files), key=str)


def deterministic_archive(files):
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for relative in files:
                data = (ROOT / relative).read_bytes()
                info = tarfile.TarInfo(str(relative))
                info.size = len(data)
                info.mode = (ROOT / relative).stat().st_mode & 0o777
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
    return raw.getvalue()


def command(*args):
    return subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def image_inventory(image):
    inspect = json.loads(command("docker", "image", "inspect", image))[0]
    inventory_script = r'''
import importlib.metadata as metadata
import hashlib
import json
from pathlib import Path

paragraphs = Path("/var/lib/dpkg/status").read_text().split("\n\n")
os_packages = []
for paragraph in paragraphs:
    fields = {}
    for line in paragraph.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    if fields.get("Package") and fields.get("Status") == "install ok installed":
        os_packages.append({
            "name": fields["Package"],
            "version": fields.get("Version"),
            "architecture": fields.get("Architecture"),
        })
python_packages = sorted(
    ({"name": dist.metadata["Name"], "version": dist.version}
     for dist in metadata.distributions()),
    key=lambda row: row["name"].lower(),
)
print(json.dumps({
    "os_packages": sorted(os_packages, key=lambda row: row["name"]),
    "python_distributions": python_packages,
    "application_files": {
        str(path.relative_to("/app")): hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in ("/app/src", "/app/config")
        for path in sorted(Path(folder).rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    },
}, sort_keys=True))
'''
    packages = json.loads(
        command("docker", "run", "--rm", image, "python3", "-c", inventory_script)
    )
    return {
        "reference": image,
        "id": inspect["Id"],
        "repo_digests": inspect.get("RepoDigests") or [],
        "architecture": inspect["Architecture"],
        "os": inspect["Os"],
        "size_bytes": inspect["Size"],
        **packages,
    }


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    files = included_files()
    archive = deterministic_archive(files)
    (output / "source.tar.gz").write_bytes(archive)
    manifest = [
        {
            "path": str(path),
            "bytes": (ROOT / path).stat().st_size,
            "sha256": sha256((ROOT / path).read_bytes()),
        }
        for path in files
    ]
    (output / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    patch = subprocess.run(
        ["git", "diff", "--binary"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    (output / "tracked.patch").write_bytes(patch)
    status = command("git", "status", "--porcelain").splitlines()
    candidate = {
        "schema_version": 1,
        "artifact_type": "mirage_release_candidate",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_commit": command("git", "rev-parse", "HEAD").strip(),
        "working_tree_dirty": bool(status),
        "git_status": status,
        "source_files": len(files),
        "source_archive_sha256": sha256(archive),
        "source_manifest_sha256": sha256(
            (output / "source_manifest.json").read_bytes()
        ),
        "tracked_patch_sha256": sha256(patch),
        "image_inventory_file": "image_inventory.json" if args.image else None,
    }
    if args.image:
        inventory = image_inventory(args.image)
        expected = {
            row['path']: row['sha256'] for row in manifest
            if row['path'].startswith(('src/', 'config/'))
            and not row['path'].startswith(('src/chronos/dashboard/', 'src/chronos/layer0/'))
        }
        if inventory['application_files'] != expected:
            raise ValueError('Image application files do not match the frozen source')
        (output / "image_inventory.json").write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n"
        )
        candidate["image_id"] = inventory["id"]
        candidate["image_inventory_sha256"] = sha256(
            (output / "image_inventory.json").read_bytes()
        )
    (output / "candidate.json").write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n"
    )
    complete = {
        "schema_version": 1,
        "artifact_type": "mirage_release_candidate_completion",
        "candidate_sha256": sha256((output / "candidate.json").read_bytes()),
        "source_archive_sha256": candidate["source_archive_sha256"],
        "source_manifest_sha256": candidate["source_manifest_sha256"],
    }
    (output / "complete.json").write_text(
        json.dumps(complete, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(candidate, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
