"""Build an LlmRequest from engine outcome + evidence (spec §12.2).

The request's user text is a controlled string: outcome + controlling
rule + numeric context + delimited passage block. No user-supplied
free text reaches the LLM.
"""

from __future__ import annotations

from wageguard.compliance.checks.minimum_wage import EngineResult
from wageguard.domain.outcomes import Passed
from wageguard.evidence.retrieval import EvidenceBundle
from wageguard.llm.port import LlmClient, LlmRequest, LlmResponse
from wageguard.llm.prompts import PromptRegistry

DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT_SECONDS = 30


def build_llm_request(
    *,
    engine_result: EngineResult,
    evidence: EvidenceBundle,
    prompts: PromptRegistry,
    model_id: str,
    prompt_name: str = "explain_decision",
    prompt_version: str = "v1",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> LlmRequest:
    record = prompts.get(prompt_name, prompt_version)
    asserted = "PASS" if isinstance(engine_result.verdict, Passed) else "FLAG"
    passages_block = _render_passages(evidence)
    user_text = record.text.format(
        asserted_outcome=asserted,
        controlling_rule_id=str(engine_result.controlling_rule.rule_id),
        controlling_jurisdiction=str(engine_result.controlling_rule.jurisdiction),
        controlling_rate=engine_result.controlling_rate.to_canonical_string(),
        actual_rate=engine_result.actual_rate.to_canonical_string(),
        shortfall=(
            engine_result.shortfall.to_canonical_string()
            if engine_result.shortfall is not None
            else "null"
        ),
        passages=passages_block,
    )
    return LlmRequest(
        model_id=model_id,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        prompt_sha256=record.sha256,
        system_text="",
        user_text=user_text,
        temperature=0.0,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )


def explain_decision(
    *,
    engine_result: EngineResult,
    evidence: EvidenceBundle,
    prompts: PromptRegistry,
    client: LlmClient,
    model_id: str,
    prompt_name: str = "explain_decision",
    prompt_version: str = "v1",
) -> tuple[LlmResponse, LlmRequest]:
    req = build_llm_request(
        engine_result=engine_result,
        evidence=evidence,
        prompts=prompts,
        model_id=model_id,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
    )
    response = client.generate_structured(req)
    return response, req


def _render_passages(evidence: EvidenceBundle) -> str:
    lines: list[str] = []
    for p in evidence.required:
        lines.append(f"[required] {p.passage_id}: {p.text}")
    for sp in evidence.supplemental:
        lines.append(f"[supplemental] {sp.passage.passage_id}: {sp.passage.text}")
    return "\n".join(lines)
