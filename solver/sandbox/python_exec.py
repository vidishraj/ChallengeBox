"""Run a Python candidate in a resource-limited subprocess.

The candidate's ``entrypoint`` function is executed in a fresh ``python3``
process with a wall-clock timeout and an address-space (memory) cap, so a
runaway or memory-hungry candidate cannot take the harness down. The outcome is
mapped to a structured :class:`ExecResult`.
"""

from __future__ import annotations

import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional, Sequence

from ..contracts import ExecResult, ExecStatus

_DRIVER = str(Path(__file__).with_name("_py_driver.py"))

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MEM_BYTES = 1024 * 1024 * 1024  # 1 GiB address-space cap


def _limit_memory(mem_bytes: int):
    """preexec_fn: cap the child's virtual address space (POSIX only)."""

    def _apply() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

    return _apply


def run_python_candidate(
    source: str,
    entrypoint: str,
    args: Optional[Sequence[Any]] = None,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    mem_bytes: int = DEFAULT_MEM_BYTES,
) -> ExecResult:
    """Execute ``entrypoint(*args)`` from ``source`` and classify the outcome.

    ``args`` defaults to ``[]`` (a smoke run: does the module import and does the
    entrypoint exist + run without crashing).
    """
    args = list(args or [])
    started = time.monotonic()

    with tempfile.TemporaryDirectory(prefix="cbox-py-") as tmp:
        d = Path(tmp)
        candidate_path = d / "candidate.py"
        args_path = d / "args.json"
        result_path = d / "result.json"
        candidate_path.write_text(source, encoding="utf-8")
        args_path.write_text(json.dumps(args), encoding="utf-8")

        cmd = [sys.executable, _DRIVER, str(candidate_path), entrypoint, str(args_path), str(result_path)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                preexec_fn=_limit_memory(mem_bytes),
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(
                status=ExecStatus.TIMED_OUT,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                error=f"exceeded {timeout_s}s wall-clock",
                duration_s=time.monotonic() - started,
            )

        duration = time.monotonic() - started

        # The driver writes a structured result unless it was killed hard
        # (e.g. OOM from the RLIMIT_AS cap, or a segfault).
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            status = ExecStatus(payload["status"])
            value = payload.get("value_json")
            if value is None and status == ExecStatus.OK:
                value = payload.get("value_repr")
            return ExecResult(
                status=status,
                value=value,
                stdout=proc.stdout,
                stderr=proc.stderr,
                error=payload.get("error", ""),
                duration_s=duration,
            )

        killed = proc.returncode < 0  # terminated by a signal (OOM / segfault)
        return ExecResult(
            status=ExecStatus.CRASHED,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error=(
                "process killed (likely out of memory or fatal signal)"
                if killed
                else f"process exited {proc.returncode} without a result"
            ),
            duration_s=duration,
        )
