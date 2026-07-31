from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path

from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = REPOSITORY_ROOT / "plugins"
IMAGE_PLUGIN_ROOT = PLUGINS_ROOT / "image-enhance"
CODE_PLUGIN_ROOT = PLUGINS_ROOT / "code-enhance"
CODE_SPECIALTIES = (
    "beautify",
    "simplify",
    "standardize",
    "design",
    "security",
)
CODE_SPECIALTY_CHECK_IDS = {
    "beautify": {f"BF-{number:02d}" for number in range(1, 6)},
    "simplify": {f"SM-{number:02d}" for number in range(1, 10)},
    "standardize": {f"ST-{number:02d}" for number in range(1, 9)},
    "design": {f"DS-{number:02d}" for number in range(1, 14)},
    "security": {f"SE-{number:02d}" for number in range(1, 10)},
}


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
        ("video-enhance", "create"),
        ("video-enhance", "analyze"),
        ("model-enhance", "consult"),
        *(("code-enhance", skill_name) for skill_name in CODE_SPECIALTIES),
    )
    code_skill_hashes: dict[str, str] = {}

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
        expected_large = small.resize((1024, 1024), Image.Resampling.NEAREST)
        assert large.tobytes() == expected_large.tobytes()
        assert all(
            small.getpixel(point) == (255, 255, 255)
            for point in ((0, 0), (63, 0), (0, 63), (63, 63))
        )
        if plugin_name == "code-enhance":
            code_skill_hashes[skill_name] = hashlib.sha256(small.tobytes()).hexdigest()

    assert set(code_skill_hashes) == set(CODE_SPECIALTIES)
    assert len(set(code_skill_hashes.values())) == len(CODE_SPECIALTIES)


def test_code_enhance_exposes_only_five_explicit_read_only_specialties() -> None:
    skills_root = CODE_PLUGIN_ROOT / "skills"
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    manifest = json.loads(
        (CODE_PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    skill_directories = {
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    plugin_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in CODE_PLUGIN_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".json", ".md", ".py", ".yaml"}
    )

    assert skill_directories == set(CODE_SPECIALTIES)
    assert not (skills_root / "review").exists()
    assert re.fullmatch(
        r"0\.2\.0\+codex\.\d{14}",
        manifest["version"],
    )
    assert manifest["interface"]["displayName"] == "Code Enhance"
    assert manifest["interface"]["category"] == "Developer Tools"
    assert not {"mcpServers", "hooks", "apps"} & manifest.keys()
    assert "$code-enhance:review" not in f"{readme}\n{plugin_text}"
    assert all(
        legacy not in plugin_text
        for legacy in (
            "Behavior & Safety",
            "Code Craft",
            "Architecture & Evolution",
            "BS-01",
            "CC-01",
            "AE-01",
        )
    )

    default_prompts = manifest["interface"]["defaultPrompt"]
    assert 1 <= len(default_prompts) <= 3
    manifest_prompt_skills: list[str] = []
    for prompt in default_prompts:
        assert len(prompt) <= 128
        invocations = re.findall(r"\$code-enhance:([a-z-]+)", prompt)
        assert 1 <= len(invocations) <= 2
        if len(invocations) == 1:
            assert prompt.startswith(f"Use $code-enhance:{invocations[0]} to ")
        else:
            assert prompt.startswith(
                f"Use $code-enhance:{invocations[0]} and "
                f"$code-enhance:{invocations[1]} to "
            )
        manifest_prompt_skills.extend(invocations)
    assert tuple(manifest_prompt_skills) == CODE_SPECIALTIES

    for skill_name in CODE_SPECIALTIES:
        skill_root = skills_root / skill_name
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        normalized = " ".join(skill.lower().split())

        assert re.search(rf"^name: {skill_name}$", skill, flags=re.MULTILINE)
        assert "allow_implicit_invocation: false" in metadata
        assert re.search(
            rf'^\s+default_prompt: "Use \$code-enhance:{skill_name}\b',
            metadata,
            flags=re.MULTILINE,
        )
        assert re.findall(r"\$code-enhance:([a-z-]+)", metadata) == [skill_name]
        assert "strictly read-only" in normalized
        assert "natural-language request" in normalized
        assert "exactly one concise" in normalized
        assert "../../scripts/review_scope.py" in skill
        assert "directory" in normalized
        assert "current development" in normalized
        assert any(
            marker in normalized
            for marker in ("historical comparison", "comparisons between named")
        )
        assert any(
            marker in normalized
            for marker in (
                "ordinary correctness",
                "behavior-correctness",
                "exclude correctness",
            )
        )
        assert all(
            forbidden not in f"{skill}\n{metadata}"
            for forbidden in (
                f"$code-enhance:{skill_name} repo",
                f"$code-enhance:{skill_name} latest",
                f"$code-enhance:{skill_name} versions",
                f"$code-enhance:{skill_name} --",
            )
        )


def test_code_enhance_shares_coverage_deduplication_and_fresh_validation() -> None:
    references = CODE_PLUGIN_ROOT / "references"
    orchestration = (references / "orchestration.md").read_text(encoding="utf-8")
    contract = (references / "finding-contract.md").read_text(encoding="utf-8")
    rubric = (references / "review-rubric.md").read_text(encoding="utf-8")
    normalized_orchestration = " ".join(orchestration.split())
    normalized_contract = " ".join(contract.split())
    combined = "\n".join((orchestration, contract, rubric))

    assert "neutral context pack" in orchestration
    assert "resolve scope once" in orchestration.lower()
    assert 'fork_turns: "none"' in orchestration
    assert "fresh Validator" in orchestration
    assert "cannot spawn agents" in orchestration
    assert "invoke Skills" in orchestration
    assert "root cause + affected symbol/boundary/contract + change axis" in combined
    assert "primary_review_kind" in combined
    assert "related_review_kinds" in combined
    assert "Exactly one `primary_review_kind` is required" in contract
    assert "A single root cause produces one candidate" in orchestration
    assert "Zero candidates does not relax this formula" in normalized_orchestration
    assert (
        "A candidate without a fresh Validator result is not reportable"
        in normalized_orchestration
    )
    assert "ordinary behavior correctness" in contract.lower()
    assert "not independently reportable" in normalized_contract
    assert all(f"V-{number:02d}" in rubric for number in range(1, 9))
    assert all(
        field in contract
        for field in (
            "inspection_id",
            "review_kind",
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
            "primary_review_kind",
            "related_review_kinds",
            "independent_context_read",
            "independent_reconstruction",
            "falsification_hypotheses",
            "falsification_attempts",
            "residual_assumptions",
            "specialty_gate_results",
            "verdict: Confirmed | Supported | Rejected",
        )
    )

    for skill_name in CODE_SPECIALTIES:
        skill = (CODE_PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "](../../references/orchestration.md)" in skill
        assert "](../../references/finding-contract.md)" in skill
        assert "](../../references/review-rubric.md)" in skill
        assert 'fork_turns: "none"' in skill
        assert re.search(r"fresh (?:isolated )?Validator", skill, flags=re.IGNORECASE)
        assert "primary_review_kind" in skill
        assert "related_review_kinds" in skill


def test_code_enhance_scope_helper_is_shared_uv_locked_and_dependency_free() -> None:
    script = CODE_PLUGIN_ROOT / "scripts" / "review_scope.py"

    assert script == (
        REPOSITORY_ROOT / "plugins" / "code-enhance" / "scripts" / "review_scope.py"
    )
    assert script.read_text(encoding="utf-8").startswith("# /// script")
    assert script.with_suffix(".py.lock").is_file()
    assert not list(CODE_PLUGIN_ROOT.rglob("*.ps1"))
    for skill_name in CODE_SPECIALTIES:
        skill = (CODE_PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "../../scripts/review_scope.py" in skill


def test_code_enhance_handbooks_have_unique_complete_check_matrices() -> None:
    all_ids: list[str] = []
    for skill_name, expected_ids in CODE_SPECIALTY_CHECK_IDS.items():
        handbook = (
            CODE_PLUGIN_ROOT / "skills" / skill_name / "references" / "handbook.md"
        ).read_text(encoding="utf-8")
        handbook_ids = re.findall(
            r"^(?:#{2,4}\s+|\|\s+`)((?:BF|SM|ST|DS|SE)-(?:S)?\d{2})\b",
            handbook,
            flags=re.MULTILINE,
        )

        expected_with_supplements = set(expected_ids)
        if skill_name == "security":
            expected_with_supplements |= {f"SE-S{number:02d}" for number in range(1, 8)}
        assert set(handbook_ids) == expected_with_supplements
        assert len(handbook_ids) == len(set(handbook_ids))
        all_ids.extend(handbook_ids)
        assert "checked_clear | candidate | not_applicable | blocked" in handbook
        assert "blocked" in handbook
    assert len(all_ids) == len(set(all_ids))


def test_code_enhance_design_alone_owns_pattern_fitness_guidance() -> None:
    pattern_fit_path = (
        CODE_PLUGIN_ROOT / "skills" / "design" / "references" / "pattern-fit.md"
    )
    pattern_files = set(CODE_PLUGIN_ROOT.glob("skills/*/references/pattern-fit.md"))

    assert pattern_files == {pattern_fit_path}
    pattern_fit = pattern_fit_path.read_text(encoding="utf-8")
    design_skill = (CODE_PLUGIN_ROOT / "skills" / "design" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "pattern-fit.md" in design_skill
    for skill_name in set(CODE_SPECIALTIES) - {"design"}:
        specialty_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (CODE_PLUGIN_ROOT / "skills" / skill_name).rglob("*.md")
        )
        assert "pattern-fit.md" not in specialty_text

    assert "Mandatory three-option comparison" in pattern_fit
    assert "underlying problem and the named-pattern judgment are separate" in (
        " ".join(pattern_fit.split())
    )
    assert all(
        action in pattern_fit
        for action in ("introduce", "expand", "remove", "collapse", "replace", "keep")
    )


def test_code_enhance_performance_and_security_evidence_gates_are_strict() -> None:
    rubric = (CODE_PLUGIN_ROOT / "references" / "review-rubric.md").read_text(
        encoding="utf-8"
    )
    standardize = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            CODE_PLUGIN_ROOT / "skills" / "standardize" / "SKILL.md",
            CODE_PLUGIN_ROOT / "skills" / "standardize" / "references" / "handbook.md",
        )
    )
    security = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            CODE_PLUGIN_ROOT / "skills" / "security" / "SKILL.md",
            CODE_PLUGIN_ROOT / "skills" / "security" / "references" / "handbook.md",
        )
    )
    normalized_standardize = " ".join(standardize.split())
    normalized_security = " ".join(security.split())

    assert "ordinary correctness" in rubric
    assert all(
        evidence in normalized_standardize
        for evidence in (
            "reachable workload",
            "before/after cost model",
            "benchmark",
            "profile",
            "query plan",
            "material user, latency, throughput, memory, I/O, or capacity impact",
        )
    )
    assert "might be faster" in normalized_standardize
    assert all(
        link in normalized_security
        for link in (
            "attacker capability",
            "attacker-controlled source",
            "missing or bypassable controls",
            "sensitive operation, sink, or asset",
            "practical confidentiality, integrity, or availability impact",
        )
    )
    assert "When any link is unknown or merely hypothetical" in normalized_security


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


def test_video_create_uses_one_serial_computer_use_worker_per_video() -> None:
    skill_root = PLUGINS_ROOT / "video-enhance" / "skills" / "create"
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    runbook = (skill_root / "references" / "google-flow.md").read_text(encoding="utf-8")
    metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    normalized = " ".join(skill.split())
    normalized_runbook = " ".join(runbook.split())
    worker_template = skill.split("Construct the worker task", maxsplit=1)[1]

    assert 'fork_turns: "none"' in skill
    assert "one distinct leaf worker per video deliverable" in normalized
    assert "Never have more than one video worker active at a time" in normalized
    assert "Never assign a second video to an existing worker" in normalized
    assert "Never spawn a replacement worker" in normalized
    assert "Never call Computer Use, `node_repl`, or operate Safari" in normalized
    assert "Force every Flow submission to `x1`" in normalized
    assert "ROLE: video-create-leaf" in worker_template
    assert "$computer-use:computer-use" in worker_template
    assert "Use node_repl" in worker_template
    assert "Do not spawn, delegate" in worker_template
    assert "needs_budget" in worker_template
    assert "send_message" in worker_template
    assert "followup_task" in skill
    assert "MAX_ATTEMPTS_PER_SEGMENT: 2" in worker_template
    assert "video_inspect" in worker_template
    assert "allow_implicit_invocation: true" in metadata
    assert "$video-enhance:create google-flow" in metadata

    assert "derive new element indexes" in normalized_runbook
    assert "Never reuse an index from an older state" in normalized_runbook
    assert (
        "Do not use a stored list of options or a remembered price"
        in normalized_runbook
    )
    assert "Read the complete visible phrase" in normalized_runbook
    assert "ITEM_CREDIT_CAP" in normalized_runbook
    assert "INVOCATION_REMAINING_CREDITS" in normalized_runbook
    assert "Do not purchase credits" in normalized_runbook
    assert "After 20 minutes" in normalized_runbook
    assert "x2" not in runbook
    assert "x3" not in runbook
    assert "x4" not in runbook
    assert not re.search(r"element_index\\s*:\\s*\\d+", f"{skill}\n{runbook}")
    assert not re.search(r"\\b(?:15|20|25|30|40|100) credits\\b", runbook)


def test_video_create_interface_and_input_modes_are_explicit() -> None:
    skill = (
        PLUGINS_ROOT / "video-enhance" / "skills" / "create" / "SKILL.md"
    ).read_text(encoding="utf-8")
    normalized = " ".join(skill.split())

    assert "Require a provider immediately after the skill invocation" in normalized
    assert "Support exactly `google-flow`" in normalized
    assert "If the provider is missing, ask one concise question" in normalized
    assert "If it is unsupported, report the supported provider and stop" in normalized
    for default in (
        "`model=omni-flash`",
        "`duration=10s`",
        "`aspect_ratio=16:9`",
        "`count=1`",
        "`resolution=auto`",
    ):
        assert default in skill
    assert "Ingredient mode and frame mode are mutually exclusive" in normalized
    assert "Never discover and upload an unmentioned file" in normalized
    assert "Never overwrite an existing file" in normalized
    assert "prefer a displayed 1080p download that adds zero credits" in normalized
    assert "otherwise use the original download" in normalized


def test_video_create_failure_and_pause_contracts_cover_safe_boundaries() -> None:
    skill_root = PLUGINS_ROOT / "video-enhance" / "skills" / "create"
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    runbook = (skill_root / "references" / "google-flow.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.split())
    normalized_runbook = " ".join(runbook.split())

    assert "first worker return the live quote as `needs_budget`" in normalized
    assert "both caps set to known integers" in normalized
    assert "either remaining cap is unknown" in normalized
    assert "If the skill or node_repl is unavailable, return failed" in normalized
    assert "currently visible alternatives" in normalized_runbook
    assert "Never silently change model, duration, ratio, mode, or count" in (
        normalized_runbook
    )
    assert "return `needs_user_action`" in normalized_runbook
    for intervention in ("login", "password", "2FA", "CAPTCHA", "legal terms"):
        assert intervention in normalized_runbook
    assert "Retry each segment automatically at most once" in normalized
    assert "Never retry for a subjective quality preference" in normalized
    assert "corrupt download" in normalized
    assert "duration/dimension/container mismatch" in normalized
    assert "After 20 minutes" in normalized
    assert "return pending without cancelling or deleting the remote job" in normalized
    assert "actual_credit_delta` to `null`" in normalized_runbook
    assert "temporary hard link" in normalized
    assert "same device and inode" in normalized
    assert "Do not change the user's global configuration" in normalized_runbook
    assert "Never spawn a replacement worker" in normalized


def test_video_create_stitches_ordered_segments_in_the_same_worker() -> None:
    skill_root = PLUGINS_ROOT / "video-enhance" / "skills" / "create"
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    stitching = (skill_root / "references" / "stitching.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.split())
    normalized_stitching = " ".join(stitching.split())

    assert "Treat `count` as the number of final video deliverables" in normalized
    assert "Treat `segments` as the number of ordered Flow clips" in normalized
    assert "`count=1 segments=2 stitch=true`" in normalized
    assert "never turn the two segments into two workers" in normalized
    assert "A stitched deliverable remains one final video and one worker" in normalized
    assert "submits each of its ordered segments separately as `x1`" in normalized
    assert "Local stitching consumes no Flow credits" in normalized
    assert "hard-cut assembly" in normalized
    assert "do not stitch a partial final video" in normalized_stitching.lower()
    assert "MAX_ATTEMPTS_PER_SEGMENT: 2" in skill
    assert "scripts/stitch_videos.py" in stitching
    assert "Never use a shell glob to establish order" in normalized_stitching
    assert "verified stream-copy" in normalized_stitching
    assert "high-quality local H.264/AAC normalization" in normalized_stitching
    assert "frame extraction and stitching add zero" in normalized_stitching


def test_video_create_frame_chains_stitched_segments_for_continuity() -> None:
    skill_root = PLUGINS_ROOT / "video-enhance" / "skills" / "create"
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    stitching = (skill_root / "references" / "stitching.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.split())
    normalized_stitching = " ".join(stitching.split())

    assert "`continuity=frame-chain` when `stitch=true`" in normalized
    assert "final decoded frame into the next segment as its start frame" in normalized
    assert "scripts/extract_boundary_frame.py" in stitching
    assert "--position last" in stitching
    assert "authorized only as the next segment's `start_frame`" in normalized_stitching
    assert "Configure segment N+1 in frame mode with that exact PNG" in (
        normalized_stitching
    )
    assert "camera position, lens feel, framing, motion direction" in (
        normalized_stitching
    )
    assert "do not silently fall back to prompt-only continuity" in (
        normalized_stitching
    )
    assert "`continuity=explicit`" in stitching
    assert "`continuity=independent`" in stitching
    assert "--position first" in stitching
    assert "Do not spend credits on an automatic retry" in normalized_stitching
    assert "frame extraction and stitching add zero" in normalized_stitching


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
