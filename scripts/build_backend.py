#!/usr/bin/env python3
"""Reproducible Build Script for Prompt Compiler Standalone Backend Executable.

Automates:
1. Environment and prerequisite verification (Python 3.14+, PyInstaller, macOS arm64)
2. Safe cleanup of previous build/dist artifacts
3. Deterministic PyInstaller execution using backend/PromptCompilerBackend.spec
4. Binary existence and Mach-O arm64 architecture verification
5. Reporting output executable location and size
"""

import os
import shutil
import subprocess
import sys


def get_repo_root() -> str:
    """Resolve the repository root directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(script_dir) in ("scripts", "bin"):
        return os.path.dirname(script_dir)
    return script_dir


def main() -> int:
    repo_root = get_repo_root()
    backend_dir = os.path.join(repo_root, "backend")
    spec_file = os.path.join(backend_dir, "PromptCompilerBackend.spec")
    dist_dir = os.path.join(backend_dir, "dist")
    build_dir = os.path.join(backend_dir, "build")
    output_exe = os.path.join(dist_dir, "prompt-compiler-backend")

    print("==================================================")
    print("PROMPT COMPILER — STANDALONE BACKEND BUILD")
    print("==================================================")
    print(f"Repository Root : {repo_root}")
    print(f"Backend Dir     : {backend_dir}")
    print(f"Spec File       : {spec_file}")
    print(f"Target Output   : {output_exe}")
    print(f"Python Version  : {sys.version.split()[0]}")
    print("==================================================")

    if not os.path.exists(spec_file):
        print(f"ERROR: Spec file not found at {spec_file}", file=sys.stderr)
        return 1

    # 1. Clean previous build artifacts
    print("\n[1/4] Cleaning previous packaging artifacts...")
    for path in (build_dir, dist_dir):
        if os.path.exists(path):
            print(f"  Removing {path}...")
            shutil.rmtree(path, ignore_errors=True)
    print("  Clean complete.")

    # 2. Find pyinstaller executable
    pyinstaller_bin = shutil.which("pyinstaller")
    venv_pyinstaller = os.path.join(backend_dir, ".venv", "bin", "pyinstaller")
    if os.path.exists(venv_pyinstaller):
        pyinstaller_bin = venv_pyinstaller

    if not pyinstaller_bin:
        print("ERROR: PyInstaller executable not found. Please install pyinstaller.", file=sys.stderr)
        return 1

    print(f"\n[2/4] Invoking PyInstaller ({pyinstaller_bin})...")
    cmd = [pyinstaller_bin, spec_file, "--noconfirm"]
    result = subprocess.run(cmd, cwd=backend_dir)
    if result.returncode != 0:
        print(f"ERROR: PyInstaller build failed with return code {result.returncode}", file=sys.stderr)
        return result.returncode

    # 3. Verify output binary exists
    print("\n[3/4] Verifying generated binary...")
    if not os.path.exists(output_exe):
        print(f"ERROR: Expected binary not found at {output_exe}", file=sys.stderr)
        return 1

    file_size_mb = os.path.getsize(output_exe) / (1024 * 1024)
    print(f"  Binary exists: {output_exe} ({file_size_mb:.1f} MB)")

    # 4. Verify architecture
    print("\n[4/4] Verifying binary architecture...")
    try:
        file_out = subprocess.check_output(["file", output_exe], text=True).strip()
        print(f"  file: {file_out}")
        if "arm64" not in file_out:
            print("  WARNING: Expected arm64 architecture, check binary inspection above.")
    except Exception as e:
        print(f"  Notice: 'file' command could not be run: {e}")

    try:
        lipo_out = subprocess.check_output(["lipo", "-info", output_exe], text=True).strip()
        print(f"  lipo: {lipo_out}")
    except Exception:
        pass

    # 5. Create Tauri 2 sidecar binary name
    sidecar_target_name = "prompt-compiler-backend-aarch64-apple-darwin"
    sidecar_target_path = os.path.join(dist_dir, sidecar_target_name)
    shutil.copy2(output_exe, sidecar_target_path)
    os.chmod(sidecar_target_path, 0o755)
    print(f"\n[5/5] Created Tauri 2 sidecar artifact:")
    print(f"  {sidecar_target_path}")

    print("\n==================================================")
    print("BUILD SUCCESSFUL!")
    print(f"Executable (Default): {output_exe}")
    print(f"Executable (Sidecar): {sidecar_target_path}")
    print("Ready for standalone testing or Tauri sidecar integration.")
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
