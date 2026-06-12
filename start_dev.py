#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Sequence


ROOT_DIR = Path(__file__).resolve().parents[0]
FRONTEND_DIR = ROOT_DIR / "frontend"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backend_url = f"http://{args.backend_host}:{args.backend_port}"
    frontend_url = f"http://{args.frontend_host}:{args.frontend_port}"
    cors_origins = ",".join(
        {
            frontend_url,
            f"http://localhost:{args.frontend_port}",
            f"http://127.0.0.1:{args.frontend_port}",
        }
    )

    backend_env = os.environ.copy()
    backend_env["ME_AGENT_CORS_ORIGINS"] = cors_origins

    frontend_env = os.environ.copy()
    frontend_env["NEXT_PUBLIC_API_BASE_URL"] = backend_url

    processes: list[subprocess.Popen[str]] = []
    try:
        processes.append(
            start_process(
                "backend",
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.app.main:app",
                    "--reload",
                    "--host",
                    args.backend_host,
                    "--port",
                    str(args.backend_port),
                ],
                cwd=ROOT_DIR,
                env=backend_env,
            )
        )
        processes.append(
            start_process(
                "frontend",
                [
                    "npm",
                    "run",
                    "dev",
                    "--",
                    "--hostname",
                    args.frontend_host,
                    "--port",
                    str(args.frontend_port),
                ],
                cwd=FRONTEND_DIR,
                env=frontend_env,
            )
        )

        print(f"frontend: {frontend_url}", flush=True)
        print(f"backend:  {backend_url}", flush=True)
        return wait_for_exit(processes)
    except KeyboardInterrupt:
        return 130
    finally:
        stop_processes(processes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start Me.Agent frontend and backend dev servers.")
    parser.add_argument("--frontend-port", "--fe-port", type=valid_port, default=11100)
    parser.add_argument("--backend-port", "--be-port", type=valid_port, default=11101)
    parser.add_argument("--frontend-host", default="127.0.0.1")
    parser.add_argument("--backend-host", default="127.0.0.1")
    return parser


def valid_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def start_process(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    threading.Thread(target=stream_output, args=(name, process), daemon=True).start()
    return process


def stream_output(name: str, process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{name}] {line}", end="", flush=True)


def wait_for_exit(processes: Sequence[subprocess.Popen[str]]) -> int:
    while True:
        for process in processes:
            return_code = process.poll()
            if return_code is not None:
                return return_code
        threading.Event().wait(0.25)


def stop_processes(processes: Sequence[subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)


if __name__ == "__main__":
    raise SystemExit(main())
