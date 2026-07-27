from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = REPOSITORY_ROOT / "plugins"
IMAGE_PLUGIN_ROOT = PLUGINS_ROOT / "image-enhance"


def test_create_allows_implicit_invocation_and_worker_prompt_is_non_recursive() -> None:
    skill = (IMAGE_PLUGIN_ROOT / "skills" / "create" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    metadata = (
        IMAGE_PLUGIN_ROOT / "skills" / "create" / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
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
    review_root = IMAGE_PLUGIN_ROOT / "skills" / "review"
    skill = (review_root / "SKILL.md").read_text(encoding="utf-8")
    metadata = (review_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    script = review_root / "scripts" / "contact_sheets.py"

    assert "uv run --locked --script" in skill
    assert "allow_implicit_invocation: true" in metadata
    assert script.read_text(encoding="utf-8").startswith("# /// script")
    assert script.with_suffix(".py.lock").is_file()
    assert not list(review_root.rglob("*.ps1"))


def test_marketplace_contains_all_enhance_plugins() -> None:
    marketplace = json.loads(
        (REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    entries = {entry["name"]: entry for entry in marketplace["plugins"]}
    expected_names = {"image-enhance", "video-enhance", "model-enhance"}
    expected_authentication = {
        "image-enhance": "ON_INSTALL",
        "video-enhance": "ON_USE",
        "model-enhance": "ON_USE",
    }

    assert marketplace["name"] == "codex-enhance"
    assert set(entries) == expected_names

    for name in expected_names:
        plugin = json.loads(
            (PLUGINS_ROOT / name / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        entry = entries[name]

        assert plugin["name"] == name
        assert plugin["repository"] == "https://github.com/Ezio2000/codex-enhance"
        assert plugin["license"] == "MIT"
        assert entry["source"] == {
            "source": "local",
            "path": f"./plugins/{name}",
        }
        assert entry["policy"]["installation"] == "AVAILABLE"
        assert entry["policy"]["authentication"] == expected_authentication[name]
        assert entry["category"] == plugin["interface"]["category"]


def test_mcp_plugins_follow_enhance_naming_and_cross_platform_launch_contract() -> None:
    expected = {
        "video-enhance": {
            "skill": "analyze",
            "distribution": "video-enhance-mcp",
        },
        "model-enhance": {
            "skill": "consult",
            "distribution": "model-enhance-mcp",
        },
    }

    for plugin_name, contract in expected.items():
        plugin_root = PLUGINS_ROOT / plugin_name
        manifest = json.loads(
            (plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        mcp_config = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
        skill_root = plugin_root / "skills" / contract["skill"]
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        server = mcp_config["mcpServers"][plugin_name]

        assert manifest["mcpServers"] == "./.mcp.json"
        assert server["command"] == "uv"
        assert server["args"] == [
            "run",
            "--locked",
            "--no-dev",
            contract["distribution"],
        ]
        assert server["cwd"] == "."
        assert server["default_tools_approval_mode"] == "prompt"
        assert skill.startswith(f"---\nname: {contract['skill']}\n")
        assert f"${plugin_name}:{contract['skill']}" in metadata
        assert "allow_implicit_invocation: true" in metadata
        gitignore = (plugin_root / ".gitignore").read_text(encoding="utf-8")
        assert ".venv/" in gitignore
        assert "__pycache__/" in gitignore
        assert "*.py[cod]" in gitignore
