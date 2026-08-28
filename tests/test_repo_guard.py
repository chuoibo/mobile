from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "repo_guard.py"
SPEC = importlib.util.spec_from_file_location("repo_guard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
repo_guard = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = repo_guard
SPEC.loader.exec_module(repo_guard)


class ScanHelper(unittest.TestCase):
    """Just the helper. Inheriting a suite would re-run every one of its tests."""

    def scan_text(self, text: str, path: str = "safe-note.txt"):
        raw = text.encode("utf-8")
        return repo_guard.content_findings(
            path=path,
            raw=raw,
            file_number=1,
            config=repo_guard.GuardConfig(artifacts=()),
            digest=hashlib.sha256(raw).hexdigest(),
            line_numbers=None,
            commit=None,
        )


class PatternScannerTests(ScanHelper):
    def test_email_phone_and_long_number_are_masked(self):
        fake_email = "an.kiemthu" + "@" + "example.invalid"
        fake_phone = "+84" + " 912 345" + " 678"
        fake_identifier = "1234" + "567890"
        findings = self.scan_text("\n".join((fake_email, fake_phone, fake_identifier)))

        self.assertEqual(
            {finding.rule for finding in findings},
            {"email", "vn-phone", "long-number"},
        )
        rendered = "\n".join(finding.render() for finding in findings)
        self.assertNotIn(fake_email, rendered)
        self.assertNotIn(fake_phone, rendered)
        self.assertNotIn(fake_identifier, rendered)

    def test_github_and_aws_credentials_are_blocked_and_masked(self):
        github_classic = "ghp_" + "A" * 36
        github_fine_grained = "github" + "_pat_" + "B" * 30
        aws_access_key = "AKIA" + "C" * 16
        aws_secret = "D" * 20 + "/" + "E" * 19
        text = "\n".join(
            (
                github_classic,
                github_fine_grained,
                aws_access_key,
                "aws_secret_access_key=" + aws_secret,
            )
        )

        findings = self.scan_text(text)

        self.assertEqual(
            {finding.rule for finding in findings},
            {
                "github-token",
                "aws-access-key-id",
                "aws-secret-access-key",
            },
        )
        rendered = "\n".join(finding.render() for finding in findings)
        for credential in (
            github_classic,
            github_fine_grained,
            aws_access_key,
            aws_secret,
        ):
            self.assertNotIn(credential, rendered)
        self.assertEqual(rendered.count("<redacted-secret>"), 4)

    def test_secret_rules_cannot_be_allowlisted(self):
        payload = {
            "version": 1,
            "artifacts": [
                {
                    "path": "safe-note.txt",
                    "sha256": "a" * 64,
                    "rules": ["github-token"],
                    "reason": "synthetic credential fixture",
                }
            ],
        }
        with self.assertRaises(repo_guard.GuardError):
            repo_guard.load_config(json.dumps(payload).encode("utf-8"))

    def test_grouped_vnd_is_not_treated_as_an_identifier(self):
        findings = self.scan_text("Chi phí tổng hợp: 100.000.000 VND")
        self.assertEqual(findings, [])

    def test_common_vietnamese_phone_formats_are_detected(self):
        fake_numbers = (
            "+84" + " (0) 912 345" + " 678",
            "0" + "28 1234" + " 5678",
        )
        for fake_number in fake_numbers:
            with self.subTest(fake_number=fake_number):
                findings = self.scan_text(fake_number)
                self.assertEqual({item.rule for item in findings}, {"vn-phone"})

    def test_inline_annotation_requires_a_specific_rule_and_reason(self):
        fake_identifier = "9876" + "543210"
        text = (
            "<!-- repo-guard: allow=long-number "
            "reason=synthetic-aggregate-fixture -->\n"
            f"Mã tổng hợp giả: {fake_identifier}"
        )
        self.assertEqual(self.scan_text(text), [])

    def test_data_uri_base64_is_blocked_for_every_filename_shape_and_masked(self):
        payload = base64.b64encode(b"obviously synthetic image bytes").decode()
        markers = (
            "data:image/" + "jpeg;base64,",
            "DATA:application/" + "octet-stream;charset=utf-8;BASE64,",
        )

        for marker in markers:
            line = f"preview={marker}{payload}"
            for path in ("docs/note.md", "src/fixture.py", "README"):
                with self.subTest(marker=marker, path=path):
                    findings = self.scan_text(line, path=path)
                    matches = [
                        item for item in findings if item.rule == "data-uri-base64"
                    ]
                    self.assertEqual(len(matches), 1)
                    rendered = matches[0].render()
                    self.assertIn(f"line-bytes={len(line.encode('utf-8'))}", rendered)
                    self.assertNotIn(payload, rendered)
                    self.assertNotIn(path, rendered)

    def test_dense_raw_base64_line_is_blocked_and_masked(self):
        payload = base64.b64encode(b"synthetic binary fixture" * 1400).decode()
        self.assertGreater(len(payload.encode("utf-8")), 32 * 1024)

        findings = self.scan_text(payload, path="notes/synthetic.md")
        matches = [item for item in findings if item.rule == "dense-base64-line"]

        self.assertEqual(len(matches), 1)
        rendered = matches[0].render()
        self.assertIn(f"line-bytes={len(payload.encode('utf-8'))}", rendered)
        self.assertNotIn(payload[:80], rendered)
        self.assertNotIn("notes/synthetic.md", rendered)

    def test_wrapped_base64_fragments_are_aggregated_across_arbitrary_gaps(self):
        payload = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        self.assertGreater(len(payload.encode("utf-8")), 22 * 1024)

        separators = (
            (8, "\n"),
            (40, "\n\n\n"),
            (76, "\n\n\n\n"),
            (
                200,
                "\n"
                + "\n".join(
                    f"Dòng phân cách tổng hợp số {index}." for index in range(50)
                )
                + "\n",
            ),
        )
        for width, separator in separators:
            with self.subTest(width=width, separator_lines=separator.count("\n") - 1):
                wrapped = separator.join(textwrap.wrap(payload, width=width))
                findings = self.scan_text(wrapped, path="notes/synthetic-bill.txt")
                matches = [
                    item
                    for item in findings
                    if item.rule == "aggregate-base64-fragments"
                ]

                self.assertEqual(len(matches), 1)
                rendered = matches[0].render()
                self.assertIn("<redacted-base64-fragments>", rendered)
                counted = int(
                    rendered.split("aggregate-bytes=", 1)[1].split(",", 1)[0]
                )
                self.assertGreater(
                    counted,
                    repo_guard.MAX_AGGREGATE_BASE64_BYTES,
                )
                self.assertNotIn(payload[:76], rendered)
                self.assertNotIn("notes/synthetic-bill.txt", rendered)

    def test_short_urlsafe_fragments_with_underscores_are_aggregated(self):
        fragment = "Aa0_____"
        base64.urlsafe_b64decode(fragment)
        payload = "\n".join(" ".join([fragment] * 100) for _ in range(30))
        self.assertEqual(len(payload.encode("ascii")), 26_999)

        findings = self.scan_text(payload, path="notes/synthetic-url-safe.txt")
        matches = [
            item for item in findings if item.rule == "aggregate-base64-fragments"
        ]

        self.assertEqual(len(matches), 1)
        rendered = matches[0].render()
        self.assertIn("aggregate-bytes=24000", rendered)
        self.assertNotIn(fragment, rendered)
        self.assertNotIn("notes/synthetic-url-safe.txt", rendered)

    def test_long_source_identifiers_do_not_aggregate_into_a_payload(self):
        line = (
            "const getGuestEnvelope = save_guest_objection("
            "SCREAMING_SNAKE_CASE, obligation_id, token_digest);"
        )
        source = "\n".join(line for _ in range(400))
        self.assertGreater(len(source.encode("utf-8")), 32 * 1024)

        rules = {item.rule for item in self.scan_text(source, path="app/source.tsx")}

        self.assertNotIn("aggregate-base64-fragments", rules)

    def test_long_base64_token_is_blocked_in_json_and_plain_text(self):
        encoded = base64.b64encode(bytes(range(256)) * 20).decode("ascii")
        payload = encoded[:3000]
        self.assertEqual(len(payload.encode("utf-8")), 3000)
        cases = (
            json.dumps({"image": payload}, separators=(",", ":")),
            payload,
        )

        for text in cases:
            with self.subTest(container="json" if text != payload else "plain"):
                findings = self.scan_text(text, path="notes/synthetic-payload.txt")
                matches = [
                    item for item in findings if item.rule == "long-base64-token"
                ]

                self.assertEqual(len(matches), 1)
                rendered = matches[0].render()
                self.assertIn("token-bytes=3000", rendered)
                self.assertNotIn(payload[:80], rendered)
                self.assertNotIn("notes/synthetic-payload.txt", rendered)

    def test_base64_line_threshold_is_strict(self):
        at_threshold = "A" * repo_guard.MAX_BASE64_LINE_BYTES
        over_threshold = at_threshold + "A"

        self.assertNotIn(
            "dense-base64-line",
            {item.rule for item in self.scan_text(at_threshold)},
        )
        self.assertIn(
            "dense-base64-line",
            {item.rule for item in self.scan_text(over_threshold)},
        )

    def test_base64_aggregate_and_token_thresholds_are_strict(self):
        fragment_count = (
            repo_guard.MAX_AGGREGATE_BASE64_BYTES
            // repo_guard.MIN_BASE64_FRAGMENT_BYTES
        )
        fragment = "Aa0_____"
        self.assertEqual(len(fragment), repo_guard.MIN_BASE64_FRAGMENT_BYTES)
        aggregate_at_threshold = "\n".join(
            fragment for _index in range(fragment_count)
        )
        aggregate_over_threshold = "\n".join(
            [
                *(fragment for _index in range(fragment_count - 1)),
                fragment + "_",
            ]
        )
        token_at_threshold = "A" * repo_guard.MAX_BASE64_TOKEN_BYTES
        token_over_threshold = token_at_threshold + "A"

        self.assertNotIn(
            "aggregate-base64-fragments",
            {item.rule for item in self.scan_text(aggregate_at_threshold)},
        )
        self.assertIn(
            "aggregate-base64-fragments",
            {item.rule for item in self.scan_text(aggregate_over_threshold)},
        )
        self.assertNotIn(
            "long-base64-token",
            {item.rule for item in self.scan_text(token_at_threshold)},
        )
        self.assertIn(
            "long-base64-token",
            {item.rule for item in self.scan_text(token_over_threshold)},
        )

    def test_hashes_signatures_and_long_golden_vector_json_are_not_blocked(self):
        digest = hashlib.sha256(b"synthetic golden vector").hexdigest()
        signature = base64.b64encode(bytes(range(64))).decode()
        vectors = [
            {
                "case": f"synthetic-{index:03d}",
                "sha256": digest,
                "signature": signature,
            }
            for index in range(40)
        ]
        golden_json = json.dumps({"vectors": vectors}, separators=(",", ":"))
        self.assertGreater(
            len(golden_json.encode("utf-8")), repo_guard.MAX_BASE64_LINE_BYTES
        )

        repeated_text = "A" * 300
        for value in (digest, signature, golden_json, repeated_text):
            with self.subTest(length=len(value)):
                self.assertEqual(self.scan_text(value, path="vectors/golden.json"), [])

        golden_dir = MODULE_PATH.parents[1] / "phase0" / "allocator" / "golden"
        for vector_path in sorted(golden_dir.glob("*.json")):
            with self.subTest(vector=vector_path.name):
                self.assertEqual(
                    self.scan_text(
                        vector_path.read_text(encoding="utf-8"),
                        path=f"phase0/allocator/golden/{vector_path.name}",
                    ),
                    [],
                )

        python_source = "\n".join(f"value_{index} = {index}" for index in range(200))
        markdown_table = "| key | value |\n|---|---|\n" + "\n".join(
            f"| row-{index:03d} | synthetic text |" for index in range(120)
        )
        adr_path = (
            MODULE_PATH.parents[1]
            / "docs"
            / "decisions"
            / "ADR-0004-hop-dong-allocator.md"
        )
        team_markdown_path = (
            MODULE_PATH.parents[1]
            / "docs"
            / "superpowers"
            / "specs"
            / "2026-08-25-group-hangout-ai-design.md"
        )
        repository_text_cases = (
            ("python-200-lines", python_source, "src/synthetic_module.py"),
            ("markdown-table", markdown_table, "docs/synthetic-table.md"),
            (
                "adr-0004",
                adr_path.read_text(encoding="utf-8"),
                "docs/decisions/ADR-0004-hop-dong-allocator.md",
            ),
            (
                "long-team-markdown",
                team_markdown_path.read_text(encoding="utf-8"),
                "docs/superpowers/specs/2026-08-25-group-hangout-ai-design.md",
            ),
        )
        self.assertGreater(len(markdown_table.encode("utf-8")), 3000)
        self.assertGreater(team_markdown_path.stat().st_size, 80 * 1024)
        for name, text, path in repository_text_cases:
            with self.subTest(repository_text=name):
                self.assertEqual(self.scan_text(text, path=path), [])

    def test_dense_base64_fixture_can_use_narrow_inline_annotation(self):
        payload = base64.b64encode(b"synthetic fixture bytes" * 300).decode()
        text = (
            "# repo-guard: allow=dense-base64-line "
            "reason=reviewed-synthetic-vector\n"
            f"{payload}"
        )

        self.assertEqual(self.scan_text(text, path="vectors/fixture.txt"), [])

    def test_new_base64_rules_can_use_narrow_inline_annotations(self):
        payload = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        wrapped = "\n".join(
            "# repo-guard: allow=aggregate-base64-fragments "
            "reason=reviewed-wrapped-vector\n" + fragment
            for fragment in textwrap.wrap(payload, width=76)
        )
        token = payload[:3000]
        cases = (
            (
                "aggregate-base64-fragments",
                wrapped,
            ),
            (
                "long-base64-token",
                "# repo-guard: allow=long-base64-token "
                "reason=reviewed-encoded-vector\n"
                f"{token}",
            ),
        )

        for rule, text in cases:
            with self.subTest(rule=rule):
                self.assertEqual(self.scan_text(text, path="vectors/fixture.txt"), [])

    def test_aggregate_base64_annotation_does_not_exempt_distant_lines(self):
        payload = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        fragments = textwrap.wrap(payload, width=76)
        text = (
            "# repo-guard: allow=aggregate-base64-fragments "
            "reason=reviewed-one-fragment\n"
            + fragments[0]
            + "\n\n\n"
            + "\n\n\n".join(fragments[1:])
        )

        self.assertIn(
            "aggregate-base64-fragments",
            {item.rule for item in self.scan_text(text, path="vectors/fixture.txt")},
        )

    def test_controlled_artifact_requires_exact_path_and_digest(self):
        path = "docs/assets/synthetic-diagram.png"
        raw = b"\x89PNG\r\n\x1a\nsynthetic-only"
        digest = hashlib.sha256(raw).hexdigest()
        config = repo_guard.GuardConfig(
            artifacts=(
                repo_guard.ArtifactAllowance(
                    path=path,
                    sha256=digest,
                    rules=frozenset({"controlled-artifact"}),
                ),
            )
        )
        entry = repo_guard.GitEntry("100644", "blob", "0" * 40, path.encode())

        allowed = repo_guard.scan_entry(entry, raw, 1, config, None, None)
        changed = repo_guard.scan_entry(entry, raw + b"changed", 1, config, None, None)

        self.assertEqual(allowed, [])
        self.assertIn("controlled-artifact", {item.rule for item in changed})

    def test_each_required_artifact_category_is_controlled(self):
        extensions = (".png", ".pdf", ".zip", ".xlsx", ".sqlite")
        for suffix in extensions:
            with self.subTest(suffix=suffix):
                path = f"safe/synthetic-artifact{suffix}"
                entry = repo_guard.GitEntry("100644", "blob", "0" * 40, path.encode())
                findings = repo_guard.scan_entry(
                    entry,
                    b"obviously synthetic text payload",
                    1,
                    repo_guard.GuardConfig(artifacts=()),
                    None,
                    None,
                )
                self.assertIn("controlled-artifact", {item.rule for item in findings})

    def test_forbidden_data_path_cannot_be_allowlisted(self):
        path = "data/raw/synthetic-note.txt"
        raw = b"obviously synthetic"
        entry = repo_guard.GitEntry("100644", "blob", "0" * 40, path.encode())
        findings = repo_guard.scan_entry(
            entry,
            raw,
            1,
            repo_guard.GuardConfig(artifacts=()),
            None,
            None,
        )
        self.assertIn("forbidden-path", {item.rule for item in findings})

    def test_export_filename_is_not_echoed(self):
        filename = "participants" + "_export.csv"
        entry = repo_guard.GitEntry("100644", "blob", "0" * 40, filename.encode())
        findings = repo_guard.scan_entry(
            entry,
            b"synthetic,only\n",
            1,
            repo_guard.GuardConfig(artifacts=()),
            None,
            None,
        )
        rendered = "\n".join(item.render() for item in findings)
        self.assertIn("export-filename", {item.rule for item in findings})
        self.assertNotIn(filename, rendered)


class GitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic-test" + "@" + "example.invalid")
        (self.repo / ".repo-guard-allowlist.json").write_text(
            '{"version": 1, "artifacts": []}\n', encoding="utf-8"
        )
        (self.repo / "note.txt").write_text("safe baseline\n", encoding="utf-8")
        self.git("add", ".repo-guard-allowlist.json", "note.txt")
        self.git("commit", "-m", "synthetic baseline")

    def tearDown(self):
        self.temp_dir.cleanup()

    def git(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return completed.stdout.strip()

    def run_guard(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(MODULE_PATH), *args],
            cwd=self.repo,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_staged_scan_reads_index_not_unstaged_worktree(self):
        (self.repo / "note.txt").write_text(
            "safe baseline\nstaged safe line\n", encoding="utf-8"
        )
        self.git("add", "note.txt")
        fake_email = "unstaged.person" + "@" + "example.invalid"
        (self.repo / "note.txt").write_text(
            f"safe baseline\nstaged safe line\n{fake_email}\n", encoding="utf-8"
        )

        completed = self.run_guard("staged")

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertNotIn(fake_email, completed.stdout + completed.stderr)

    def test_staged_failure_never_logs_raw_match_or_path(self):
        fake_email = "participant.synthetic" + "@" + "example.invalid"
        filename = "participants" + "_export.csv"
        (self.repo / filename).write_text(fake_email + "\n", encoding="utf-8")
        self.git("add", "-f", filename)

        completed = self.run_guard("staged")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1, output)
        self.assertNotIn(fake_email, output)
        self.assertNotIn(filename, output)
        self.assertIn("rule=email", output)
        self.assertIn("rule=export-filename", output)

    def test_staged_secret_failure_never_logs_the_credential(self):
        fake_token = "ghp_" + "S" * 36
        (self.repo / "note.txt").write_text(
            "safe baseline\n" + fake_token + "\n", encoding="utf-8"
        )
        self.git("add", "note.txt")

        completed = self.run_guard("staged")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1, output)
        self.assertIn("rule=github-token", output)
        self.assertIn("<redacted-secret>", output)
        self.assertNotIn(fake_token, output)

    def test_staged_scan_blocks_embedded_and_raw_base64_without_logging_them(self):
        embedded_path = "synthetic-preview.md"
        raw_path = "synthetic-encoded.md"
        embedded_payload = base64.b64encode(b"synthetic jpeg bytes" * 900).decode()
        raw_payload = base64.b64encode(b"synthetic raw bytes" * 1400).decode()
        data_uri_marker = "data:image/" + "jpeg;base64,"
        embedded_line = f"{data_uri_marker}{embedded_payload}"
        (self.repo / embedded_path).write_text(embedded_line + "\n", encoding="utf-8")
        (self.repo / raw_path).write_text(raw_payload + "\n", encoding="utf-8")
        self.git("add", embedded_path, raw_path)

        completed = self.run_guard("staged")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1, output)
        self.assertIn("rule=data-uri-base64", output)
        self.assertIn("rule=dense-base64-line", output)
        self.assertIn(f"line-bytes={len(embedded_line.encode('utf-8'))}", output)
        self.assertIn(f"line-bytes={len(raw_payload.encode('utf-8'))}", output)
        for sensitive_value in (
            embedded_path,
            raw_path,
            embedded_payload[:80],
            raw_payload[:80],
        ):
            self.assertNotIn(sensitive_value, output)

    def test_staged_scan_blocks_wrapped_and_json_base64_without_logging_them(self):
        wrapped_path = "synthetic-wrapped.txt"
        json_path = "synthetic-payload.json"
        encoded = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        separator = (
            "\n"
            + "\n".join(f"synthetic separator line {index}" for index in range(50))
            + "\n"
        )
        wrapped_payload = separator.join(textwrap.wrap(encoded, width=76))
        token = encoded[:3000]
        json_payload = json.dumps({"image": token}, separators=(",", ":"))
        (self.repo / wrapped_path).write_text(wrapped_payload + "\n", encoding="utf-8")
        (self.repo / json_path).write_text(json_payload + "\n", encoding="utf-8")
        self.git("add", wrapped_path, json_path)

        completed = self.run_guard("staged")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1, output)
        self.assertIn("rule=aggregate-base64-fragments", output)
        self.assertIn("rule=long-base64-token", output)
        self.assertIn("token-bytes=3000", output)
        for sensitive_value in (
            wrapped_path,
            json_path,
            encoded[:76],
            token[:80],
        ):
            self.assertNotIn(sensitive_value, output)

    def test_staged_aggregate_counts_all_added_lines_in_one_file(self):
        path = "synthetic-scattered-fragments.txt"
        encoded = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        fragments = textwrap.wrap(encoded, width=40)
        split_at = len(fragments) // 2
        self.assertLess(sum(map(len, fragments[:split_at])), 16 * 1024)
        self.assertLess(sum(map(len, fragments[split_at:])), 16 * 1024)

        stable_context = [f"safe stable context line {index}" for index in range(500)]
        baseline = ["synthetic heading", *stable_context, "synthetic footer"]
        (self.repo / path).write_text("\n".join(baseline) + "\n", encoding="utf-8")
        self.git("add", path)
        self.git("commit", "-m", "synthetic baseline with two insertion points")

        candidate = [
            "synthetic heading",
            *fragments[:split_at],
            *stable_context,
            *fragments[split_at:],
            "synthetic footer",
        ]
        (self.repo / path).write_text("\n".join(candidate) + "\n", encoding="utf-8")
        self.git("add", path)

        completed = self.run_guard("staged")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1, output)
        self.assertIn("rule=aggregate-base64-fragments", output)
        self.assertIn(f"aggregate-bytes={len(encoded)}", output)
        self.assertNotIn(path, output)
        self.assertNotIn(encoded[:40], output)

    def test_range_scan_catches_data_removed_in_a_later_commit(self):
        base = self.git("rev-parse", "HEAD")
        fake_email = "transient.synthetic" + "@" + "example.invalid"
        (self.repo / "note.txt").write_text(
            f"safe baseline\n{fake_email}\n", encoding="utf-8"
        )
        self.git("add", "note.txt")
        self.git("commit", "-m", "synthetic transient fixture")
        (self.repo / "note.txt").write_text("safe baseline\n", encoding="utf-8")
        self.git("add", "note.txt")
        self.git("commit", "-m", "remove synthetic transient fixture")
        head = self.git("rev-parse", "HEAD")

        completed = self.run_guard("range", base, head)
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1, output)
        self.assertNotIn(fake_email, output)
        self.assertIn("rule=email", output)


class LockfileDigestAllowanceTests(ScanHelper):
    """Neither a lockfile name nor a format marker is evidence.

    The first version of the generated-lockfile exemption keyed off the name
    alone. Codex proved that was a complete backdoor: a base64 bill plus a bank
    account number, in any file called package-lock.json anywhere in the tree,
    produced zero findings. A format marker did not close that bypass because
    unexpected fields could still be pasted into an otherwise valid lockfile.
    """

    def _bill_and_account(self) -> str:
        payload = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        # repo-guard: allow=long-number reason=synthetic-account-number-this-test-must-contain-one
        return '{"anh":"' + payload + '","stk":"19036812345678"}'

    def test_a_file_merely_named_like_a_lockfile_gets_no_exemption(self):
        line = self._bill_and_account()

        for path in ("package-lock.json", "nested/deep/package-lock.json"):
            with self.subTest(path=path):
                rules = {item.rule for item in self.scan_text(line, path=path)}
                self.assertIn("long-number", rules)
                self.assertIn("aggregate-base64-fragments", rules)

    def test_a_valid_marker_does_not_exempt_unexpected_content(self):
        payload = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        # repo-guard: allow=long-number reason=synthetic-lockfile-identifier
        synthetic_identifier = "19036812345678"
        line = json.dumps(
            {
                "name": "x",
                "lockfileVersion": 3,
                "packages": {
                    "": {
                        "integrity": payload,
                        "unexpectedIdentifier": synthetic_identifier,
                    }
                },
            },
            separators=(",", ":"),
        )

        rules = {item.rule for item in self.scan_text(line, path="package-lock.json")}

        self.assertIn("aggregate-base64-fragments", rules)
        self.assertIn("long-number", rules)

    def test_a_format_marker_buried_past_the_head_does_not_earn_the_exemption(self):
        # Otherwise an attacker appends `"lockfileVersion": 3` after the payload.
        line = self._bill_and_account() + ',{"lockfileVersion":3}'

        rules = {item.rule for item in self.scan_text(line, path="package-lock.json")}

        self.assertIn("long-number", rules)

    def test_exact_path_and_digest_can_allow_a_reviewed_lockfile(self):
        fragment = "Aa0_____"
        # repo-guard: allow=long-number reason=synthetic-lockfile-identifier
        synthetic_identifier = "19036812345678"
        payload = {
            "name": "synthetic-lockfile",
            "lockfileVersion": 3,
            "packages": {},
            "generatedFragments": [fragment] * 3_000,
            "generatedIdentifier": synthetic_identifier,
        }
        raw = json.dumps(payload, indent=2).encode("utf-8")
        path = "apps/mobile/package-lock.json"
        digest = hashlib.sha256(raw).hexdigest()
        config = repo_guard.GuardConfig(
            artifacts=(
                repo_guard.ArtifactAllowance(
                    path=path,
                    sha256=digest,
                    rules=frozenset(
                        {"aggregate-base64-fragments", "long-number"}
                    ),
                ),
            )
        )

        allowed = repo_guard.content_findings(
            path, raw, 1, config, digest, None, None
        )
        changed = repo_guard.content_findings(
            path,
            raw + b" ",
            1,
            config,
            hashlib.sha256(raw + b" ").hexdigest(),
            None,
            None,
        )

        self.assertEqual(allowed, [])
        self.assertIn(
            "aggregate-base64-fragments",
            {item.rule for item in changed},
        )
        self.assertIn("long-number", {item.rule for item in changed})


if __name__ == "__main__":
    unittest.main()


class LockfileExemptionTests(ScanHelper):
    """A filename is not evidence.

    The first version of the generated-lockfile exemption keyed off the name
    alone. Codex proved that was a complete backdoor: a base64 bill plus a bank
    account number, in any file called package-lock.json anywhere in the tree,
    produced zero findings; the same bytes named notes.json produced four.
    """

    def _bill_and_account(self) -> str:
        payload = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        # repo-guard: allow=long-number reason=synthetic-account-number-this-test-must-contain-one
        return '{"anh":"' + payload + '","stk":"19036812345678"}'

    def test_a_file_merely_named_like_a_lockfile_gets_no_exemption(self):
        line = self._bill_and_account()

        for path in ("package-lock.json", "nested/deep/package-lock.json"):
            with self.subTest(path=path):
                rules = {item.rule for item in self.scan_text(line, path=path)}
                self.assertIn("long-number", rules)
                self.assertIn("aggregate-base64-fragments", rules)

    def test_the_exemption_still_applies_to_a_real_lockfile(self):
        payload = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        line = '{"name":"x","lockfileVersion":3,"packages":{"":{"integrity":"' + payload + '"}}}'

        rules = {item.rule for item in self.scan_text(line, path="package-lock.json")}

        self.assertNotIn("aggregate-base64-fragments", rules)
        self.assertNotIn("long-number", rules)

    def test_a_format_marker_buried_past_the_head_does_not_earn_the_exemption(self):
        # Otherwise an attacker appends `"lockfileVersion": 3` after the payload.
        line = self._bill_and_account() + ',{"lockfileVersion":3}'

        rules = {item.rule for item in self.scan_text(line, path="package-lock.json")}

        self.assertIn("long-number", rules)
