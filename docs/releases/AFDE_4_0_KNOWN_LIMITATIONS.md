# AFDE-4.0 Beta Known Limitations

- The official Beta path supports only mock and OpenAI providers.
- Execution is limited to one registered development_worker.
- Plan tasks execute sequentially; parallel execution is not supported.
- Provider response content is treated as a worker instruction and is not
  executed as code or as an autonomous tool action.
- The deterministic rule-based Planner always creates the existing
  prepare/execute/verify chain.
- Runtime Evidence is local JSON and has no database, cross-process lock,
  signature, tamper-evident chain, retention policy, or remote replication.
- Failure evidence cannot be produced when the evidence directory or file
  itself cannot be created; the CLI reports exit code 7 instead.
- The Beta path has no resume, retry scheduler, automatic replanning, provider
  routing, or provider fallback.
- Live OpenAI behavior depends on external availability, account permissions,
  rate limits, network transport, and model availability.
- The Beta service executes only the plan's bounded Execute goal task; Prepare
  and Verify remain plan context and are not separate provider calls.
- There is no multi-agent execution, autonomous loop, memory, RAG, vector
  database, UI workflow, or additional external integration.
- factory-demo and Operator remain separate legacy-compatible workflows and are
  not aliases for the official Beta execute command.
