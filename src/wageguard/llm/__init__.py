# LLM port + provider-agnostic adapters.
# Development adapters are Gemini and Groq (user directive); the port is
# designed so any provider implementing `LlmClient` can plug in. No module
# in the codebase imports `anthropic` or `openai`.
