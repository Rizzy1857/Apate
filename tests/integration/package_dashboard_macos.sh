#!/usr/bin/env bash
# Local development app bundle. No signing/notarization claim.
set -euo pipefail
cd "$(dirname "$0")/../.."
test "$(uname -s)" = Darwin
if pgrep -x Mirage >/dev/null; then
  printf '%s\n' 'Close Mirage before rebuilding its app bundle.' >&2
  exit 1
else
  task_check_status=$?
  if test "$task_check_status" -ne 1; then
    printf '%s\n' 'Cannot inspect running applications; retry packaging with process-list access.' >&2
    exit 1
  fi
fi
cargo build --locked --manifest-path src/chronos/dashboard/Cargo.toml
bundle="$PWD/.local-deploy/Mirage.app"
mkdir -p "$bundle/Contents/MacOS"
task_binary="$(mktemp "$bundle/Contents/MacOS/.Mirage.XXXXXX")"
cp src/chronos/dashboard/target/debug/dashboard "$task_binary"
chmod 755 "$task_binary"
mv -f "$task_binary" "$bundle/Contents/MacOS/Mirage"
cp config/dashboard-macos.plist "$bundle/Contents/Info.plist"
codesign --force --deep --sign - "$bundle"
printf '%s\n' "$bundle"
