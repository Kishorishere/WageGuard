"""Parser: untrusted JSON -> validated model -> normalized -> RawFacts.

The one function that spans the trust boundary. Every failure mode maps
to `InputRejected` with field-level detail; a well-formed but incomplete
request becomes `CannotDetermine` later in the resolver, not here.
"""

from __future__ import annotations

import json
from types import MappingProxyType

from pydantic import ValidationError

from wageguard.compliance.facts import RawFacts
from wageguard.domain.enums import CheckType
from wageguard.domain.errors import InputRejected
from wageguard.domain.fields import FieldName
from wageguard.intake.model import CheckRequestModel
from wageguard.intake.normalize import normalize_check_request


def parse_check_request(raw_json: str) -> RawFacts:
    """Convert a JSON string into typed, normalized RawFacts.

    Raises `InputRejected` on malformed JSON, unknown fields, wrong
    types, or non-ISO dates. Well-formed requests with missing fields
    are the resolver's problem, not this function's.
    """
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise InputRejected(f"malformed JSON: {exc.msg} at char {exc.pos}") from exc

    if not isinstance(payload, dict):
        raise InputRejected(f"request body must be a JSON object, got {type(payload).__name__}")

    normalized = normalize_check_request(payload)

    try:
        model = CheckRequestModel.model_validate(normalized)
    except ValidationError as exc:
        raise InputRejected(_format_validation_error(exc)) from exc

    return _to_raw_facts(model)


def _format_validation_error(exc: ValidationError) -> str:
    """Human-readable, field-named error summary."""
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "invalid")
        parts.append(f"{loc}: {msg}")
    return "input validation failed: " + "; ".join(parts)


def _to_raw_facts(model: CheckRequestModel) -> RawFacts:
    dumped = model.model_dump()
    values: dict[FieldName, object] = {}
    for field_name in FieldName:
        if field_name.value in dumped:
            values[field_name] = dumped[field_name.value]
    check = CheckType(dumped["check"])
    return RawFacts(check=check, values=MappingProxyType(values))
