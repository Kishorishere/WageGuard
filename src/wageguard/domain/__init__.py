# The domain package holds immutable types (Money, IDs, EffectiveRange,
# Outcome sum type, reason codes, error hierarchy). It MUST NOT import
# from llm/, evidence/, interfaces/, SQLAlchemy, or any HTTP library.
# See S-4 and the architecture tests under tests/architecture/.
