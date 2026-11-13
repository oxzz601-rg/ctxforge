import json

import pytest

from ctxforge.core import build_bundle, collect, estimate_tokens, rank


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "README.md").write_text("# Demo\n\nA tiny service that bills customers.\n")
    (tmp_path / "src" / "billing.py").write_text(
        "from src.db import connect\n\n\ndef charge(customer):\n    \"\"\"Retry billing with exponential backoff.\"\"\"\n    return connect()\n"
    )
    (tmp_path / "src" / "db.py").write_text("def connect():\n    return 'db'\n")
    (tmp_path / "tests" / "test_billing.py").write_text("def test_charge():\n    assert True\n")
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG\x00\x00binary")
    return tmp_path


def test_collect_skips_binaries(repo):
    files, skipped = collect(repo)
    paths = {item.path for item in files}
    assert "src/billing.py" in paths and "README.md" in paths
    assert "assets/logo.png" not in paths
    assert "assets/logo.png" in skipped


def test_query_ranking_puts_the_relevant_file_first(repo):
    files, _ = collect(repo)
    ranked = rank(files, "retry billing backoff")
    assert ranked[0].path == "src/billing.py"
    assert ranked[0].score > 0


def test_imports_are_pulled_in(repo):
    files, _ = collect(repo)
    ranked = {item.path: item for item in rank(files, "retry billing")}
    assert ranked["src/db.py"].score > 0


def test_budget_is_respected(repo):
    bundle = build_bundle(repo, query="billing", budget=120, max_file_tokens=60)
    assert bundle.total_tokens <= 120
    assert bundle.files


def test_large_files_are_truncated(repo):
    (repo / "src" / "big.py").write_text("\n".join("value_{} = {}".format(i, i) for i in range(400)))
    bundle = build_bundle(repo, query="big value", budget=400, max_file_tokens=40)
    truncated = [item for item in bundle.files if item.truncated]
    assert truncated, "expected at least one truncated file"
    assert "omitted by ctxforge" in truncated[0].text


def test_include_and_exclude(repo):
    files, _ = collect(repo, include=("src/*",))
    assert {item.path for item in files} == {"src/billing.py", "src/db.py"}
    files, skipped = collect(repo, exclude=("tests/*",))
    assert "tests/test_billing.py" not in {item.path for item in files}
    assert "tests/test_billing.py" in skipped


def test_render_is_deterministic_and_complete(repo):
    first = build_bundle(repo, query="billing", budget=4000)
    second = build_bundle(repo, query="billing", budget=4000)
    assert first.render() == second.render()
    text = first.render()
    assert "## Repository map" in text
    assert "```python" in text
    assert "## README.md" in text
    manifest = json.loads(json.dumps(first.manifest()))
    assert manifest["total_tokens"] == first.total_tokens


def test_token_estimate_is_conservative():
    assert estimate_tokens("hello world") >= 2
    assert estimate_tokens("") == 1


def test_missing_directory_is_reported(tmp_path):
    with pytest.raises(NotADirectoryError):
        build_bundle(tmp_path / "nope")
