import pytest
from afde.cli import build_parser
from real_worker_runtime import RealWorkerRuntime
@pytest.mark.parametrize("value",["0","1","2","3"])
def test_revision_option(value): assert build_parser().parse_args(["factory-demo","--request","x","--max-revisions",value]).max_revisions==int(value)
def test_one_revision_succeeds(tmp_path): assert RealWorkerRuntime(tmp_path).run("demo [qa-fail-once]",live=False,max_revisions=1).status=="completed"
def test_revision_disabled_fails(tmp_path): assert RealWorkerRuntime(tmp_path).run("demo [qa-fail-once]",live=False,max_revisions=0).status=="failed"
