# AFDE-2.6 Real AI Provider Sprint

The existing AFDE-2.5 five-worker runtime now supports an opt-in OpenAI provider
while retaining the deterministic mock provider. The adapter uses the Responses
API, worker-specific system instructions, prior worker output context, normalized
JSON results, usage metadata, request IDs, structured failures, and the existing
revision/artifact/event flow.

Configuration is environment-only: `OPENAI_API_KEY`,
`AI_FACTORY_OPENAI_MODEL`, `AI_FACTORY_OPENAI_TIMEOUT_SECONDS`, and
`AI_FACTORY_OPENAI_MAX_RETRIES`. External calls also require
`--allow-live-api`. The SDK import is lazy, so mock execution remains functional
when the optional OpenAI package is unavailable.

No live request is part of the default test suite. A human must intentionally
provide a key, accept possible charges, and opt in before live validation.
