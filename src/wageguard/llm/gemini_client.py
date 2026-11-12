"""Gemini HTTP adapter (spec §12.6; user directive on provider-agnostic port).

Implements `LlmClient` against Google's generativelanguage.googleapis.com
endpoint using httpx. No vendor SDK import.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from wageguard.domain.errors import LlmMalformedOutput, LlmRefused, LlmTimeout
from wageguard.llm.port import LlmRequest, LlmResponse, LlmUsage


@dataclass(frozen=True, slots=True)
class GeminiClient:
    api_key: str
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    def generate_structured(self, req: LlmRequest) -> LlmResponse:
        url = f"{self.base_url}/models/{req.model_id}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": req.user_text}]}],
            "generationConfig": {
                "temperature": req.temperature,
                "maxOutputTokens": req.max_tokens,
                "responseMimeType": "application/json",
            },
        }
        if req.system_text:
            payload["systemInstruction"] = {"parts": [{"text": req.system_text}]}

        started = time.monotonic()
        try:
            response = httpx.post(
                url,
                params={"key": self.api_key},
                json=payload,
                timeout=req.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise LlmTimeout(f"gemini timeout after {req.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise LlmTimeout(f"gemini transport error: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        if response.status_code == 429:
            raise LlmTimeout(f"gemini rate limit: {response.status_code}")
        if 400 <= response.status_code < 600:
            raise LlmRefused(f"gemini returned HTTP {response.status_code}: {response.text[:200]}")

        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise LlmMalformedOutput("gemini response had no candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        if not parts or "text" not in parts[0]:
            raise LlmMalformedOutput("gemini candidate had no text part")
        raw_text = parts[0]["text"]
        usage_raw = data.get("usageMetadata") or {}
        usage = LlmUsage(
            prompt_tokens=usage_raw.get("promptTokenCount"),
            completion_tokens=usage_raw.get("candidatesTokenCount"),
            total_tokens=usage_raw.get("totalTokenCount"),
        )
        return LlmResponse(
            raw_text=raw_text,
            model_id=req.model_id,
            finish_reason=candidates[0].get("finishReason", "stop"),
            usage=usage,
            latency_ms=latency_ms,
        )
