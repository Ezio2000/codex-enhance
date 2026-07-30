from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = REPOSITORY_ROOT / "plugins"
IMAGE_PLUGIN_ROOT = PLUGINS_ROOT / "image-enhance"
CODE_PLUGIN_ROOT = PLUGINS_ROOT / "code-enhance"


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
    expected_names = {
        "image-enhance",
        "video-enhance",
        "model-enhance",
        "code-enhance",
    }
    expected_authentication = {
        "image-enhance": "ON_INSTALL",
        "video-enhance": "ON_USE",
        "model-enhance": "ON_USE",
        "code-enhance": "ON_INSTALL",
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
    for plugin_name in (
        "image-enhance",
        "video-enhance",
        "model-enhance",
        "code-enhance",
    ):
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
        ("code-enhance", "review"),
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


def test_code_review_is_explicit_read_only_and_natural_language_only() -> None:
    skill_root = CODE_PLUGIN_ROOT / "skills" / "review"
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    manifest = json.loads(
        (CODE_PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    public_surfaces = "\n".join(
        [
            readme,
            "\n".join(manifest["interface"]["defaultPrompt"]),
            metadata,
            skill,
        ]
    )
    documented_examples = re.findall(
        r"```text\n(\$code-enhance:review[^\n]+)\n```",
        f"{readme}\n{skill}",
    )

    assert "allow_implicit_invocation: false" in metadata
    assert re.fullmatch(
        r"0\.1\.0\+codex\.\d{14}",
        manifest["version"],
    )
    assert manifest["interface"]["displayName"] == "Code Enhance"
    assert manifest["interface"]["category"] == "Developer Tools"
    assert not {"mcpServers", "hooks", "apps"} & manifest.keys()
    assert (
        'default_prompt: "Use $code-enhance:review to '
        "review my current development changes"
    ) in metadata
    assert "strictly read-only" in " ".join(skill.lower().split())
    assert "bare" in skill.lower()
    assert "clarif" in skill.lower()
    assert all(
        prompt.startswith("Use $code-enhance:review to ")
        for prompt in manifest["interface"]["defaultPrompt"]
    )
    assert len(documented_examples) >= 8
    assert all(
        len(example.removeprefix("$code-enhance:review").strip()) >= 10
        and example.rstrip().endswith((".", "?", "!", "。", "？", "！"))
        for example in documented_examples
    )
    assert all(
        forbidden not in public_surfaces
        for forbidden in (
            "$code-enhance:review repo",
            "$code-enhance:review latest",
            "$code-enhance:review versions",
            "$code-enhance:review --",
        )
    )


def test_code_review_has_independent_finders_and_fresh_validation() -> None:
    review_root = CODE_PLUGIN_ROOT / "skills" / "review"
    skill = (review_root / "SKILL.md").read_text(encoding="utf-8")
    orchestration = (review_root / "references" / "orchestration.md").read_text(
        encoding="utf-8"
    )
    contract = (review_root / "references" / "finding-contract.md").read_text(
        encoding="utf-8"
    )
    pattern_fit = (review_root / "references" / "pattern-fit.md").read_text(
        encoding="utf-8"
    )
    combined = "\n".join((skill, orchestration, contract, pattern_fit))

    assert 'fork_turns: "none"' in combined
    assert "Behavior & Safety" in combined
    assert "Code Craft" in combined
    assert "Architecture & Evolution" in combined
    assert "validator" in combined.lower()
    assert "no spawning" in combined.lower()
    assert "no skill invocation" in combined.lower()
    assert "neutral relay" in combined.lower()
    assert "direct child-thread budget" in combined.lower()
    assert "YAGNI" in combined
    assert "Confirmed" in combined
    assert "Supported" in combined
    assert all(
        column in combined
        for column in (
            "ID",
            "Priority",
            "Dimension",
            "Location",
            "Verified issue",
            "Failure/change cost",
            "Evidence",
            "Minimal improvement",
            "Pattern judgment",
            "Change timing",
            "Confidence",
        )
    )


def test_code_review_scope_helper_is_uv_locked_and_dependency_free() -> None:
    review_root = CODE_PLUGIN_ROOT / "skills" / "review"
    script = review_root / "scripts" / "review_scope.py"

    assert script.read_text(encoding="utf-8").startswith("# /// script")
    assert script.with_suffix(".py.lock").is_file()
    assert not list(review_root.rglob("*.ps1"))


def test_code_review_rubric_covers_false_positive_and_pattern_scenarios() -> None:
    review_root = CODE_PLUGIN_ROOT / "skills" / "review"
    rubric = (review_root / "references" / "review-rubric.md").read_text(
        encoding="utf-8"
    )
    pattern_fit = (review_root / "references" / "pattern-fit.md").read_text(
        encoding="utf-8"
    )
    contract = (review_root / "references" / "finding-contract.md").read_text(
        encoding="utf-8"
    )
    combined = "\n".join((rubric, pattern_fit, contract))

    assert "Zero is valid" in combined
    assert "attack surface" in combined
    assert "hot path" in combined
    assert "accidental duplication" in combined
    assert "Repeated switch" in combined
    assert "Single-implementation interface" in combined
    assert "One-product Factory" in combined
    assert "Pass-through Wrapper" in combined
    assert "Adapter" in combined
    assert all(
        judgment in combined
        for judgment in ("appropriate", "missing", "misused", "overused")
    )


def test_code_review_uses_strict_per_check_handbooks_and_auditable_ledgers() -> None:
    review_root = CODE_PLUGIN_ROOT / "skills" / "review"
    references = review_root / "references"
    skill = (review_root / "SKILL.md").read_text(encoding="utf-8")
    orchestration = (references / "orchestration.md").read_text(encoding="utf-8")
    rubric = (references / "review-rubric.md").read_text(encoding="utf-8")
    contract = (references / "finding-contract.md").read_text(encoding="utf-8")
    pattern_fit = (references / "pattern-fit.md").read_text(encoding="utf-8")
    normalized_skill = " ".join(skill.split())
    normalized_orchestration = " ".join(orchestration.split())
    normalized_contract = " ".join(contract.split())
    normalized_pattern_fit = " ".join(pattern_fit.split())
    handbooks = {
        "BS": (references / "finder-behavior-safety.md").read_text(encoding="utf-8"),
        "CC": (references / "finder-code-craft.md").read_text(encoding="utf-8"),
        "AE": (references / "finder-architecture-evolution.md").read_text(
            encoding="utf-8"
        ),
    }

    for filename in (
        "finder-behavior-safety.md",
        "finder-code-craft.md",
        "finder-architecture-evolution.md",
    ):
        assert f"](references/{filename})" in skill

    expected_ids = {
        "BS": {f"BS-{number:02d}" for number in range(1, 13)},
        "CC": {f"CC-{number:02d}" for number in range(1, 13)},
        "AE": {f"AE-{number:02d}" for number in range(1, 14)},
    }
    all_ids: list[str] = []
    for prefix, handbook in handbooks.items():
        matrix_ids = re.findall(
            rf"^\| `({prefix}-\d{{2}})\b",
            handbook,
            flags=re.MULTILINE,
        )
        assert set(matrix_ids) == expected_ids[prefix]
        assert len(matrix_ids) == len(set(matrix_ids))
        all_ids.extend(matrix_ids)
        assert all(
            heading in handbook
            for heading in (
                "Applicability and minimum context",
                "Required inspection",
                "Candidate evidence",
                "Disconfirming evidence",
                "Minimum verification",
                "Ledger payload",
            )
        )
        assert "inspection_ledger" in handbook
        assert "checked_clear | candidate | not_applicable | blocked" in handbook

    assert len(all_ids) == len(set(all_ids))
    surface_ids = set(
        re.findall(r"^\| `(BS-S\d{2})` \|", handbooks["BS"], flags=re.MULTILINE)
    )
    assert surface_ids == {f"BS-S{number:02d}" for number in range(1, 8)}
    assert all(
        field in contract
        for field in (
            "inspection_id",
            "check_id",
            "applicability_triggers_checked",
            "artifacts_searched",
            "files_and_symbols_read",
            "source_extents_or_objects_read",
            "context_read",
            "inspection_action",
            "disconfirming_evidence",
            "verification_attempts",
            "scope_origin",
            "proof_chain",
            "independent_context_read",
            "independent_reconstruction",
            "falsification_hypotheses",
            "falsification_attempts",
            "residual_assumptions",
            "problem_verdict",
            "pattern_action",
            "introduction_or_expansion_gates",
            "removal_or_collapse_gates",
            "keep_evidence",
            "represented_need_absent_obsolete_or_not_served_by_participants",
            "no_required_boundary_is_lost_or_replacement_improves_it",
        )
    )
    assert "no inspection record is blocked" in orchestration
    assert "Zero candidates does not relax this formula" in normalized_orchestration
    assert "complete handbook ID set" in orchestration
    assert "Generic claims such as" in normalized_orchestration
    assert "must not fill the missing proof" in normalized_orchestration
    assert "surface_inventory" in orchestration
    assert "source extents/objects" in orchestration
    assert "source_extents_or_objects_read" in orchestration
    assert (
        "every deduplicated candidate has an independent Validator result"
        in normalized_orchestration
    )
    assert "A filename, summary, diff hunk" in normalized_skill
    assert "Load references by workflow stage" in skill
    assert "Before returning any candidate" in skill
    assert "before independent validation or adjudication" in normalized_skill
    assert "V-01 Behavior" in rubric
    assert "V-07 Test gap" in rubric
    assert "D-01 Scope" in rubric
    assert "D-08 Traceability" in rubric
    assert "problem_verdict" in rubric
    assert all(
        proof_chain in rubric
        for proof_chain in (
            "Pattern introduce or expand",
            "Pattern keep",
            "Pattern remove or collapse",
            "Pattern replace",
        )
    )
    assert "untrusted review data" in normalized_skill
    assert "candidate funnel counts" in normalized_contract
    assert "missing, blocked, and unvalidated" in normalized_contract

    assert all(
        pattern in pattern_fit
        for pattern in (
            "**Adapter**",
            "**Strategy**",
            "**State**",
            "**Factory**",
            "**Builder**",
            "**Command**",
            "**Observer or event**",
            "**Decorator**",
            "**Proxy**",
            "**Facade**",
            "**Repository**",
            "**Template Method or base class**",
            "**Dependency injection boundary**",
            "**CQRS, event sourcing, saga, or other system-level pattern**",
        )
    )
    assert "no universal threshold decides the result" in normalized_pattern_fit
    assert (
        "underlying problem and the named-pattern judgment are separate"
        in normalized_pattern_fit
    )
    assert "construction/lifecycle axis" in normalized_pattern_fit
    assert all(
        action in pattern_fit
        for action in ("introduce", "expand", "remove", "collapse", "replace", "keep")
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
