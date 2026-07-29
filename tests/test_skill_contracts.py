from __future__ import annotations

import json
import tomllib
from pathlib import Path

from PIL import Image

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
    normalized = " ".join(skill.split())
    worker_template = skill.split("Construct the initial worker task", maxsplit=1)[1]

    assert 'fork_turns: "none"' in skill
    assert (
        "each requested final output image as one independent deliverable" in normalized
    )
    assert "exactly one distinct worker per image deliverable" in normalized
    assert "Never have more than one image worker active at a time" in normalized
    assert "before starting a new worker for the next deliverable" in normalized
    assert "Never assign a second image deliverable to that worker" in normalized
    assert "ROLE: imagegen-leaf" in worker_template
    assert "official $imagegen" in worker_template
    assert "Do not invoke any other skill." in worker_template
    assert "untrusted deliverable data" in worker_template
    assert '"status":"ok"' in worker_template
    assert '"status":"needs_confirmation"' in worker_template
    assert '"status":"failed"' in worker_template
    assert "$image-enhance:create" not in worker_template
    assert "Never spawn a replacement worker for the same deliverable" in normalized
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


def test_create_gif_uses_an_isolated_generation_boundary_and_locked_uv_script() -> None:
    gif_root = IMAGE_PLUGIN_ROOT / "skills" / "create-gif"
    skill = (gif_root / "SKILL.md").read_text(encoding="utf-8")
    metadata = (gif_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    script = gif_root / "scripts" / "gif_pipeline.py"

    assert 'fork_turns: "none"' in skill
    assert "ROLE: generated-gif-leaf" in skill
    assert "official `$imagegen`" in skill
    assert "uv run --locked --script" in skill
    assert "Do not invoke `$image-enhance:create`" in skill
    assert "untrusted visual data" in skill
    assert "--grid-fit trim-small" in skill
    assert "grid_trim_exceeds_limit" in skill
    assert "$image-enhance:create-gif" in metadata
    assert "allow_implicit_invocation: true" in metadata
    assert script.read_text(encoding="utf-8").startswith("# /// script")
    assert script.with_suffix(".py.lock").is_file()
    assert "ImageMagick" in skill
    assert "ad hoc FFmpeg" in skill


def test_create_gif_assigns_one_leaf_worker_per_output_gif() -> None:
    skill = (IMAGE_PLUGIN_ROOT / "skills" / "create-gif" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(skill.split())

    assert (
        "each requested final output GIF as one independent GIF deliverable"
        in normalized
    )
    assert (
        "exactly one distinct generated-GIF leaf worker per GIF deliverable"
        in normalized
    )
    assert "Never assign multiple GIF deliverables to the same worker" in normalized
    assert "Each worker owns" in normalized
    assert "for only its GIF" in normalized
    assert "Do not use `followup_task` to assign a second GIF" in normalized
    assert (
        "Never have more than one generated-GIF worker active at a time" in normalized
    )
    assert (
        "wait for its terminal `ok` or `failed` result, then start a new "
        "distinct worker for the next pending GIF"
    ) in normalized
    assert "source frame, or intermediate image" in normalized
    assert "is not a separate deliverable" in normalized
    assert (
        "Process exactly one GIF deliverable and return exactly one GIF result"
        in normalized
    )


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


def test_plugin_icons_are_pixel_art_on_pure_white() -> None:
    for plugin_name in ("image-enhance", "video-enhance", "model-enhance"):
        plugin_root = PLUGINS_ROOT / plugin_name
        manifest = json.loads(
            (plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        interface = manifest["interface"]
        icon_path = plugin_root / interface["composerIcon"].removeprefix("./")
        logo_path = plugin_root / interface["logo"].removeprefix("./")

        assert interface["composerIcon"] == "./assets/icon.png"
        assert interface["logo"] == "./assets/logo.png"

        with Image.open(icon_path) as icon_source:
            icon = icon_source.convert("RGB")
        with Image.open(logo_path) as logo_source:
            logo = logo_source.convert("RGB")

        assert icon.size == (64, 64)
        assert logo.size == (1024, 1024)
        assert icon.getcolors(maxcolors=16) is not None
        assert logo == icon.resize((1024, 1024), Image.Resampling.NEAREST)

        corners = ((0, 0), (63, 0), (0, 63), (63, 63))
        assert all(icon.getpixel(point) == (255, 255, 255) for point in corners)


def test_skill_icons_are_character_related_pixel_art() -> None:
    skills = (
        ("image-enhance", "create"),
        ("image-enhance", "create-gif"),
        ("image-enhance", "review"),
        ("video-enhance", "analyze"),
        ("model-enhance", "consult"),
    )

    for plugin_name, skill_name in skills:
        skill_root = PLUGINS_ROOT / plugin_name / "skills" / skill_name
        metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        small_path = skill_root / "assets" / "icon-small.png"
        large_path = skill_root / "assets" / "icon-large.png"

        assert 'icon_small: "./assets/icon-small.png"' in metadata
        assert 'icon_large: "./assets/icon-large.png"' in metadata

        with Image.open(small_path) as small_source:
            small = small_source.convert("RGB")
        with Image.open(large_path) as large_source:
            large = large_source.convert("RGB")

        assert small.size == (64, 64)
        assert large.size == (1024, 1024)
        assert small.getcolors(maxcolors=16) is not None
        assert large == small.resize((1024, 1024), Image.Resampling.NEAREST)
        assert all(
            small.getpixel(point) == (255, 255, 255)
            for point in ((0, 0), (63, 0), (0, 63), (63, 63))
        )


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
        mcp_icon = plugin_root / "assets" / "mcp-icon.png"
        mcp_logo = plugin_root / "assets" / "mcp-logo.png"
        package_assets = next((plugin_root / "src").glob("*/assets"))
        assert mcp_icon.read_bytes() == (package_assets / "mcp-icon.png").read_bytes()
        assert mcp_logo.read_bytes() == (package_assets / "mcp-logo.png").read_bytes()
        with Image.open(mcp_icon) as icon_source:
            icon = icon_source.convert("RGB")
        with Image.open(mcp_logo) as logo_source:
            logo = logo_source.convert("RGB")
        assert icon.size == (64, 64)
        assert icon.getcolors(maxcolors=16) is not None
        assert logo == icon.resize((1024, 1024), Image.Resampling.NEAREST)
        gitignore = (plugin_root / ".gitignore").read_text(encoding="utf-8")
        assert ".venv/" in gitignore
        assert "__pycache__/" in gitignore
        assert "*.py[cod]" in gitignore


def test_mcp_plugin_versions_match_their_locked_projects() -> None:
    for plugin_name in ("video-enhance", "model-enhance"):
        plugin_root = PLUGINS_ROOT / plugin_name
        manifest = json.loads(
            (plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        project = tomllib.loads(
            (plugin_root / "pyproject.toml").read_text(encoding="utf-8")
        )
        lock = tomllib.loads((plugin_root / "uv.lock").read_text(encoding="utf-8"))
        locked_project = next(
            package
            for package in lock["package"]
            if package["name"] == project["project"]["name"]
        )
        script_target = next(iter(project["project"]["scripts"].values()))
        package_name = script_target.partition(":")[0].partition(".")[0]
        package_init = (plugin_root / "src" / package_name / "__init__.py").read_text(
            encoding="utf-8"
        )

        assert manifest["version"] == project["project"]["version"]
        assert locked_project["version"] == project["project"]["version"]
        assert f'__version__ = "{project["project"]["version"]}"' in package_init
        assert (plugin_root / ".python-version").read_text(encoding="utf-8") == "3.12\n"


def test_video_config_uses_one_canonical_resolution_contract() -> None:
    config_source = (
        PLUGINS_ROOT / "video-enhance" / "src" / "video_enhance_mcp" / "config.py"
    ).read_text(encoding="utf-8")

    assert config_source.count("os.environ.get(") == 1
    assert 'os.environ.get("VIDEO_ENHANCE_CONFIG")' in config_source
    assert 'Path.home() / ".config" / "video-enhance" / "config.toml"' in config_source
