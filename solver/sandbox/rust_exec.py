"""Compile and run a Rust candidate under resource limits.

Compiles with ``rustc -O -C overflow-checks=on`` so the candidate is optimized
for speed on maximum-size inputs AND integer overflow panics (a DETECTABLE
:data:`ExecStatus.OVERFLOWED`) instead of silently wrapping — the failure mode
we could otherwise never see, since a release build would wrap and hand the
grader a wrong answer. Degrades cleanly to ``compile-error`` if ``rustc`` is
absent.
"""

from __future__ import annotations

import resource
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from ..contracts import ExecResult, ExecStatus

DEFAULT_COMPILE_TIMEOUT_S = 60.0
DEFAULT_RUN_TIMEOUT_S = 10.0
DEFAULT_MEM_BYTES = 1024 * 1024 * 1024  # 1 GiB


def rustc_path() -> Optional[str]:
    """Absolute path to ``rustc``, or None if it is not on the box."""
    return shutil.which("rustc")


def _limit_memory(mem_bytes: int):
    def _apply() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

    return _apply


def run_rust_candidate(
    source: str,
    stdin: str = "",
    *,
    compile_timeout_s: float = DEFAULT_COMPILE_TIMEOUT_S,
    run_timeout_s: float = DEFAULT_RUN_TIMEOUT_S,
    mem_bytes: int = DEFAULT_MEM_BYTES,
    overflow_checks: bool = True,
) -> ExecResult:
    """Compile and run a Rust candidate.

    ``overflow_checks=True`` (default) is the CORRECTNESS build: integer overflow
    panics into a detectable :data:`ExecStatus.OVERFLOWED` instead of wrapping.
    ``overflow_checks=False`` is the TIMING build used by the performance probe —
    the checks cost real cycles, and we judge "fast enough at maximum size"
    against the same unchecked build the grader effectively runs, so a candidate
    that is correct is not discarded as slow for a tax the grader never pays.
    """
    started = time.monotonic()

    rustc = rustc_path()
    if rustc is None:
        return ExecResult(
            status=ExecStatus.COMPILE_ERROR,
            error="rustc not available on this host",
            duration_s=time.monotonic() - started,
        )

    with TemporaryDirectory(prefix="cbox-rs-") as tmp:
        d = Path(tmp)
        src = d / "candidate.rs"
        binary = d / "candidate"
        src.write_text(source, encoding="utf-8")

        rustc_cmd = [rustc, "-O"]
        if overflow_checks:
            rustc_cmd += ["-C", "overflow-checks=on"]
        rustc_cmd += ["-o", str(binary), str(src)]

        # --- compile ---
        try:
            comp = subprocess.run(
                rustc_cmd,
                capture_output=True,
                text=True,
                timeout=compile_timeout_s,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(
                status=ExecStatus.COMPILE_ERROR,
                error=f"rustc exceeded {compile_timeout_s}s",
                duration_s=time.monotonic() - started,
            )
        if comp.returncode != 0:
            return ExecResult(
                status=ExecStatus.COMPILE_ERROR,
                stderr=comp.stderr,
                error="rustc failed",
                duration_s=time.monotonic() - started,
            )

        # --- run (stdin -> stdout) ---
        try:
            proc = subprocess.run(
                [str(binary)],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=run_timeout_s,
                preexec_fn=_limit_memory(mem_bytes),
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(
                status=ExecStatus.TIMED_OUT,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                error=f"exceeded {run_timeout_s}s wall-clock",
                duration_s=time.monotonic() - started,
            )

        duration = time.monotonic() - started
        if proc.returncode == 0:
            return ExecResult(
                status=ExecStatus.OK,
                value=proc.stdout,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_s=duration,
            )

        # Overflow checks turn a too-narrow integer type into a panic we can see.
        overflowed = "with overflow" in proc.stderr
        return ExecResult(
            status=ExecStatus.OVERFLOWED if overflowed else ExecStatus.CRASHED,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error=(
                "integer overflow (checked build)"
                if overflowed
                else f"exited {proc.returncode}"
            ),
            duration_s=duration,
        )
