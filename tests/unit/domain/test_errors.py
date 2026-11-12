"""Error hierarchy rooted at WageGuardError, with four disjoint fault families.

Rejection (`InputRejected`) is distinct from fault families. A network
timeout cannot shape-shift into "cannot determine" (S-3, G-03).
"""

from __future__ import annotations

from wageguard.domain.errors import (
    AppendFailed,
    ChainBroken,
    CitationNotRetrieved,
    ConfigurationError,
    CurrencyMismatchError,
    EvidenceError,
    InputRejected,
    LedgerError,
    LlmError,
    LlmMalformedOutput,
    LlmRefused,
    LlmTimeout,
    OutcomeContradiction,
    QuoteMismatch,
    RetrievalUnavailable,
    SourceVersionMismatch,
    VerificationFailed,
    WageGuardError,
)


def test_root_is_an_exception() -> None:
    assert issubclass(WageGuardError, Exception)


def test_input_rejected_is_direct_child() -> None:
    assert issubclass(InputRejected, WageGuardError)
    assert not issubclass(InputRejected, EvidenceError)
    assert not issubclass(InputRejected, LlmError)
    assert not issubclass(InputRejected, VerificationFailed)
    assert not issubclass(InputRejected, LedgerError)


def test_fault_families_are_distinct() -> None:
    assert not issubclass(EvidenceError, LlmError)
    assert not issubclass(LlmError, EvidenceError)
    assert not issubclass(VerificationFailed, LlmError)
    assert not issubclass(LedgerError, EvidenceError)


def test_evidence_subtree() -> None:
    assert issubclass(RetrievalUnavailable, EvidenceError)
    assert issubclass(SourceVersionMismatch, EvidenceError)


def test_llm_subtree() -> None:
    assert issubclass(LlmTimeout, LlmError)
    assert issubclass(LlmMalformedOutput, LlmError)
    assert issubclass(LlmRefused, LlmError)


def test_verification_subtree() -> None:
    assert issubclass(CitationNotRetrieved, VerificationFailed)
    assert issubclass(QuoteMismatch, VerificationFailed)
    assert issubclass(OutcomeContradiction, VerificationFailed)


def test_ledger_subtree() -> None:
    assert issubclass(ChainBroken, LedgerError)
    assert issubclass(AppendFailed, LedgerError)


def test_configuration_error_is_a_direct_child() -> None:
    assert issubclass(ConfigurationError, WageGuardError)


def test_currency_mismatch_is_input_rejected() -> None:
    assert issubclass(CurrencyMismatchError, InputRejected)
