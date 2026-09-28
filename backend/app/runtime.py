"""Desktop backend process lifecycle manager for Prompt Compiler.

Orchestrates the lifecycle of the local FastAPI backend when running
as a desktop sidecar or local process:
1. Spawns backend process bound to local loopback interface.
2. Polls /api/health until backend is initialized and ready.
3. Provides graceful termination with safe fallback to prevent orphaned processes.
"""

import os
import signal
import subprocess
import sys
import time
from typing import Any
import httpx

from app.config import settings


class DesktopBackendManager:
    """Manages the local FastAPI backend process lifecycle for desktop mode."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        executable_path: str | None = None,
        data_dir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.host = host or settings.desktop_backend_host
        self.port = port if port is not None else settings.desktop_backend_port
        self.executable_path = executable_path
        self.data_dir = data_dir or settings.app_data_dir
        self.extra_env = env or {}
        self.process: subprocess.Popen[str] | None = None

    @property
    def base_url(self) -> str:
        """The HTTP base URL of the local backend."""
        return f"http://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        """The health check readiness URL."""
        return f"{self.base_url}/api/health"

    @property
    def runtime_status_url(self) -> str:
        """The runtime status URL."""
        return f"{self.base_url}/api/runtime/status"

    def is_running(self) -> bool:
        """Check if the backend process is currently active."""
        if self.process is None:
            return False
        return self.process.poll() is None

    def start(
        self,
        wait_for_readiness: bool = True,
        timeout: float = 15.0,
    ) -> bool:
        """Spawn the backend process and optionally wait for health check readiness.

        Args:
            wait_for_readiness: If True, polls /api/health until responsive.
            timeout: Maximum seconds to wait for readiness.

        Returns:
            True if process started (and verified ready if wait_for_readiness=True).

        Raises:
            RuntimeError: If process fails to launch or exits unexpectedly.
            TimeoutError: If process fails to become ready within timeout.
        """
        if self.is_running():
            return True

        # Build runtime environment
        proc_env = os.environ.copy()
        proc_env["DESKTOP_MODE"] = "true"
        proc_env["DESKTOP_BACKEND_HOST"] = self.host
        proc_env["DESKTOP_BACKEND_PORT"] = str(self.port)
        if self.data_dir:
            proc_env["APP_DATA_DIR"] = self.data_dir
            proc_env["PROMPT_COMPILER_DATA_DIR"] = self.data_dir
        proc_env.update(self.extra_env)

        # Build command: sidecar binary OR Python uvicorn launcher
        if self.executable_path:
            cmd = [self.executable_path, "--host", self.host, "--port", str(self.port)]
        else:
            python_bin = sys.executable
            cmd = [
                python_bin,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                self.host,
                "--port",
                str(self.port),
            ]

        # Determine backend project root directory
        backend_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=backend_dir,
                env=proc_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to spawn backend process: {exc}") from exc

        if wait_for_readiness:
            return self.wait_for_ready(timeout=timeout)

        return True

    def wait_for_ready(
        self,
        timeout: float = 15.0,
        poll_interval: float = 0.25,
    ) -> bool:
        """Poll the health check endpoint until the backend responds or timeout expires.

        Args:
            timeout: Maximum seconds to wait for readiness.
            poll_interval: Interval between poll attempts.

        Returns:
            True when backend returns HTTP 200 on /api/health.

        Raises:
            RuntimeError: If process exits prematurely before becoming ready.
            TimeoutError: If timeout expires before backend becomes healthy.
        """
        start_time = time.monotonic()
        client = httpx.Client(timeout=1.0)

        try:
            while (time.monotonic() - start_time) < timeout:
                if self.process is not None and self.process.poll() is not None:
                    _, stderr = self.process.communicate() if self.process else ("", "")
                    raise RuntimeError(
                        f"Backend process terminated unexpectedly with exit code {self.process.returncode}: {stderr}"
                    )

                try:
                    resp = client.get(self.health_url)
                    if resp.status_code == 200:
                        return True
                except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
                    pass

                time.sleep(poll_interval)

            raise TimeoutError(
                f"Backend at '{self.base_url}' failed to become ready within {timeout}s."
            )
        finally:
            client.close()

    def shutdown(self, timeout: float = 5.0) -> bool:
        """Gracefully terminate the backend process with SIGTERM, falling back to SIGKILL.

        Args:
            timeout: Maximum seconds to wait for graceful exit.

        Returns:
            True if process terminated cleanly.
        """
        if self.process is None or self.process.poll() is not None:
            self.process = None
            return True

        # Request graceful shutdown via SIGTERM
        try:
            self.process.terminate()
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Safe fallback: force kill to eliminate zombie/orphaned processes
            try:
                self.process.kill()
                self.process.wait(timeout=2.0)
            except Exception:
                pass
        except Exception:
            pass

        self.process = None
        return True

    def __enter__(self) -> "DesktopBackendManager":
        self.start(wait_for_readiness=True)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown()
