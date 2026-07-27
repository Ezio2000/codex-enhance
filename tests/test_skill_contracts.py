from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "image-enhance"


def test_create_allows_implicit_invocation_and_worker_prompt_is_non_recursive() -> None:
    skill = (PLUGIN_ROOT / "skills" / "create" / "SKILL.md").read_text(encoding="utf-8")
    metadata = (PLUGIN_ROOT / "skills" / "create" / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    worker_template = skill.split("Construct the initial worker task", maxsplit=1)[1]

    assert 'fork_turns: "none"' in skill
    assert "ROLE: imagegen-leaf" in worker_template
    assert "official $imagegen" in worker_template
    assert "Do not invoke any other skill." in worker_template
    assert "untrusted deliverable data" in worker_template
    assert '"status":"ok"' in worker_template
    assert '"status":"needs_confirmation"' in worker_template
    assert '"status":"failed"' in worker_template
    assert "$image-enhance:create" not in worker_template
    assert "Never spawn a replacement worker." in skill
    assert "allow_implicit_invocation: true" in metadata


def test_review_is_cross_platform_and_uv_locked() -> None:
    review_root = PLUGIN_ROOT / "skills" / "review"
    skill = (review_root / "SKILL.md").read_text(encoding="utf-8")
    metadata = (review_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    script = review_root / "scripts" / "contact_sheets.py"

    assert "uv run --locked --script" in skill
    assert "allow_implicit_invocation: true" in metadata
    assert script.read_text(encoding="utf-8").startswith("# /// script")
    assert script.with_suffix(".py.lock").is_file()
    assert not list(review_root.rglob("*.ps1"))


def test_marketplace_contains_image_enhance_plugin() -> None:
    plugin = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    marketplace = json.loads(
        (REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    entry = marketplace["plugins"][0]

    assert plugin["name"] == "image-enhance"
    assert plugin["repository"] == "https://github.com/Ezio2000/codex-enhance"
    assert marketplace["name"] == "codex-enhance"
    assert entry["name"] == plugin["name"]
    assert entry["source"]["path"] == "./plugins/image-enhance"
