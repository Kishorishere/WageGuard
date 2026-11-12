"""Error hierarchy rooted at WageGuardError (spec §7.2).

The four fault families (Evidence, Llm, Verification, Ledger) are
distinct from each other and from InputRejected. A compliance outcome
cannot shape-shift into a fault, and a fault cannot be mistaken for an
abstention.
"""

from __future__ import annotations


class WageGuardError(Exception):
    """Base class for every error raised by WageGuard code."""


# --- Rejection --------------------------------------------------------------


class InputRejected(WageGuardError):
    """Structurally malformed input. Never produces a compliance outcome."""


class CurrencyMismatchError(InputRejected):
    """Arithmetic across different currencies is rejected."""


# --- Configuration ---------------------------------------------------------


class ConfigurationError(WageGuardError):
    """Startup-time defect (bad ruleset, prompt hash mismatch, etc.)."""


# --- Evidence fault family -------------------------------------------------


class EvidenceError(WageGuardError):
    """Retrieval or evidence-integrity failure."""


class RetrievalUnavailable(EvidenceError):
    """The retrieval backend is unreachable or times out."""


class SourceVersionMismatch(EvidenceError):
    """A required passage's source version does not match what the rule references."""


# --- LLM fault family ------------------------------------------------------


class LlmError(WageGuardError):
    """Any failure in the LLM call path."""


class LlmTimeout(LlmError):
    """The LLM provider did not respond within the configured timeout."""


class LlmMalformedOutput(LlmError):
    """The provider returned output that does not satisfy the schema."""


class LlmRefused(LlmError):
    """The provider declined to produce an explanation."""


# --- Verification fault family ---------------------------------------------


class VerificationFailed(WageGuardError):
    """The verifier rejected the LLM output."""


class CitationNotRetrieved(VerificationFailed):
    """A citation references a passage not in this run's evidence bundle."""


class QuoteMismatch(VerificationFailed):
    """A verbatim quote does not appear in its cited passage."""


class OutcomeContradiction(VerificationFailed):
    """The LLM-asserted outcome disagrees with the engine outcome."""


# --- Ledger fault family ---------------------------------------------------


class LedgerError(WageGuardError):
    """Any failure in the ledger append/verify path."""


class ChainBroken(LedgerError):
    """A record's prev_hash does not match the previous record's hash."""


class AppendFailed(LedgerError):
    """A ledger append did not durably commit."""
