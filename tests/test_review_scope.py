from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "plugins"
    / "code-enhance"
    / "skills"
    / "review"
    / "scripts"
    / "review_scope.py"
)


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", os.fspath(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(
        ["git", "init", os.fspath(repository)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _git(repository, "config", "user.name", "Scope Test")
    _git(repository, "config", "user.email", "scope@example.test")
    return repository


def _commit_all(repository: Path, message: str) -> str:
    _git(repository, "add", "-A")
    _git(repository, "commit", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


def _run_scope(
    *arguments: str,
    expected_returncode: int = 0,
) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, os.fspath(SCRIPT_PATH), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected_returncode, result.stderr or result.stdout
    return json.loads(result.stdout)


def _by_path(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["path"]: item for item in items}


def test_repository_scope_covers_tracked_and_nonignored_untracked_code(
    tmp_path: Path,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "src").mkdir()
    (repository / "vendor").mkdir()
    (repository / "generated").mkdir()
    (repository / "skills" / "demo").mkdir(parents=True)
    (repository / "src" / "main.py").write_text("print('main')\n", encoding="utf-8")
    (repository / "vendor" / "library.py").write_text(
        "vendor = True\n", encoding="utf-8"
    )
    (repository / "generated" / "client.py").write_text(
        "generated = True\n", encoding="utf-8"
    )
    (repository / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (repository / "README.md").write_text("# docs\n", encoding="utf-8")
    (repository / "skills" / "demo" / "SKILL.md").write_text(
        "# Runtime instructions\n", encoding="utf-8"
    )
    (repository / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    _commit_all(repository, "initial")

    (repository / "src" / "new module.py").write_text("value = 1\n", encoding="utf-8")
    (repository / "ignored.py").write_text("ignored = True\n", encoding="utf-8")

    payload = _run_scope("repo", "--repository", os.fspath(repository))

    included = _by_path(payload["included_files"])
    excluded = _by_path(payload["excluded_files"])
    assert payload["status"] == "ok"
    assert payload["mode"] == "repository"
    assert {
        "skills/demo/SKILL.md",
        "src/main.py",
        "src/new module.py",
    } <= set(included)
    assert included["src/main.py"]["source"] == "tracked"
    assert included["src/new module.py"]["source"] == "untracked"
    assert excluded["vendor/library.py"]["reason"] == "dependency_directory"
    assert excluded["generated/client.py"]["reason"] == "generated_or_build_directory"
    assert excluded["package-lock.json"]["reason"] == "lock_file"
    assert excluded["README.md"]["reason"] == "non_code_file"
    assert "ignored.py" not in included | excluded
    assert payload["counts"]["included"] == len(payload["included_files"])


def test_development_scope_combines_branch_staged_unstaged_and_untracked(
    tmp_path: Path,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "main.py").write_text("value = 1\n", encoding="utf-8")
    base = _commit_all(repository, "base")

    (repository / "branch.py").write_text("branch = True\n", encoding="utf-8")
    _commit_all(repository, "branch commit")

    (repository / "staged.py").write_text("staged = True\n", encoding="utf-8")
    _git(repository, "add", "staged.py")
    (repository / "main.py").write_text("value = 2\n", encoding="utf-8")
    (repository / "untracked.py").write_text("untracked = True\n", encoding="utf-8")

    payload = _run_scope(
        "latest",
        "--repository",
        os.fspath(repository),
        "--base",
        base,
    )

    included = _by_path(payload["included_files"])
    assert included["branch.py"]["sources"] == ["branch_commits"]
    assert included["staged.py"]["sources"] == ["staged"]
    assert included["main.py"]["sources"] == ["unstaged"]
    assert included["untracked.py"]["sources"] == ["untracked"]
    assert payload["basis"]["base_source"] == "explicit"
    assert payload["basis"]["base_commit"] == base
    assert payload["empty"] is False


def test_staged_addition_deleted_from_worktree_uses_index_content(
    tmp_path: Path,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "base.py").write_text("base = True\n", encoding="utf-8")
    _commit_all(repository, "base")

    staged_path = repository / "staged.py"
    staged_path.write_text("staged = True\n", encoding="utf-8")
    _git(repository, "add", "staged.py")
    staged_path.unlink()

    payload = _run_scope(
        "latest",
        "--repository",
        os.fspath(repository),
        "--base",
        "HEAD",
    )

    included = _by_path(payload["included_files"])
    assert included["staged.py"]["change_types"] == ["added", "deleted"]
    assert included["staged.py"]["sources"] == ["staged", "unstaged"]
    assert payload["uncovered_files"] == []
    assert payload["empty"] is False


def test_initial_commit_is_treated_as_new_first_party_content(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "app.py").write_text("app = True\n", encoding="utf-8")
    head = _commit_all(repository, "first")

    payload = _run_scope("latest", "--repository", os.fspath(repository))

    included = _by_path(payload["included_files"])
    assert payload["basis"]["head_commit"] == head
    assert payload["basis"]["base_ref"] is None
    assert payload["basis"]["base_source"] == "initial_repository"
    assert included["app.py"]["change_types"] == ["added"]
    assert included["app.py"]["sources"] == ["initial_repository"]


def test_empty_development_delta_is_explicit(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "app.py").write_text("app = True\n", encoding="utf-8")
    _commit_all(repository, "initial")

    payload = _run_scope(
        "latest",
        "--repository",
        os.fspath(repository),
        "--base",
        "HEAD",
    )

    assert payload["empty"] is True
    assert payload["included_files"] == []
    assert payload["diagnostics"] == ["No reviewable development changes were found."]


def test_pull_request_base_precedes_remote_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    base = _commit_all(repository, "base")
    _git(repository, "update-ref", "refs/remotes/origin/main", base)
    _git(
        repository,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
    )
    (repository / "app.py").write_text("value = 2\n", encoding="utf-8")
    _commit_all(repository, "feature")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")

    payload = _run_scope("latest", "--repository", os.fspath(repository))

    assert payload["basis"]["base_source"] == "pull_request"
    assert payload["basis"]["base_commit"] == base


def test_remote_default_precedes_configured_upstream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    upstream = _commit_all(repository, "upstream")
    (repository / "app.py").write_text("value = 2\n", encoding="utf-8")
    remote_default = _commit_all(repository, "remote default")
    (repository / "app.py").write_text("value = 3\n", encoding="utf-8")
    _commit_all(repository, "feature")
    branch = _git(repository, "branch", "--show-current")
    _git(repository, "branch", "trunk", upstream)
    _git(repository, "config", f"branch.{branch}.remote", ".")
    _git(repository, "config", f"branch.{branch}.merge", "refs/heads/trunk")
    _git(repository, "update-ref", "refs/remotes/origin/main", remote_default)
    _git(
        repository,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
    )
    for variable in (
        "GITHUB_BASE_REF",
        "CI_MERGE_REQUEST_TARGET_BRANCH_NAME",
        "SYSTEM_PULLREQUEST_TARGETBRANCH",
        "BUILDKITE_PULL_REQUEST_BASE_BRANCH",
        "CHANGE_TARGET",
    ):
        monkeypatch.delenv(variable, raising=False)

    payload = _run_scope("latest", "--repository", os.fspath(repository))

    assert payload["basis"]["base_source"] == "remote_default"
    assert payload["basis"]["base_commit"] == remote_default


def test_upstream_precedes_head_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    upstream = _commit_all(repository, "upstream")
    (repository / "app.py").write_text("value = 2\n", encoding="utf-8")
    _commit_all(repository, "middle")
    (repository / "app.py").write_text("value = 3\n", encoding="utf-8")
    _commit_all(repository, "feature")
    branch = _git(repository, "branch", "--show-current")
    _git(repository, "branch", "trunk", upstream)
    _git(repository, "config", f"branch.{branch}.remote", ".")
    _git(repository, "config", f"branch.{branch}.merge", "refs/heads/trunk")
    for variable in (
        "GITHUB_BASE_REF",
        "CI_MERGE_REQUEST_TARGET_BRANCH_NAME",
        "SYSTEM_PULLREQUEST_TARGETBRANCH",
        "BUILDKITE_PULL_REQUEST_BASE_BRANCH",
        "CHANGE_TARGET",
    ):
        monkeypatch.delenv(variable, raising=False)

    payload = _run_scope("latest", "--repository", os.fspath(repository))

    assert payload["basis"]["base_source"] == "upstream"
    assert payload["basis"]["base_commit"] == upstream


def test_head_parent_is_the_final_baseline_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    parent = _commit_all(repository, "parent")
    (repository / "app.py").write_text("value = 2\n", encoding="utf-8")
    _commit_all(repository, "head")
    for variable in (
        "GITHUB_BASE_REF",
        "CI_MERGE_REQUEST_TARGET_BRANCH_NAME",
        "SYSTEM_PULLREQUEST_TARGETBRANCH",
        "BUILDKITE_PULL_REQUEST_BASE_BRANCH",
        "CHANGE_TARGET",
    ):
        monkeypatch.delenv(variable, raising=False)

    payload = _run_scope("latest", "--repository", os.fspath(repository))

    assert payload["basis"]["base_source"] == "head_parent"
    assert payload["basis"]["base_commit"] == parent


def test_invalid_historical_ref_returns_machine_readable_error(
    tmp_path: Path,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "app.py").write_text("app = True\n", encoding="utf-8")
    _commit_all(repository, "initial")

    payload = _run_scope(
        "versions",
        "--repository",
        os.fspath(repository),
        "HEAD",
        "does-not-exist",
        expected_returncode=2,
    )

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "invalid_ref"


def _tagged_history(repository: Path) -> None:
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    _commit_all(repository, "v1")
    _git(repository, "tag", "v1")
    (repository / "app.py").write_text("value = 2\n", encoding="utf-8")
    _commit_all(repository, "v2")
    _git(repository, "tag", "v2")
    (repository / "feature.py").write_text("feature = True\n", encoding="utf-8")
    _commit_all(repository, "v3")
    _git(repository, "tag", "v3")


def test_three_versions_default_to_adjacent_comparisons(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    _tagged_history(repository)

    payload = _run_scope(
        "versions",
        "--repository",
        os.fspath(repository),
        "v1",
        "v2",
        "v3",
    )

    comparisons = payload["comparisons"]
    assert payload["basis"]["relation"] == "adjacent"
    assert [(item["from_ref"], item["to_ref"]) for item in comparisons] == [
        ("v1", "v2"),
        ("v2", "v3"),
    ]
    assert _by_path(comparisons[0]["included_files"])["app.py"]["change_types"] == [
        "modified"
    ]
    assert "feature.py" in _by_path(comparisons[1]["included_files"])
    assert payload["basis"]["worktree_changes_included"] is False


def test_explicit_comparison_overrides_adjacent_order(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    _tagged_history(repository)
    (repository / "workspace-only.py").write_text(
        "workspace = True\n", encoding="utf-8"
    )

    payload = _run_scope(
        "versions",
        "--repository",
        os.fspath(repository),
        "v1",
        "v2",
        "v3",
        "--compare",
        "v1",
        "v3",
    )

    assert payload["basis"]["relation"] == "explicit"
    assert len(payload["comparisons"]) == 1
    comparison = payload["comparisons"][0]
    assert (comparison["from_ref"], comparison["to_ref"]) == ("v1", "v3")
    assert "workspace-only.py" not in _by_path(comparison["included_files"])


def test_staged_rename_keeps_old_and_new_path(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "old.py").write_text("value = 1\n", encoding="utf-8")
    _commit_all(repository, "initial")
    _git(repository, "mv", "old.py", "new.py")

    payload = _run_scope(
        "latest",
        "--repository",
        os.fspath(repository),
        "--base",
        "HEAD",
    )

    renamed = _by_path(payload["included_files"])["new.py"]
    assert renamed["change_types"] == ["renamed"]
    assert renamed["old_paths"] == ["old.py"]
    assert renamed["sources"] == ["staged"]


def test_binary_extension_and_binary_content_are_excluded(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (repository / "looks-like-code.py").write_bytes(b"prefix\0payload")

    payload = _run_scope("repo", "--repository", os.fspath(repository))

    excluded = _by_path(payload["excluded_files"])
    assert excluded["image.png"]["reason"] == "binary_extension"
    assert excluded["looks-like-code.py"]["reason"] == "binary_content"
    assert payload["included_files"] == []


def test_generated_marker_must_be_a_header_comment(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "scanner.py").write_text(
        'GENERATED_MARKERS = (b"do not edit",)\n', encoding="utf-8"
    )
    (repository / "generated.py").write_text(
        "# Code generated by fixture. DO NOT EDIT.\nvalue = 1\n",
        encoding="utf-8",
    )

    payload = _run_scope("repo", "--repository", os.fspath(repository))

    included = _by_path(payload["included_files"])
    excluded = _by_path(payload["excluded_files"])
    assert "scanner.py" in included
    assert excluded["generated.py"]["reason"] == "generated_file"


def test_extensionless_shebang_in_bin_is_code_and_unknown_text_is_uncovered(
    tmp_path: Path,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "bin").mkdir()
    (repository / "bin" / "release").write_text(
        "#!/usr/bin/env bash\nset -eu\n", encoding="utf-8"
    )
    (repository / "domain.customlang").write_text("entity Order {}\n", encoding="utf-8")

    payload = _run_scope("repo", "--repository", os.fspath(repository))

    assert "bin/release" in _by_path(payload["included_files"])
    uncovered = _by_path(payload["uncovered_files"])
    assert uncovered["domain.customlang"]["reason"] == "unrecognized_text_type"


def test_binary_detection_scans_beyond_the_initial_chunk(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "late-binary.py").write_bytes(b"x" * 20_000 + b"\0payload")

    payload = _run_scope("repo", "--repository", os.fspath(repository))

    excluded = _by_path(payload["excluded_files"])
    assert excluded["late-binary.py"]["reason"] == "binary_content"


def test_large_historical_binary_is_excluded(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "large.py").write_text("value = 1\n", encoding="utf-8")
    _commit_all(repository, "text")
    _git(repository, "tag", "text")
    (repository / "large.py").write_bytes(b"x" * 300_000 + b"\0payload")
    _commit_all(repository, "binary")
    _git(repository, "tag", "binary")

    payload = _run_scope(
        "versions",
        "--repository",
        os.fspath(repository),
        "text",
        "binary",
    )

    comparison = payload["comparisons"][0]
    excluded = _by_path(comparison["excluded_files"])
    assert excluded["large.py"]["reason"] == "binary_content"


def test_rename_into_vendor_preserves_first_party_deletion(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "src").mkdir()
    (repository / "src" / "feature.py").write_text("feature = True\n", encoding="utf-8")
    _commit_all(repository, "initial")
    (repository / "vendor").mkdir()
    _git(repository, "mv", "src/feature.py", "vendor/feature.py")

    payload = _run_scope(
        "latest",
        "--repository",
        os.fspath(repository),
        "--base",
        "HEAD",
    )

    included = _by_path(payload["included_files"])
    excluded = _by_path(payload["excluded_files"])
    assert included["src/feature.py"]["change_types"] == ["deleted"]
    assert included["src/feature.py"]["renamed_to"] == ["vendor/feature.py"]
    assert excluded["vendor/feature.py"]["reason"] == "dependency_directory"


def test_historical_rename_into_vendor_preserves_first_party_deletion(
    tmp_path: Path,
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "src").mkdir()
    (repository / "src" / "feature.py").write_text("feature = True\n", encoding="utf-8")
    _commit_all(repository, "before")
    _git(repository, "tag", "before")
    (repository / "vendor").mkdir()
    _git(repository, "mv", "src/feature.py", "vendor/feature.py")
    _commit_all(repository, "after")
    _git(repository, "tag", "after")

    payload = _run_scope(
        "versions",
        "--repository",
        os.fspath(repository),
        "before",
        "after",
    )

    comparison = payload["comparisons"][0]
    included = _by_path(comparison["included_files"])
    excluded = _by_path(comparison["excluded_files"])
    assert included["src/feature.py"]["change_types"] == ["deleted"]
    assert included["src/feature.py"]["renamed_to"] == ["vendor/feature.py"]
    assert excluded["vendor/feature.py"]["reason"] == "dependency_directory"


def test_nul_delimited_paths_preserve_spaces_and_unicode(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "src").mkdir()
    special = "src/name with space 雪.py"
    (repository / special).write_text("snow = True\n", encoding="utf-8")

    payload = _run_scope("repo", "--repository", os.fspath(repository))

    assert special in _by_path(payload["included_files"])


def test_json_output_is_safe_for_ascii_only_stdout(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    special = "雪.py"
    (repository / special).write_text("snow = True\n", encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "ascii"

    result = subprocess.run(
        [
            sys.executable,
            os.fspath(SCRIPT_PATH),
            "repo",
            "--repository",
            os.fspath(repository),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert special in _by_path(json.loads(result.stdout)["included_files"])


@pytest.mark.skipif(os.name == "nt", reason="Windows filenames cannot contain newlines")
def test_nul_delimited_paths_preserve_newlines(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    (repository / "src").mkdir()
    special = "src/name with\nnewline.py"
    (repository / special).write_text("value = True\n", encoding="utf-8")

    payload = _run_scope("repo", "--repository", os.fspath(repository))

    assert special in _by_path(payload["included_files"])


def test_repository_external_scope_path_is_rejected(tmp_path: Path) -> None:
    repository = _init_repository(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()

    payload = _run_scope(
        "repo",
        "--repository",
        os.fspath(repository),
        "--path",
        os.fspath(outside),
        expected_returncode=2,
    )

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "path_outside_repository"


@pytest.mark.parametrize(
    ("command", "extra_arguments"),
    [
        ("latest", ["--base", "HEAD"]),
        ("versions", ["HEAD", "HEAD"]),
    ],
)
def test_missing_in_repository_scope_path_is_rejected(
    tmp_path: Path,
    command: str,
    extra_arguments: list[str],
) -> None:
    repository = _init_repository(tmp_path)
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    _commit_all(repository, "initial")

    payload = _run_scope(
        command,
        "--repository",
        os.fspath(repository),
        "--path",
        "missing",
        *extra_arguments,
        expected_returncode=2,
    )

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "scope_path_not_found"


@pytest.mark.parametrize("command", ["repo", "latest", "versions"])
def test_non_git_directory_is_rejected(tmp_path: Path, command: str) -> None:
    arguments = [command, "--repository", os.fspath(tmp_path)]
    if command == "versions":
        arguments.extend(["v1", "v2"])

    payload = _run_scope(*arguments, expected_returncode=2)

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "not_a_git_repository"
