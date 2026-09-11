"""Model-written input generation, prepared against the LLM seam.

The generator is a DISTINCT model call from any candidate generation (a shared
reading would defeat the independence the whole verifier rests on). It asks for
TWO different artifacts, deliberately not conflated:

1. A VALID-INPUT battery across the stated domains, labelled so the coverage
   control can check every extracted edge clause is exercised.
2. For each flagged hot path, ONE maximum-size input constructed to EXPLODE THAT
   SPECIFIC hot path while staying inside every stated input bound. The hot path
   is passed IN as the target, not inferred, because a max-size input that does
   not explode the flagged quantity tests nothing while looking like a passing
   performance check.

The coverage control (solver.generator) then adjudicates whether the second
artifact actually did its job.

This module is decoupled from the concrete LLM seam: it builds prompts (pure),
parses model output into a compact input PLAN (pure), and materialises the plan
into concrete inputs (pure). The model call goes through an injected client, so
wiring to client2's ``solver.llm`` when it lands and the credential clears is a
config change, not a rewrite. The materialisation DSL is intentionally small
(literal / repeat / range) so a huge input is a compact rule, never a huge
literal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from .contracts import HotPathQuantity, SpecSheet
from .generator import LabeledInput

# The input analyst persona is DISTINCT from candidate generation so its calls
# key to their own cassette and cannot share a candidate's misreading.
_INPUT_SYSTEM = (
    "You are an input-domain analyst. You read a problem SPECIFICATION and produce "
    "INPUT DATA that exercises it. You never write, see, or reason about a solution. "
    "Your inputs must be valid under every stated domain and bound."
)
_STRESS_SYSTEM = (
    "You are an adversarial input-domain analyst. Given a SPECIFICATION and ONE named "
    "derived quantity, you construct a single maximum-size input that makes THAT quantity "
    "as large as possible while keeping every stated input bound satisfied. You never "
    "write or reason about a solution."
)

# Compact plan schema (documented for the model; also what parse_plan expects).
_PLAN_SCHEMA = (
    '{"inputs": [{"label": str, "kind": "edge|random|stress", '
    '"params": [ {"literal": any} | {"repeat": {"item": any, "times": int}} '
    '| {"range": {"start": int, "stop": int}} ]}]}'
)


@dataclass
class GenPrompt:
    kind: str  # "input" | "stress"
    system: str
    user: str
    schema: str = _PLAN_SCHEMA
    temperature: float = 0.0
    model: str = "cheap"
    target: str = ""  # for "stress": the hot-path quantity this call targets


def _param_lines(spec: SpecSheet) -> str:
    if not spec.params:
        return "(entrypoint takes stdin; produce a full input payload string)"
    return "\n".join(
        f"  - {p.name}: type={p.type}; bounds={p.bounds or 'unstated'}; notes={p.notes or '-'}"
        for p in spec.params
    )


def input_generator_prompt(spec: SpecSheet) -> GenPrompt:
    edges = "\n".join(f"  - {c}" for c in spec.edge_cases) or "  (none extracted)"
    user = (
        f"Entrypoint: {spec.signature or spec.entrypoint}\n"
        f"Parameters:\n{_param_lines(spec)}\n\n"
        f"Produce a battery of VALID inputs as a JSON plan matching:\n{_PLAN_SCHEMA}\n\n"
        "Cover, each as its own labelled input: an empty collection (label 'empty'), a "
        "singleton (label 'singleton'), each bounded parameter at its minimum "
        "(label '<name>@min') and maximum (label '<name>@max'), and one input for EACH "
        "of these stated edge clauses, labelled with the clause verbatim:\n"
        f"{edges}\n\n"
        "Use repeat/range rules for large collections rather than huge literals. Return only JSON."
    )
    return GenPrompt(kind="input", system=_INPUT_SYSTEM, user=user)


def hotpath_prompt(spec: SpecSheet, hot_path: HotPathQuantity) -> GenPrompt:
    bounds = "\n".join(f"  - {b}" for b in (spec.bounds_diff.input_bounds if spec.bounds_diff else [])) or "  (none)"
    user = (
        f"Entrypoint: {spec.signature or spec.entrypoint}\n"
        f"Parameters:\n{_param_lines(spec)}\n\n"
        f"TARGET derived quantity to maximise: {hot_path.quantity}\n"
        f"  (created by: {hot_path.source_sentence})\n"
        f"  (magnitude reachable: {hot_path.magnitude or 'unbounded'})\n\n"
        "Every stated INPUT bound must remain satisfied:\n"
        f"{bounds}\n\n"
        "Construct exactly ONE input that drives the TARGET quantity as large as possible "
        f"within those bounds. Return a JSON plan matching:\n{_PLAN_SCHEMA}\n"
        "Use repeat/range rules for large collections. Return only JSON."
    )
    return GenPrompt(kind="stress", system=_STRESS_SYSTEM, user=user, target=hot_path.quantity)


# --- parsing + materialisation (pure) ------------------------------------

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_plan(text: str) -> list[dict]:
    """Extract the ``inputs`` list from a model response (tolerant of a code
    fence or surrounding prose)."""
    m = _JSON_OBJ_RE.search(text)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    inputs = obj.get("inputs")
    return inputs if isinstance(inputs, list) else []


def _expand(value_spec: Any) -> Any:
    if not isinstance(value_spec, dict):
        return value_spec
    if "literal" in value_spec:
        return value_spec["literal"]
    if "repeat" in value_spec:
        r = value_spec["repeat"]
        return [r.get("item")] * int(r.get("times", 0))
    if "range" in value_spec:
        r = value_spec["range"]
        return list(range(int(r.get("start", 0)), int(r.get("stop", 0))))
    return value_spec


def expand_params(params: Sequence[Any]) -> list[Any]:
    """Materialise a plan's ``params`` list into concrete positional args."""
    return [_expand(v) for v in params] if isinstance(params, list) else []


def materialize(plan_items: Sequence[dict], default_kind: str = "edge") -> list[LabeledInput]:
    out: list[LabeledInput] = []
    for item in plan_items:
        if not isinstance(item, dict):
            continue
        params = item.get("params", [])
        value = [_expand(v) for v in params] if isinstance(params, list) else params
        out.append(LabeledInput(value=value, label=str(item.get("label", "")), kind=str(item.get("kind", default_kind))))
    return out


# --- seam call (injected client, so wiring is a flip) --------------------


def request_generators(
    spec: SpecSheet,
    client: Any,
    to_request: Callable[[GenPrompt], Any],
) -> tuple[list[LabeledInput], list[LabeledInput]]:
    """Make the two kinds of calls and return (battery, stress).

    ``client`` is any object with ``.complete(request).text`` (client2's
    ``solver.llm`` seam). ``to_request`` adapts a GenPrompt to that seam's request
    type (supplied by the orchestrator once ``solver.llm`` is importable), keeping
    this module free of a hard dependency on it.
    """
    battery_resp = client.complete(to_request(input_generator_prompt(spec)))
    battery = materialize(parse_plan(battery_resp.text))

    stress: list[LabeledInput] = []
    hot_paths = spec.bounds_diff.hot_paths if spec.bounds_diff else []
    for hp in hot_paths:
        resp = client.complete(to_request(hotpath_prompt(spec, hp)))
        for li in materialize(parse_plan(resp.text), default_kind="stress"):
            # force the label to the targeted hot path so coverage can adjudicate
            stress.append(LabeledInput(value=li.value, label=hp.quantity, kind="stress"))
    return battery, stress
