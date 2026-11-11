"""Check the curated public inventory and fixed canary contract offline."""

from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_examples as checker  # noqa: E402


class PublicExamplesTests(unittest.TestCase):
    """Guard self-contained examples without any adapters or service credentials."""

    def test_all_examples_have_consistent_graphs(self) -> None:
        """Every catalog entry has a valid asset graph and fictitious input sample."""
        for name in sorted(checker.EXAMPLES):
            with self.subTest(example=name):
                example = ROOT / "examples" / name
                definition, pins, actions = checker.inspect_graph(
                    example / "workflow.yaml"
                )
                self.assertEqual(definition["id"], name)
                self.assertTrue(pins)
                self.assertTrue(actions)
                self.assertIsNotNone(checker.SEMVER.fullmatch(definition["version"]))
                for version in pins.values():
                    self.assertIsNotNone(checker.SEMVER.fullmatch(version))
                self.assertTrue((example / "README.md").is_file())
                sample = checker.load_yaml(example / "inputs.example.yaml")
                declared = definition.get("inputs", {})
                self.assertFalse(set(sample) - set(declared))
                required = {
                    key
                    for key, value in declared.items()
                    if value.get("required") and "default" not in value
                }
                self.assertTrue(required.issubset(sample))

    def test_canary_prompt_and_participants(self) -> None:
        """All six canary participants request the same fixed text explicitly."""
        example = ROOT / "examples" / "ai_agent_plugins_canary"
        document = yaml.safe_load((example / "workflow.yaml").read_text())
        self.assertEqual(document["version"], "0.1.3")
        self.assertEqual(document["plugins"]["ollama.cli"], "0.1.1")
        self.assertEqual(document["plugins"]["cursor.cli"], "0.1.0")
        self.assertEqual(document["network"]["mode"], "none")
        self.assertEqual(document["workspace"]["access"], "read_only")
        prompt = (example / "prompt.md").read_text().strip()
        steps = document["steps"]
        self.assertEqual(
            [step["id"] for step in steps],
            [
                "github_copilot_canary",
                "opencode_canary",
                "ollama_canary",
                "cursor_canary",
                "anthropic_canary",
                "openai_compatible_canary",
            ],
        )
        for step in steps:
            with self.subTest(participant=step["id"]):
                selected = document.get("profiles", {}).get(step.get("profile"), {})
                if selected:
                    self.assertEqual(selected["uses"], step["uses"])
                effective = {**selected, **step}
                effective["with"] = {**selected.get("with", {}), **step["with"]}
                if "prompt_file" in effective:
                    self.assertEqual(
                        (example / effective["prompt_file"]).read_text().strip(), prompt
                    )
                else:
                    self.assertEqual(
                        effective["with"]["messages"][0]["content"], prompt
                    )
                self.assertNotEqual(effective["network"]["mode"], "any")
                self.assertEqual(effective["network"]["max_redirects"], 0)

        self.assertNotIn("codex.cli", document["plugins"])
        self.assertNotIn("codex_model", document["inputs"])
        compatible = steps[-1]
        self.assertEqual(compatible["with"]["max_completion_tokens"], 64)
        self.assertNotIn("max_tokens", compatible["with"])
        self.assertEqual(
            compatible["with"]["secret_refs"], ["OPENAI_COMPATIBLE_API_KEY"]
        )
        self.assertEqual(
            compatible["network"]["allow_hosts"], ["openrouter.ai", "api.openai.com"]
        )
        self.assertEqual(compatible["network"]["allow_ports"], [443])
        self.assertTrue(compatible["network"]["tls_required"])
        self.assertEqual(
            compatible["with"]["base_url"], "{{inputs.openai_compatible_base_url}}"
        )

    def test_edge_completion_token_budget(self) -> None:
        """The advisory forwards its explicit completion-token budget unchanged."""
        flow = checker.load_yaml(ROOT / "examples/edge_fault_advisory/workflow.yaml")
        self.assertEqual(flow["version"], "0.1.0")
        step = next(step for step in flow["steps"] if step["id"] == "advise")
        self.assertEqual(step["with"]["max_completion_tokens"], 512)
        self.assertNotIn("max_tokens", step["with"])

    def test_validation_remediation_exits_on_pass_or_attempt_cap(self) -> None:
        """The loop consumes a named Boolean export; staged bookkeeping caps work."""
        module = checker.load_yaml(
            ROOT
            / "examples/cursor_ticket_delivery/modules"
            / "validation_remediation.module.yaml"
        )
        loop = next(
            step["loop"]
            for step in module["steps"]
            if step["id"] == "validation_remediation_loop"
        )
        self.assertEqual(
            loop["until"],
            "steps.run_validation_remediation_iteration.out.passed == true",
        )
        child = checker.load_yaml(
            ROOT
            / "examples/cursor_ticket_delivery/modules"
            / "validation_remediation_iteration.module.yaml"
        )
        self.assertEqual(
            child["outputs"]["passed"], "{{steps.validate_changes.out.passed}}"
        )
        self.assertIn("validation_attempt.py", str(child["steps"][0]["with"]["args"]))

    def test_model_invocations_use_bounded_supported_profiles(self) -> None:
        """CLI agents/OpenSpec opt in; shell stdout and native schemas remain exact."""
        agents = {"cursor.cli", "github.copilot.cli", "opencode.cli", "codex.cli"}
        for path in sorted((ROOT / "examples").rglob("*.yaml")):
            document = checker.load_yaml(path)
            for step in checker.walk(
                [document.get("steps", []), document.get("cleanup", [])]
            ):
                uses = step.get("uses", "")
                if not uses:
                    continue
                plugin = uses.split(":", 1)[1].split("/", 1)[0]
                selected = document.get("profiles", {}).get(step.get("profile"), {})
                if selected:
                    self.assertEqual(selected["uses"], uses)
                profile = {**selected.get("with", {}), **step.get("with", {})}
                for key, value in list(profile.items()):
                    if (
                        isinstance(value, str)
                        and value.startswith("{{context.")
                        and value.endswith("}}")
                    ):
                        name = value.removeprefix("{{context.").removesuffix("}}")
                        profile[key] = document["context"][name]
                with self.subTest(
                    path=str(path.relative_to(ROOT)), step=step.get("id")
                ):
                    if plugin in agents | {"openspec"}:
                        self.assertEqual(profile["output_mode"], "compact")
                        self.assertEqual(profile["max_context_file_bytes"], 65536)
                        self.assertEqual(profile["max_prompt_bytes"], 98304)
                    if plugin in agents:
                        self.assertEqual(profile["history_mode"], "invocation")
                    else:
                        self.assertNotIn("history_mode", profile)
                    if plugin == "ollama.cli":
                        self.assertEqual(profile["output_mode"], "compact")
                        self.assertEqual(profile["max_prompt_bytes"], 98304)
                        self.assertNotIn("max_context_file_bytes", profile)
                    if uses == "process:shell/exec":
                        self.assertNotIn("output_mode", profile)
                    if plugin in {"git.cli", "github.cli", "jira.rest"}:
                        self.assertEqual(profile["output_mode"], "compact")
                        self.assertNotIn("max_context_file_bytes", profile)
        edge = checker.load_yaml(ROOT / "examples/edge_fault_advisory/workflow.yaml")
        self.assertEqual(edge["steps"][0]["uses"], "process:shell/read_file")
        self.assertEqual(
            edge["steps"][0]["with"]["output_file"],
            {"$document": "diagnostic", "access": "write"},
        )
        canary = checker.load_yaml(
            ROOT / "examples/ai_agent_plugins_canary/workflow.yaml"
        )
        self.assertNotIn("scan_tst_comments", str(canary))

    def test_delivery_guards_and_scanner_copies(self) -> None:
        """Generation and each all-changes commit recheck operational storage."""
        for name in ("cursor_ticket_delivery", "hotfix_ticket_delivery"):
            owner = ROOT / "examples" / name
            root = checker.load_yaml(owner / "workflow.yaml")
            self.assertEqual(root["steps"][0]["id"], "initialize_reviewer_context")
            self.assertEqual(root["steps"][1]["id"], "check_working_files")
            for path in [
                owner / "workflow.yaml",
                *sorted((owner / "modules").glob("*.yaml")),
            ]:
                doc = checker.load_yaml(path)
                for index, step in enumerate(doc["steps"]):
                    if step["id"] == "scan_tst_comments":
                        self.assertEqual(
                            step["uses"], "process:git.cli/scan_instruction_comments"
                        )
                        self.assertEqual(
                            step["with"]["output_file"],
                            {"$document": "tst_comments", "access": "write"},
                        )
                    if step.get("uses") == "process:git.cli/commit_worktree":
                        guard = doc["steps"][index - 1]
                        self.assertEqual(
                            guard["id"], "check_working_files_before_commit"
                        )
                        self.assertIn(
                            "check_working_files.py", str(guard["with"]["args"])
                        )
                patterns = (
                    doc.get("inputs", {}).get("ignore_paths", {}).get("default", [])
                )
                self.assertNotIn(".transist", str(patterns))
            self.assertFalse((owner / "modules/scripts/scan_tst_comments.py").exists())

    def test_hotfix_scans_inline_comments_only_after_requested_review_changes(
        self,
    ) -> None:
        """The first model pass has empty context; only review rework scans files."""
        self.assert_implementation_lifecycle("hotfix_ticket_delivery", "implement_fix")

    def test_cursor_scans_inline_comments_only_after_requested_review_changes(
        self,
    ) -> None:
        """Cursor preserves stage-model binding while deferring scans until rework."""
        self.assert_implementation_lifecycle("cursor_ticket_delivery", "implement_plan")
        owner = ROOT / "examples/cursor_ticket_delivery/modules"
        module = checker.load_yaml(owner / "implementation.module.yaml")
        iteration = next(
            step for step in module["steps"] if step["id"] == "implementation_iteration"
        )
        self.assertEqual(
            iteration["module"]["inputs"], {"stage_model": "{{inputs.stage_model}}"}
        )
        child = checker.load_yaml(owner / "implementation_iteration.module.yaml")
        self.assertEqual(
            child["profiles"]["author"]["with"]["model"], "{{inputs.stage_model}}"
        )

    def assert_implementation_lifecycle(self, name: str, model_step: str) -> None:
        """Check first-pass, rework, exact-review and bounded-loop catalog contracts."""
        owner = ROOT / "examples" / name
        root = checker.load_yaml(owner / "workflow.yaml")
        self.assertEqual(root["documents"]["tst_comments"]["initial"], "")
        module = checker.load_yaml(owner / "modules/implementation.module.yaml")
        steps = {step["id"]: step for step in module["steps"]}
        loop = steps["implementation_loop"]["loop"]
        self.assertEqual(loop["body"], [{"ref": "implementation_iteration"}])
        call = steps["implementation_iteration"]["module"]
        self.assertEqual(
            {key: call[key] for key in ("ref", "rerun_mode")},
            {"ref": "iteration", "rerun_mode": "fresh"},
        )
        self.assertEqual(
            steps["require_implementation_approval"]["with"]["args"],
            [
                "source://scripts/require_implementation_approval.py",
                "{{steps.implementation_iteration.out.decision}}",
            ],
        )
        iteration = checker.load_yaml(
            owner / "modules/implementation_iteration.module.yaml"
        )
        steps = {step["id"]: step for step in iteration["steps"]}
        order = list(steps)
        self.assertLess(order.index(model_step), order.index("review_implementation"))
        self.assertLess(
            order.index("review_implementation"),
            order.index("capture_implementation_decision"),
        )
        self.assertLess(
            order.index("capture_implementation_decision"),
            order.index("route_implementation_decision"),
        )
        branch = steps["route_implementation_decision"]
        self.assertEqual(branch["control"], "control.noop")
        self.assertEqual(
            branch["if"],
            {
                "guard": (
                    'steps.review_implementation.out.decision == "request_changes"'
                ),
                "then": [{"ref": "scan_tst_comments"}],
                "else": [{"ref": "export_reviewed_implementation"}],
            },
        )
        self.assertEqual(loop["max_iters"], 5)
        self.assertEqual(loop["max_duration"], "16h")
        self.assertEqual(
            loop["until"], 'steps.implementation_iteration.out.decision == "approved"'
        )
        self.assertEqual(
            iteration["outputs"]["decision"],
            "{{steps.review_implementation.out.decision}}",
        )
        self.assertEqual(
            steps["capture_implementation_decision"]["gate_decision"],
            {"step": "review_implementation"},
        )
        protected = steps["export_reviewed_implementation"]["with"]["args"][1::2]
        self.assertEqual(len(protected), 3)
        self.assertTrue(
            all(
                binding["reviewed_by"] == "review_implementation"
                for binding in protected
            )
        )
        self.assertIn(
            {"$document": "tst_comments", "access": "read"},
            steps[model_step]["with"]["context_files"],
        )

    def test_delivery_pr_cleanup_requires_successful_delivery(self) -> None:
        """Failure cleanup never reads PR data that early failures cannot publish."""
        for name in ("hotfix_ticket_delivery", "cursor_ticket_delivery"):
            with self.subTest(example=name):
                self.assert_delivery_pr_lifecycle(name)

    def assert_delivery_pr_lifecycle(self, name: str) -> None:
        """Keep PR review/merge after creation and PR-dependent cleanup success-only."""
        root = checker.load_yaml(ROOT / "examples" / name / "workflow.yaml")
        cleanup = {step["id"]: step for step in root["cleanup"]}
        sync = cleanup["sync_trunk_branch"]
        self.assertEqual(sync["when"], ["success"])
        self.assertEqual(sync["uses"], "process:git.cli/sync_branch_from_pr")
        self.assertEqual(sync["with"]["pr_file"], {"$document": "pr", "access": "read"})
        for name in ("checkout_trunk_branch", "delete_local_feature_branch"):
            self.assertEqual(cleanup[name]["when"], ["success", "failed"])
        steps = [step["id"] for step in root["steps"]]
        self.assertLess(steps.index("open_pull_request"), steps.index("pr_review_loop"))
        self.assertLess(
            steps.index("pr_review_loop"), steps.index("merge_pull_request")
        )
        self.assertLess(steps.index("merge_pull_request"), steps.index("finish"))

    def test_catalog_pr_consumers_never_precede_creation(self) -> None:
        """Audit every authored root, including nested pre-PR work and fixtures."""

        def actions(path: Path) -> list[str]:
            """Collect all declared actions reachable within a module's graph."""
            document = checker.load_yaml(path)
            result = []
            for step in document.get("steps", []):
                result.extend(step_actions(path, document, step))
            return result

        def step_actions(path: Path, document: dict, step: dict) -> list[str]:
            """Resolve package-local module actions without invoking any participant."""
            if "uses" in step:
                return [step["uses"]]
            if "module" not in step:
                return []
            call = step["module"]
            ref = call if isinstance(call, str) else call["ref"]
            return actions(path.parent / document["modules"][ref]["path"])

        roots = [
            *sorted((ROOT / "examples").rglob("workflow.yaml")),
            *sorted((ROOT / "tests/fixtures").rglob("workflow.yaml")),
        ]
        self.assertEqual(len(roots), 7)
        for path in roots:
            with self.subTest(workflow=str(path.relative_to(ROOT))):
                document = checker.load_yaml(path)
                created = False
                for step in document["steps"]:
                    if step.get("uses") == "process:github.cli/pr_create":
                        created = True
                        continue
                    if not created:
                        for action in step_actions(path, document, step):
                            self.assertFalse(
                                action.startswith("process:github.cli/pr_")
                            )
                            self.assertNotEqual(
                                action, "process:git.cli/sync_branch_from_pr"
                            )
                for step in document.get("cleanup", []):
                    if step.get("uses") == "process:git.cli/sync_branch_from_pr":
                        self.assertTrue(created)
                        self.assertEqual(step["when"], ["success"])

    def test_hotfix_pending_merge_uses_separate_raw_checkpoint(self) -> None:
        """The advancing second fetch cannot overwrite requests waiting at the gate."""
        owner = ROOT / "examples/hotfix_ticket_delivery"
        cycle = checker.load_yaml(owner / "modules/pr_review_cycle.module.yaml")
        steps = {step["id"]: step for step in cycle["steps"]}
        for name in ("inspect_pr_comments", "refresh_pr_comments"):
            self.assertEqual(
                steps[name]["with"]["output_file"],
                {"$document": "review_comments_raw", "access": "update"},
            )
        refs = steps["maybe_refresh_review_state"]["if"]["then"]
        self.assertEqual(
            [ref["ref"] for ref in refs],
            [
                "check_working_files_before_refresh",
                "refresh_pr_comments",
                "refresh_pr_state",
                "merge_pending_review_comments",
                "write_operator_feedback",
            ],
        )
        projection = steps["merge_pending_review_comments"]
        self.assertEqual(
            projection["uses"], "process:github.cli/pr_prepare_review_context"
        )
        self.assertEqual(
            projection["with"]["pending_file"],
            {"$document": "review_comments", "access": "read"},
        )
        self.assertEqual(
            projection["with"]["output_file"],
            {"$document": "review_comments", "access": "write"},
        )
        self.assertNotIn(
            "--review-comments-file", steps["write_operator_feedback"]["with"]["args"]
        )
        changes = checker.load_yaml(owner / "modules/pr_review_changes.module.yaml")
        model = next(
            step
            for step in changes["steps"]
            if step["id"] == "implement_review_changes"
        )
        context = model["with"]["context_files"]
        self.assertFalse(
            any(
                path["$document"]
                in {"pr", "implementation_notes", "review_comments_raw"}
                for path in context
            )
        )

    def test_delivery_storage_and_skill_guidance(self) -> None:
        """Managed root data is distinct from intentional workspace deliverables."""
        for name in ("cursor_ticket_delivery", "hotfix_ticket_delivery"):
            with self.subTest(example=name):
                example = ROOT / "examples" / name
                document = checker.load_yaml(example / "workflow.yaml")
                self.assertNotIn("artifact_path_prefix", document["inputs"])
                self.assertNotIn("reviewer_context_id", document["inputs"])
                self.assertEqual(document["documents"]["attachments"]["kind"], "tree")
                self.assertEqual(
                    document["documents"]["reviewer_context"]["max_bytes"], 65536
                )
                modules = sorted((example / "modules").rglob("*.module.yaml"))
                self.assertTrue(modules)
                for path in modules:
                    with self.subTest(module=path.name):
                        module = checker.load_yaml(path)
                        self.assertIsNotNone(
                            checker.SEMVER.fullmatch(module["version"])
                        )
                        self.assertNotIn(
                            "artifact_path_prefix", module.get("inputs", {})
                        )
                        self.assertNotIn("workspace", module)
                skill = (
                    example / "modules" / "skills" / "code-changes" / "SKILL.md"
                ).read_text()
                guidance = " ".join(skill.split())
                for required in (
                    "Read the supplied context files before editing.",
                    "root managed documents outside the Git workspace.",
                    "do not delete, stage, commit or publish them.",
                    "Never relocate shared context to `run://`",
                    "invocation-private scratch removed after invocation.",
                    "Leave commits, pushes and PR operations to dedicated "
                    "workflow steps",
                    "Do not create commits in an agent step.",
                ):
                    with self.subTest(guidance=required):
                        self.assertIn(required, guidance)
                self.assertNotIn("Before commiting changes", skill)

    def test_ticket_samples_and_mutations_are_explicit(self) -> None:
        """Delivery examples pin their effects and use only fictional service inputs."""
        for name in ("cursor_ticket_delivery", "hotfix_ticket_delivery"):
            example = ROOT / "examples" / name
            document = checker.load_yaml(example / "workflow.yaml")
            sample = checker.load_yaml(example / "inputs.example.yaml")
            self.assertEqual(sample["jira_ticket_id"], "PROJ-123")
            self.assertEqual(sample["jira_site_url"], "https://example.atlassian.net")
            self.assertEqual(document["workspace"]["access"], "full")
            self.assertIsNotNone(checker.SEMVER.fullmatch(document["version"]))
            if name == "cursor_ticket_delivery":
                self.assertIsNotNone(
                    checker.SEMVER.fullmatch(document["plugins"]["cursor.cli"])
                )
            actions = [step.get("uses") for step in document["steps"]]
            self.assertIn("process:git.cli/commit_worktree", actions)
            self.assertIn("process:git.cli/push_current_branch", actions)
            self.assertIn("process:github.cli/pr_merge", actions)


if __name__ == "__main__":
    unittest.main()
