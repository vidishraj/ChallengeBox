"""Subprocess driver for running one Python candidate.

Invoked as a bare subprocess (no dependency on the solver package):

    python3 _py_driver.py <candidate.py> <entrypoint> <args.json> <result.json>

It imports the candidate, calls ``entrypoint(*args)``, and writes a structured
result JSON to ``<result.json>``:

    {"status": "ok"|"wrong-shape"|"crashed"|"compile-error",
     "value_json": <json-or-null>, "value_repr": "...", "error": "..."}

Wall-clock timeout and the memory cap are imposed by the PARENT (subprocess
timeout + RLIMIT_AS via preexec), so this stays minimal and stdlib-only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import traceback


def _write(result_path, payload):
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def main(argv):
    candidate_path, entrypoint, args_path, result_path = argv[1], argv[2], argv[3], argv[4]

    # 1. Import the candidate module ("compile" step for Python).
    try:
        spec = importlib.util.spec_from_file_location("candidate", candidate_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except SyntaxError as exc:
        _write(result_path, {"status": "compile-error", "error": f"{exc}"})
        return
    except BaseException:  # noqa: BLE001 - any import-time failure is a crash
        _write(result_path, {"status": "crashed", "error": traceback.format_exc()})
        return

    # 2. The required entrypoint must exist and be callable (solution shape).
    func = getattr(module, entrypoint, None)
    if not callable(func):
        _write(
            result_path,
            {"status": "wrong-shape", "error": f"module does not define callable {entrypoint!r}"},
        )
        return

    # 3. Load positional args (a JSON list; [] for a smoke run).
    try:
        with open(args_path, "r", encoding="utf-8") as fh:
            args = json.load(fh)
        if not isinstance(args, list):
            args = [args]
    except Exception:  # noqa: BLE001
        args = []

    # 4. Call it and capture the return value or the failure.
    try:
        value = func(*args)
    except BaseException:  # noqa: BLE001 - candidate raised
        _write(result_path, {"status": "crashed", "error": traceback.format_exc()})
        return

    try:
        value_json = json.loads(json.dumps(value))
    except Exception:  # noqa: BLE001 - not JSON-serializable; keep the repr
        value_json = None
    _write(
        result_path,
        {"status": "ok", "value_json": value_json, "value_repr": repr(value), "error": ""},
    )


if __name__ == "__main__":
    main(sys.argv)
