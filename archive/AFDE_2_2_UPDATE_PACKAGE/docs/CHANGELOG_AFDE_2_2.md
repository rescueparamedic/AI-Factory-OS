# AFDE-2.2 Changelog

- Added backward-compatible `TaskRunner` facade.
- Preserved `AFDETaskRunner.run_mock_pipeline()`.
- Fixed CLI provider status call to use `ProviderManager.as_dicts()`.
- Added project-root aware CLI execution.
- Added explicit CLI exit codes.
- Added runtime regression tests for providers, env-check, bootstrap-worker, and run-mock.
