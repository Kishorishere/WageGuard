# ADR-0016: Cassette-based CI evaluation

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

The golden suite exercises the full pipeline, including the LLM
call. Running against a live provider in CI (on every push) is:

1. **Slow.** Each case is a network round-trip.
2. **Not free.** Tokens cost money.
3. **Nondeterministic.** Hosted models drift at temperature 0.

CI needs the golden suite to be fast, free, and deterministic.
Live-model runs are still valuable — for the cassette-refresh
workflow and periodic drift checks — but on a separate manually
triggered schedule.

## Decision

**CI runs the golden suite against recorded cassettes.** A cassette
is a JSON file keyed by a canonical hash of the request
(`model_id`, `prompt_hash`, settings, user text). `CassetteClient`
implements the `LlmClient` Protocol and replays the recorded
response when the request hash matches. A miss is a **test
failure**, not a silent live call.

- Cassettes live in `tests/_fixtures/cassettes/<suite>/<hash>.json`.
- `make record-cassettes` is an explicit workflow run that uses a
  real API key; it rewrites the cassette files and the diff is
  reviewed in a PR.
- CI (`ci.yaml`) runs with `WAGEGUARD_LLM_PROVIDER=cassette`; no
  API key is present, so any live call attempt would fail
  immediately.
- The live-eval workflow (`live-eval.yaml`, manual trigger) runs
  the suite against a real provider (Gemini or Groq) for drift
  investigations and cassette-refresh PRs.

Usage, tokens, latency, and cost come from the recorded response
where the provider returned them; they are `NULL` otherwise.
Costs are never estimated silently (spec §12.6).

## Alternatives considered

- **Live model on every CI run.** Too slow, too expensive,
  non-deterministic. Rejected.
- **Mocked LLM output inline in tests.** Works for unit tests
  (which is what `FakeClient` does); doesn't give us end-to-end
  cassettes keyed by the real request shape, so it can't catch a
  prompt-shape regression. Rejected for the golden tier.
- **Snapshot-test the prose.** Brittle; "add one word to the
  prompt" would churn every cassette. Hashing the request keeps
  the test data stable when the request hasn't changed.

## Consequences

- CI is fast and free; the golden suite can run on every push.
- A prompt or model change invalidates cassettes; the PR fails
  until `make record-cassettes` is run and the new cassettes are
  reviewed.
- Drift is explicit: live vs. cassette divergence surfaces in the
  live-eval report, not in CI noise.
- `CassetteClient` lands with Phase 8+. Phase 6 ships `FakeClient`
  (scripted responses for unit tests) which is a subset of
  cassette semantics.
