# AFDE-2.5 Architecture Report

Baseline: `origin/develop` merge `3957001`; 164 tests passed.

The additive runtime provides models, registry, message/event streams, artifact
store, provider bridge, five workers, dashboard, revision loop, and orchestration.
It reuses ProviderManager, SprintAutoRunner, ApprovalGuardian, and AFDE CLI.
