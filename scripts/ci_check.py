import subprocess
import sys
import os
import platform

def run_command(command, description, cwd=None, ignore_errors=False, env=None):
    print(f"🔍 {description}...")
    try:
        subprocess.run(command, shell=True, check=True, cwd=cwd, env=env)
        print(f"✅ {description} passed")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ {description} failed")
        if not ignore_errors:
            sys.exit(1)
        return False

def main():
    print("🚀 Starting Local CI Checks...")
    
    # 1. Python Dependencies
    run_command(f"{sys.executable} -m pip install -r requirements.txt", "Installing Python dependencies")
    
    # 2. Linting (Ruff)
    run_command("ruff check .", "Running Linting (Ruff)", ignore_errors=True)
    
    # 3. Formatting (Black)
    run_command("black --check .", "Checking Formatting (Black)", ignore_errors=True)
    
    # 4. Type Checking (Mypy)
    # Only run if backend directory exists
    if os.path.exists("backend"):
        run_command("mypy backend/ --ignore-missing-imports", "Running Type Checking (Mypy)", ignore_errors=True)
    
    # 5. Go Build
    if os.path.exists("go-services/go.mod"):
        # Check if go is installed
        try:
            subprocess.run(["go", "version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            run_command("go build main.go", "Building Go Services", cwd="go-services")
        except FileNotFoundError:
            print("⚠️ Go not found, skipping Go build")
    
    # 6. Rust Build
    if os.path.exists("rust-protocol/Cargo.toml"):
        # Check if cargo is installed
        try:
            subprocess.run(["cargo", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            run_command("cargo build --quiet", "Building Rust Protocol", cwd="rust-protocol")
        except FileNotFoundError:
            print("⚠️ Rust/Cargo not found, skipping Rust build")

    # 7. Tests
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    run_command(f"{sys.executable} -m pytest tests/", "Running Tests", env=env)

    print("\n🎉 All CI checks completed!")

if __name__ == "__main__":
    main()
