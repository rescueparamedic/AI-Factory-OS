# AFDE-2.7 Human Approval Resume

AFDE-2.7 adds a persisted Product Owner approval boundary for controlled edits
of existing workspace text files.

## Contract

An existing-file `FILE_WRITE` remains `ASK_USER`. Runtime persists the exact
request and continuation, sets `waiting_approval`, and returns without writing
the target or running later workers.

Approval binds the approval ID, execution request, session, worker, action type,
normalized payload, target, expected pre-image hash, and canonical fingerprint.
It is single-use. Reject, replay, mismatch, missing state, or changed pre-image
fails closed.

## Evidence and CLI

Runtime records Guardian, pending, human decision, hashes, write result,
consumption, resume, and bounded QA evidence. Provider claims stay separate.

The accepted Product Owner-gated live lifecycle is session
`RWS-20260713-212619-e9259d`, approval
`APR-4ca9eb34a7d2472ea65d71299b9518c4`, and execution
`EXE-3e87a5983102451fb7cf6d573a7f5da2`. Runtime evidence—not provider prose—
observed the exact LF payload hash, successful controlled write, one successful
bounded fixture pytest execution, single approval consumption, and final
Execution Truth `VERIFIED`. The dedicated fixture was restored to its exact LF
baseline after evidence capture. Generated runtime records remain local data and
are not source-controlled Sprint artifacts.

```text
python -m afde.cli approval-show --id APR-...
python -m afde.cli approval-approve --id APR-...
python -m afde.cli approval-reject --id APR-...
```

## Limitations

There is no wildcard approval, automatic rollback, arbitrary patch, delete,
rename, shell, network, Git, package, release, deployment, or credential access.
Concurrent approval locking and UI remain future work. Live validation is a
separate Product Owner gate and must stop at `waiting_approval` before an exact
request is explicitly approved and resumed.
