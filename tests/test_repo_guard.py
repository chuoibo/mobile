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


class PatternScannerTests(unittest.TestCase):
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

    def test_wrapped_base64_blocks_are_blocked_and_masked(self):
        payload = base64.b64encode(bytes(range(256)) * 88).decode("ascii")
        self.assertGreater(len(payload.encode("utf-8")), 22 * 1024)

        for width in (12, 76, 1000):
            with self.subTest(width=width):
                wrapped = "\n".join(textwrap.wrap(payload, width=width))
                findings = self.scan_text(wrapped, path="notes/synthetic-bill.txt")
                matches = [
                    item for item in findings if item.rule == "dense-base64-block"
                ]

                self.assertEqual(len(matches), 1)
                rendered = matches[0].render()
                self.assertIn("<redacted-base64-block>", rendered)
                self.assertNotIn(payload[:76], rendered)
                self.assertNotIn("notes/synthetic-bill.txt", rendered)

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

    def test_base64_block_and_token_thresholds_are_strict(self):
        block_at_threshold = "\n".join(
            (
                "A" * (repo_guard.MAX_BASE64_BLOCK_BYTES // 2),
                "A" * (repo_guard.MAX_BASE64_BLOCK_BYTES // 2),
            )
        )
        block_over_threshold = block_at_threshold + "A"
        token_at_threshold = "A" * repo_guard.MAX_BASE64_TOKEN_BYTES
        token_over_threshold = token_at_threshold + "A"

        self.assertNotIn(
            "dense-base64-block",
            {item.rule for item in self.scan_text(block_at_threshold)},
        )
        self.assertIn(
            "dense-base64-block",
            {item.rule for item in self.scan_text(block_over_threshold)},
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
        wrapped = "\n".join(textwrap.wrap(payload, width=76))
        token = payload[:3000]
        cases = (
            (
                "dense-base64-block",
                "# repo-guard: allow=dense-base64-block "
                "reason=reviewed-wrapped-vector\n"
                f"{wrapped}",
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
        wrapped_payload = "\n".join(textwrap.wrap(encoded, width=76))
        token = encoded[:3000]
        json_payload = json.dumps({"image": token}, separators=(",", ":"))
        (self.repo / wrapped_path).write_text(wrapped_payload + "\n", encoding="utf-8")
        (self.repo / json_path).write_text(json_payload + "\n", encoding="utf-8")
        self.git("add", wrapped_path, json_path)

        completed = self.run_guard("staged")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1, output)
        self.assertIn("rule=dense-base64-block", output)
        self.assertIn("rule=long-base64-token", output)
        self.assertIn("token-bytes=3000", output)
        for sensitive_value in (
            wrapped_path,
            json_path,
            encoded[:76],
            token[:80],
        ):
            self.assertNotIn(sensitive_value, output)

    def test_staged_block_scan_uses_unchanged_neighboring_lines(self):
        wrapped_path = "synthetic-growing-block.txt"
        encoded = base64.b64encode(bytes(range(256)) * 20).decode("ascii")
        baseline_payload = "\n".join(textwrap.wrap(encoded[:4028], width=76))
        self.assertEqual(len(baseline_payload.splitlines()), 53)
        (self.repo / wrapped_path).write_text(baseline_payload + "\n", encoding="utf-8")
        self.git("add", wrapped_path)
        self.git("commit", "-m", "synthetic block below aggregate threshold")

        added_line = encoded[4028:4104]
        self.assertEqual(len(added_line), 76)
        (self.repo / wrapped_path).write_text(
            baseline_payload + "\n" + added_line + "\n", encoding="utf-8"
        )
        self.git("add", wrapped_path)

        completed = self.run_guard("staged")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1, output)
        self.assertIn("rule=dense-base64-block", output)
        self.assertIn("lines=54", output)
        self.assertNotIn(wrapped_path, output)
        self.assertNotIn(added_line, output)

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


if __name__ == "__main__":
    unittest.main()
