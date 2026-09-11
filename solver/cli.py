"""Command-line entry: ``solve <problem.json> -> <solution file>``.

Usage:
    python3 -m solver PROBLEM.json [-o OUT] [-n N] [--runlog PATH] [--quiet]

``PROCESS_START`` is captured at import — as close to process start as we can
get — so the deadline is measured as a hard wall-clock budget from launch.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROCESS_START = time.monotonic()

from .contracts import Problem  # noqa: E402 - after PROCESS_START on purpose
from .orchestrator import solve
from .runlog import RunLog


def _resolve_out(out_arg: str | None, problem: Problem) -> Path:
    """Pick the solution file path.

    -o may be a directory (file becomes ``<id>.<ext>`` inside it) or a full file
    path. Default: ``./solutions/<id>.<ext>``.
    """
    ext = problem.ext
    filename = f"{problem.problem_id}.{ext}"
    if out_arg is None:
        return Path("solutions") / filename
    p = Path(out_arg)
    if p.is_dir() or out_arg.endswith(("/", "\\")) or p.suffix == "":
        return p / filename
    return p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solve", description="ChallengeBox solver (spine)")
    parser.add_argument("problem", help="path to the problem JSON")
    parser.add_argument("-o", "--out", help="output file or directory (default ./solutions/)")
    parser.add_argument("-n", "--candidates", type=int, default=1, help="candidates to generate")
    parser.add_argument("--runlog", help="run-log JSON path (default alongside the solution)")
    parser.add_argument("--quiet", action="store_true", help="only print the solution path")
    args = parser.parse_args(argv)

    try:
        problem = Problem.load(args.problem)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_path = _resolve_out(args.out, problem)
    runlog_path = Path(args.runlog) if args.runlog else out_path.with_suffix(".runlog.json")

    log = RunLog(problem.problem_id, start=PROCESS_START)
    result = solve(problem, out_path, start=PROCESS_START, n_candidates=args.candidates, runlog=log)
    log.write(runlog_path)

    if args.quiet:
        print(result.path)
    else:
        print(result.runlog.summary())
        print(
            f"\nsolution : {result.path}"
            f"\nrun log  : {runlog_path}"
            f"\ndelivered: {result.delivered} (verified={result.verified},"
            f" remaining={result.budget.remaining():.2f}s of {problem.deadline_s:.0f}s)"
        )

    return 0 if result.delivered else 1


if __name__ == "__main__":
    raise SystemExit(main())
