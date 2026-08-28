#!/usr/bin/env python3
"""Block likely participant data, credentials, and unreviewed artifacts from Git.

The scanner intentionally never prints raw matched content or raw repository paths.
It is a mitigation layer, not a PII classifier and not a replacement for keeping
real research data outside every repository and worktree.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


CONFIG_PATH = ".repo-guard-allowlist.json"
CONFIG_PATH_BYTES = CONFIG_PATH.encode("ascii")
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_BASE64_LINE_BYTES = 4 * 1024
MAX_AGGREGATE_BASE64_BYTES = 16 * 1024
MIN_BASE64_FRAGMENT_BYTES = 8
MAX_BASE64_TOKEN_BYTES = 2 * 1024
MIN_BASE64_CHARACTER_DENSITY = 0.98
MAX_FINDINGS_TO_PRINT = 100

# New files with these extensions must be reviewed and pinned by path and digest.
CONTROLLED_EXTENSIONS = {
    ".7z",
    ".accdb",
    ".avif",
    ".bmp",
    ".bz2",
    ".csv",
    ".db",
    ".doc",
    ".docx",
    ".gif",
    ".gz",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".mdb",
    ".ndjson",
    ".ods",
    ".pdf",
    ".png",
    ".rar",
    ".sqlite",
    ".sqlite3",
    ".svg",
    ".tar",
    ".tgz",
    ".tif",
    ".tiff",
    ".tsv",
    ".webp",
    ".xls",
    ".xlsb",
    ".xlsm",
    ".xlsx",
    ".xz",
    ".zip",
}

SAFE_DISPLAY_EXTENSIONS = CONTROLLED_EXTENSIONS | {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

EXPORT_DATA_EXTENSIONS = CONTROLLED_EXTENSIONS | {".json", ".xml"}
EXPLICIT_EXPORT_NAME_RE = re.compile(
    r"(?:^|[-_. ])(?:export|dump|raw[-_. ]?data)(?:$|[-_. ])", re.IGNORECASE
)
DATASET_EXPORT_NAME_RE = re.compile(
    r"(?:^|[-_. ])(?:participants?|respondents?|survey[-_. ]?responses?|"
    r"form[-_. ]?responses?|transcripts?|receipts?|bills?)(?:$|[-_. ])",
    re.IGNORECASE,
)

FORBIDDEN_COMPONENTS = {
    ".research-data",
    "bills",
    "export",
    "exports",
    "operator-exports",
    "participant-data",
    "private-data",
    "receipts",
    "research-data",
    "research_data",
    "study-data",
    "study_data",
    "survey-responses",
    "transcripts",
}
FORBIDDEN_SEQUENCES = {
    ("data", "exports"),
    ("data", "participants"),
    ("data", "private"),
    ("data", "raw"),
}

EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}(?![A-Za-z0-9-])"
)
VN_MOBILE_RE = re.compile(
    r"(?<!\d)(?:(?:\+|00)?84(?:[ ().-]*0)?|0)[ ().-]*(?:3|5|7|8|9)"
    r"(?:[ ().-]*\d){8}(?!\d)"
)
VN_LANDLINE_RE = re.compile(
    r"(?<!\d)(?:(?:\+|00)?84(?:[ ().-]*0)?|0)[ ().-]*2"
    r"(?:[ ().-]*\d){8,9}(?!\d)"
)
LONG_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\d(?:[ .-]?\d){8,63}(?![A-Za-z0-9])")
GITHUB_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    r"gh[pousr]_[A-Za-z0-9]{36,255}|"
    r"github_pat_[A-Za-z0-9_]{20,255}"
    r")(?![A-Za-z0-9_])"
)
AWS_ACCESS_KEY_ID_RE = re.compile(
    r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"
)
AWS_SECRET_ACCESS_KEY_RE = re.compile(
    r"(?i)(?:aws_)?secret(?:_access)?_key\s*[:=]\s*[\"']?"
    r"(?P<secret>[A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])"
)
GROUPED_VND_RE = re.compile(r"\d{1,3}(?:[., ]\d{3})+")
CURRENCY_RE = re.compile(r"(?:\bVND\b|₫|\bđồng\b)", re.IGNORECASE)
DATA_URI_BASE64_RE = re.compile(
    r"data:[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+"
    r"(?:;[^,\s;]+)*;base64,",
    re.IGNORECASE,
)
BASE64_BYTE_VALUES = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-"
)
BASE64_FRAGMENT_RE = re.compile(
    rf"[A-Za-z0-9+/_-]{{{MIN_BASE64_FRAGMENT_BYTES - 2},}}={{0,2}}"
)
BASE64_TOKEN_RE = re.compile(
    rf"[A-Za-z0-9+/_-]{{{MAX_BASE64_TOKEN_BYTES + 1},}}={{0,2}}"
)
ANNOTATION_RE = re.compile(
    r"repo-guard:\s*allow=(email|vn-phone|long-number|data-uri-base64|"
    r"dense-base64-line|aggregate-base64-fragments|long-base64-token)"
    r"\s+reason=([A-Za-z0-9][A-Za-z0-9._-]{7,})"
)

CONTENT_RULES = {
    "aggregate-base64-fragments",
    "data-uri-base64",
    "dense-base64-line",
    "email",
    "github-token",
    "aws-access-key-id",
    "aws-secret-access-key",
    "long-base64-token",
    "long-number",
    "vn-phone",
}
SECRET_RULES = {
    "aws-access-key-id",
    "aws-secret-access-key",
    "github-token",
}
ALLOWLISTABLE_RULES = (CONTENT_RULES - SECRET_RULES) | {
    "controlled-artifact",
    "export-filename",
}


class GuardError(RuntimeError):
    """A safe-to-display scanner error with no repository content."""


@dataclass(frozen=True)
class GitEntry:
    mode: str
    object_type: str
    oid: str
    path: bytes


@dataclass(frozen=True)
class StagedChange:
    status: str
    old_path: bytes | None
    new_path: bytes


@dataclass(frozen=True)
class ArtifactAllowance:
    path: str
    sha256: str
    rules: frozenset[str]


@dataclass(frozen=True)
class GuardConfig:
    artifacts: tuple[ArtifactAllowance, ...]

    def permits(self, path: str, digest: str, rule: str) -> bool:
        return any(
            item.path == path and item.sha256 == digest and rule in item.rules
            for item in self.artifacts
        )


@dataclass(frozen=True)
class Finding:
    rule: str
    file_number: int
    line: int | None
    column: int | None
    masked_match: str
    masked_path: str
    commit: str | None = None

    def render(self) -> str:
        location = f"F{self.file_number:04d}"
        if self.line is not None:
            location += f":{self.line}"
            if self.column is not None:
                location += f":{self.column}"
        fields = [
            f"rule={self.rule}",
            f"location={location}",
            f"path={self.masked_path}",
        ]
        if self.commit is not None:
            fields.append(f"commit={self.commit[:12]}")
        fields.append(f"match={self.masked_match}")
        return "- " + " ".join(fields)


@dataclass
class ScanResult:
    findings: list[Finding]
    files_scanned: int = 0
    commits_scanned: int = 0

    def extend(self, other: "ScanResult") -> None:
        self.findings.extend(other.findings)
        self.files_scanned += other.files_scanned
        self.commits_scanned += other.commits_scanned


def run_git(repo: Path, *args: str, allow_failure: bool = False) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        if allow_failure:
            return b""
        raise GuardError("Git operation failed; raw Git diagnostics were suppressed.")
    return completed.stdout


def decode_path(path: bytes) -> str:
    return path.decode("utf-8", errors="surrogateescape")


def masked_path(path: str) -> str:
    parts = PurePosixPath(path).parts
    if not parts:
        return "***"
    masked: list[str] = []
    for index, part in enumerate(parts):
        suffix = PurePosixPath(part).suffix.lower()
        if index == len(parts) - 1 and suffix in SAFE_DISPLAY_EXTENSIONS:
            masked.append(f"***{suffix}")
        else:
            masked.append("***")
    return "/".join(masked)


def mask_match(rule: str, value: str) -> str:
    if rule in SECRET_RULES:
        return f"<redacted-secret> (chars={len(value)})"
    if rule == "email":
        return "***@***.***"
    if rule == "vn-phone":
        digits = sum(character.isdigit() for character in value)
        return f"***-***-*** (digits={digits})"
    if rule == "long-number":
        digits = sum(character.isdigit() for character in value)
        return f"******** (digits={digits})"
    if rule in {"data-uri-base64", "dense-base64-line"}:
        line_bytes = len(value.encode("utf-8"))
        return f"<redacted-base64-line> (line-bytes={line_bytes})"
    if rule == "aggregate-base64-fragments":
        fragments = [
            match
            for match in BASE64_FRAGMENT_RE.finditer(value)
            if len(match.group(0).encode("ascii")) >= MIN_BASE64_FRAGMENT_BYTES
        ]
        aggregate_bytes = sum(
            len(match.group(0).encode("ascii")) for match in fragments
        )
        return (
            f"<redacted-base64-fragments> (aggregate-bytes={aggregate_bytes}, "
            f"tokens={len(fragments)})"
        )
    if rule == "long-base64-token":
        token_bytes = len(value.encode("utf-8"))
        return f"<redacted-base64-token> (token-bytes={token_bytes})"
    if rule == "export-filename":
        suffix = PurePosixPath(value).suffix.lower()
        safe_suffix = suffix if suffix in SAFE_DISPLAY_EXTENSIONS else ".***"
        return f"<redacted-export-name>{safe_suffix}"
    if rule == "controlled-artifact":
        return "<redacted-controlled-artifact>"
    if rule == "forbidden-path":
        return "<redacted-forbidden-path>"
    return "<redacted>"


def load_config(raw: bytes | None) -> GuardConfig:
    if raw is None:
        return GuardConfig(artifacts=())
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GuardError("Repo guard allowlist is not valid UTF-8 JSON.") from error
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise GuardError("Repo guard allowlist must use version 1.")
    raw_artifacts = payload.get("artifacts", [])
    if not isinstance(raw_artifacts, list):
        raise GuardError("Repo guard allowlist artifacts must be a list.")

    artifacts: list[ArtifactAllowance] = []
    for item in raw_artifacts:
        if not isinstance(item, dict):
            raise GuardError("Repo guard allowlist contains an invalid artifact entry.")
        path = item.get("path")
        digest = item.get("sha256")
        rules = item.get("rules")
        reason = item.get("reason")
        if (
            not isinstance(path, str)
            or path.startswith("/")
            or ".." in PurePosixPath(path).parts
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or not isinstance(rules, list)
            or not rules
            or any(rule not in ALLOWLISTABLE_RULES for rule in rules)
            or not isinstance(reason, str)
            or len(reason.strip()) < 12
        ):
            raise GuardError("Repo guard allowlist contains an invalid artifact entry.")
        artifacts.append(
            ArtifactAllowance(
                path=path,
                sha256=digest,
                rules=frozenset(rules),
            )
        )
    return GuardConfig(artifacts=tuple(artifacts))


def parse_tree(repo: Path, ref: str) -> dict[bytes, GitEntry]:
    raw = run_git(repo, "ls-tree", "-r", "-z", ref)
    entries: dict[bytes, GitEntry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path = record.split(b"\t", 1)
            mode, object_type, oid = metadata.decode("ascii").split(" ", 2)
        except (ValueError, UnicodeDecodeError) as error:
            raise GuardError("Git tree metadata could not be parsed safely.") from error
        entries[path] = GitEntry(mode, object_type, oid, path)
    return entries


def parse_index(repo: Path) -> dict[bytes, GitEntry]:
    raw = run_git(repo, "ls-files", "--stage", "-z")
    entries: dict[bytes, GitEntry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path = record.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split(" ", 2)
        except (ValueError, UnicodeDecodeError) as error:
            raise GuardError(
                "Git index metadata could not be parsed safely."
            ) from error
        if stage == "0":
            entries[path] = GitEntry(mode, "blob", oid, path)
    return entries


def parse_staged_changes(repo: Path) -> list[StagedChange]:
    raw = run_git(
        repo,
        "diff",
        "--cached",
        "--name-status",
        "-z",
        "--diff-filter=ACMR",
    )
    tokens = raw.split(b"\0")
    changes: list[StagedChange] = []
    cursor = 0
    while cursor < len(tokens) and tokens[cursor]:
        try:
            status = tokens[cursor].decode("ascii")
        except UnicodeDecodeError as error:
            raise GuardError("Git staged status could not be parsed safely.") from error
        cursor += 1
        if status.startswith(("R", "C")):
            if cursor + 1 >= len(tokens):
                raise GuardError("Git staged rename metadata is incomplete.")
            old_path = tokens[cursor]
            new_path = tokens[cursor + 1]
            cursor += 2
        else:
            if cursor >= len(tokens):
                raise GuardError("Git staged path metadata is incomplete.")
            old_path = None
            new_path = tokens[cursor]
            cursor += 1
        changes.append(StagedChange(status, old_path, new_path))
    return changes


def read_object(repo: Path, entry: GitEntry) -> bytes:
    if entry.mode == "160000" or entry.object_type == "commit":
        return entry.oid.encode("ascii")
    return run_git(repo, "cat-file", "blob", entry.oid)


def current_head_tree(repo: Path) -> dict[bytes, GitEntry]:
    if not run_git(repo, "rev-parse", "--verify", "HEAD", allow_failure=True):
        return {}
    return parse_tree(repo, "HEAD")


# Dependency and build directories. Not a privacy rule, but the same failure
# shape: one `git add -A` swept 12,629 node_modules files into the repository
# and took .git from a few hundred kilobytes to 84 MB, because the ignore rule
# happened to live on a different branch. A guard that trusts .gitignore
# inherits whichever branch it is standing on; this list does not.
JUNK_PATH_SEGMENTS = (
    "node_modules",
    ".expo",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    ".venv",
)

# A file whose entire name is punctuation is a shell accident. A zero-byte file
# called `=` reached main this way, was flagged in review, and got merged
# anyway. Cheap to catch, embarrassing to explain.
STRAY_NAMES = frozenset({"=", "-", "--", "~", "*", "?", "."})


def is_junk_path(path: str) -> bool:
    return any(segment in PurePosixPath(path).parts for segment in JUNK_PATH_SEGMENTS)


def is_stray_name(path: str) -> bool:
    return PurePosixPath(path).name in STRAY_NAMES


def is_forbidden_path(path: str) -> bool:
    parts = tuple(part.casefold() for part in PurePosixPath(path).parts)
    if any(part in FORBIDDEN_COMPONENTS for part in parts):
        return True
    return any(
        parts[index : index + len(sequence)] == sequence
        for sequence in FORBIDDEN_SEQUENCES
        for index in range(0, len(parts) - len(sequence) + 1)
    )


def has_export_filename(path: str) -> bool:
    filename = PurePosixPath(path).name
    suffix = PurePosixPath(filename).suffix.lower()
    stem = filename[: -len(suffix)] if suffix else filename
    return bool(EXPLICIT_EXPORT_NAME_RE.search(stem)) or (
        suffix in EXPORT_DATA_EXTENSIONS and bool(DATASET_EXPORT_NAME_RE.search(stem))
    )


def is_binary(raw: bytes) -> bool:
    if b"\0" in raw:
        return True
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def controlled_artifact(path: str, entry: GitEntry, raw: bytes) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    return (
        suffix in CONTROLLED_EXTENSIONS
        or entry.mode in {"120000", "160000"}
        or len(raw) > MAX_TEXT_BYTES
        or is_binary(raw)
    )


def added_line_numbers(old_raw: bytes | None, new_raw: bytes) -> set[int]:
    try:
        new_lines = new_raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return set()
    if old_raw is None:
        return set(range(1, len(new_lines) + 1))
    try:
        old_lines = old_raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return set(range(1, len(new_lines) + 1))

    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added: set[int] = set()
    for tag, _old_start, _old_end, new_start, new_end in matcher.get_opcodes():
        if tag in {"insert", "replace"}:
            added.update(range(new_start + 1, new_end + 1))
    return added


def inline_allows(lines: Sequence[str], zero_based_line: int, rule: str) -> bool:
    for candidate_index in (zero_based_line, zero_based_line - 1):
        if candidate_index < 0:
            continue
        for match in ANNOTATION_RE.finditer(lines[candidate_index]):
            if match.group(1) == rule:
                return True
    return False


def grouped_vnd_amount(line: str, start: int, end: int) -> bool:
    value = line[start:end]
    if GROUPED_VND_RE.fullmatch(value) is None:
        return False
    context = line[max(0, start - 16) : min(len(line), end + 16)]
    return CURRENCY_RE.search(context) is not None


def is_dense_base64_line(line: str) -> bool:
    raw_line = line.encode("utf-8")
    if len(raw_line) <= MAX_BASE64_LINE_BYTES:
        return False
    base64_bytes = sum(byte in BASE64_BYTE_VALUES for byte in raw_line)
    return base64_bytes / len(raw_line) >= MIN_BASE64_CHARACTER_DENSITY


def overlaps(span: tuple[int, int], occupied: Iterable[tuple[int, int]]) -> bool:
    start, end = span
    return any(
        start < other_end and other_start < end for other_start, other_end in occupied
    )


def content_findings(
    path: str,
    raw: bytes,
    file_number: int,
    config: GuardConfig,
    digest: str,
    line_numbers: set[int] | None,
    commit: str | None,
) -> list[Finding]:
    if len(raw) > MAX_TEXT_BYTES or is_binary(raw):
        return []
    text = raw.decode("utf-8")
    lines = text.splitlines()
    findings: list[Finding] = []

    aggregate_rule = "aggregate-base64-fragments"
    aggregate_fragments: list[tuple[int, int, str]] = []
    for zero_based_line, line in enumerate(lines):
        line_number = zero_based_line + 1
        if line_numbers is not None and line_number not in line_numbers:
            continue
        if inline_allows(lines, zero_based_line, aggregate_rule):
            continue
        aggregate_fragments.extend(
            (zero_based_line, match.start(), match.group(0))
            for match in BASE64_FRAGMENT_RE.finditer(line)
            if len(match.group(0).encode("ascii")) >= MIN_BASE64_FRAGMENT_BYTES
        )

    aggregate_bytes = sum(
        len(fragment.encode("ascii"))
        for _line, _column, fragment in aggregate_fragments
    )
    if aggregate_bytes > MAX_AGGREGATE_BASE64_BYTES and not config.permits(
        path, digest, aggregate_rule
    ):
        first_line, first_column, _first_fragment = aggregate_fragments[0]
        aggregate_text = "\n".join(
            fragment for _line, _column, fragment in aggregate_fragments
        )
        findings.append(
            Finding(
                rule=aggregate_rule,
                file_number=file_number,
                line=first_line + 1,
                column=first_column + 1,
                masked_match=mask_match(aggregate_rule, aggregate_text),
                masked_path=masked_path(path),
                commit=commit,
            )
        )

    for zero_based_line, line in enumerate(lines):
        line_number = zero_based_line + 1
        if line_numbers is not None and line_number not in line_numbers:
            continue

        occupied: list[tuple[int, int]] = []
        candidates: list[tuple[int, int, str, str]] = []
        data_uri_match = DATA_URI_BASE64_RE.search(line)
        if data_uri_match is not None:
            candidates.append(
                (
                    data_uri_match.start(),
                    data_uri_match.end(),
                    "data-uri-base64",
                    line,
                )
            )
        elif is_dense_base64_line(line):
            candidates.append((0, len(line), "dense-base64-line", line))
        else:
            base64_token_match = BASE64_TOKEN_RE.search(line)
            if base64_token_match is not None:
                candidates.append(
                    (
                        base64_token_match.start(),
                        base64_token_match.end(),
                        "long-base64-token",
                        base64_token_match.group(0),
                    )
                )
        for match in EMAIL_RE.finditer(line):
            candidates.append((match.start(), match.end(), "email", match.group(0)))
            occupied.append(match.span())
        for secret_re, rule in (
            (GITHUB_TOKEN_RE, "github-token"),
            (AWS_ACCESS_KEY_ID_RE, "aws-access-key-id"),
        ):
            for match in secret_re.finditer(line):
                candidates.append((match.start(), match.end(), rule, match.group(0)))
                occupied.append(match.span())
        for match in AWS_SECRET_ACCESS_KEY_RE.finditer(line):
            secret = match.group("secret")
            candidates.append(
                (
                    match.start("secret"),
                    match.end("secret"),
                    "aws-secret-access-key",
                    secret,
                )
            )
            occupied.append((match.start("secret"), match.end("secret")))
        for phone_re in (VN_MOBILE_RE, VN_LANDLINE_RE):
            for match in phone_re.finditer(line):
                if overlaps(match.span(), occupied):
                    continue
                candidates.append(
                    (match.start(), match.end(), "vn-phone", match.group(0))
                )
                occupied.append(match.span())
        for match in LONG_NUMBER_RE.finditer(line):
            if overlaps(match.span(), occupied):
                continue
            if grouped_vnd_amount(line, match.start(), match.end()):
                continue
            candidates.append(
                (match.start(), match.end(), "long-number", match.group(0))
            )

        for start, _end, rule, value in sorted(candidates):
            if config.permits(path, digest, rule) or inline_allows(
                lines, zero_based_line, rule
            ):
                continue
            findings.append(
                Finding(
                    rule=rule,
                    file_number=file_number,
                    line=line_number,
                    column=start + 1,
                    masked_match=mask_match(rule, value),
                    masked_path=masked_path(path),
                    commit=commit,
                )
            )
    return findings


def scan_entry(
    entry: GitEntry,
    raw: bytes,
    file_number: int,
    config: GuardConfig,
    line_numbers: set[int] | None,
    commit: str | None,
) -> list[Finding]:
    path = decode_path(entry.path)
    digest = hashlib.sha256(raw).hexdigest()
    findings: list[Finding] = []

    if is_forbidden_path(path):
        findings.append(
            Finding(
                rule="forbidden-path",
                file_number=file_number,
                line=None,
                column=None,
                masked_match=mask_match("forbidden-path", path),
                masked_path=masked_path(path),
                commit=commit,
            )
        )

    for rule, matches in (("junk-path", is_junk_path), ("stray-name", is_stray_name)):
        if matches(path):
            findings.append(
                Finding(
                    rule=rule,
                    file_number=file_number,
                    line=None,
                    column=None,
                    masked_match=f"<redacted-{rule}>",
                    masked_path=masked_path(path),
                    commit=commit,
                )
            )

    if has_export_filename(path) and not config.permits(
        path, digest, "export-filename"
    ):
        findings.append(
            Finding(
                rule="export-filename",
                file_number=file_number,
                line=None,
                column=None,
                masked_match=mask_match("export-filename", PurePosixPath(path).name),
                masked_path=masked_path(path),
                commit=commit,
            )
        )

    if controlled_artifact(path, entry, raw) and not config.permits(
        path, digest, "controlled-artifact"
    ):
        findings.append(
            Finding(
                rule="controlled-artifact",
                file_number=file_number,
                line=None,
                column=None,
                masked_match=mask_match("controlled-artifact", path),
                masked_path=masked_path(path),
                commit=commit,
            )
        )

    findings.extend(
        content_findings(
            path=path,
            raw=raw,
            file_number=file_number,
            config=config,
            digest=digest,
            line_numbers=line_numbers,
            commit=commit,
        )
    )
    return findings


def config_from_entries(repo: Path, entries: Mapping[bytes, GitEntry]) -> GuardConfig:
    config_entry = entries.get(CONFIG_PATH_BYTES)
    raw = read_object(repo, config_entry) if config_entry is not None else None
    return load_config(raw)


def scan_tree(repo: Path, ref: str, commit_label: str | None = None) -> ScanResult:
    entries = parse_tree(repo, ref)
    config = config_from_entries(repo, entries)
    result = ScanResult(findings=[])
    for file_number, path in enumerate(sorted(entries), start=1):
        entry = entries[path]
        raw = read_object(repo, entry)
        result.files_scanned += 1
        result.findings.extend(
            scan_entry(
                entry=entry,
                raw=raw,
                file_number=file_number,
                config=config,
                line_numbers=None,
                commit=commit_label,
            )
        )
    return result


def scan_staged(repo: Path) -> ScanResult:
    index_entries = parse_index(repo)
    head_entries = current_head_tree(repo)
    changes = parse_staged_changes(repo)
    config = config_from_entries(repo, index_entries)
    result = ScanResult(findings=[])

    for file_number, change in enumerate(
        sorted(changes, key=lambda item: item.new_path), start=1
    ):
        entry = index_entries.get(change.new_path)
        if entry is None:
            continue
        raw = read_object(repo, entry)
        old_path = change.old_path if change.old_path is not None else change.new_path
        old_entry = head_entries.get(old_path)
        old_raw = read_object(repo, old_entry) if old_entry is not None else None
        changed_lines = added_line_numbers(old_raw, raw)
        result.files_scanned += 1
        result.findings.extend(
            scan_entry(
                entry=entry,
                raw=raw,
                file_number=file_number,
                config=config,
                line_numbers=changed_lines,
                commit=None,
            )
        )
    return result


def resolve_commit(repo: Path, ref: str) -> str:
    raw = run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    try:
        commit = raw.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise GuardError("Git commit identifier could not be parsed safely.") from error
    if re.fullmatch(r"[0-9a-f]{40,64}", commit) is None:
        raise GuardError("Git commit identifier has an unexpected format.")
    return commit


def list_commits(repo: Path, revision: str) -> list[str]:
    raw = run_git(repo, "rev-list", "--reverse", "--topo-order", revision)
    try:
        commits = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise GuardError("Git commit list could not be parsed safely.") from error
    if any(re.fullmatch(r"[0-9a-f]{40,64}", commit) is None for commit in commits):
        raise GuardError("Git commit list has an unexpected format.")
    return commits


def scan_commits(repo: Path, commits: Sequence[str]) -> ScanResult:
    result = ScanResult(findings=[])
    for commit in commits:
        commit_result = scan_tree(repo, commit, commit_label=commit)
        commit_result.commits_scanned = 1
        result.extend(commit_result)
        if len(result.findings) >= MAX_FINDINGS_TO_PRINT:
            break
    return result


def scan_range(repo: Path, base: str, head: str) -> ScanResult:
    head_commit = resolve_commit(repo, head)
    if not base or re.fullmatch(r"0+", base):
        commits = list_commits(repo, head_commit)
    else:
        base_commit = resolve_commit(repo, base)
        commits = list_commits(repo, f"{base_commit}..{head_commit}")
    return scan_commits(repo, commits)


def emit_result(result: ScanResult, label: str) -> int:
    if result.findings:
        print(
            f"Repo guard blocked {label}: {len(result.findings)} finding(s) "
            f"across {result.files_scanned} file scan(s)."
        )
        for finding in result.findings[:MAX_FINDINGS_TO_PRINT]:
            print(finding.render())
        if len(result.findings) > MAX_FINDINGS_TO_PRINT:
            print(
                f"- {len(result.findings) - MAX_FINDINGS_TO_PRINT} additional "
                "finding(s) omitted."
            )
        print("Raw paths, source lines, and raw matches are intentionally not logged.")
        print("See docs/security/repo-guard.md for remediation and allowlisting.")
        return 1

    detail = f"{result.files_scanned} file scan(s)"
    if result.commits_scanned:
        detail += f" in {result.commits_scanned} commit(s)"
    print(f"Repo guard passed {label}: {detail}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan Git content without printing raw matches or paths."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("staged", help="Scan added lines and artifacts in the index.")

    tree_parser = subparsers.add_parser(
        "tree", help="Scan every tracked file at a ref."
    )
    tree_parser.add_argument("ref", nargs="?", default="HEAD")

    range_parser = subparsers.add_parser(
        "range", help="Scan every complete tree introduced in a commit range."
    )
    range_parser.add_argument("base")
    range_parser.add_argument("head")

    history_parser = subparsers.add_parser(
        "history", help="Scan every complete tree reachable from a ref."
    )
    history_parser.add_argument("ref", nargs="?", default="HEAD")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo = Path.cwd()
    try:
        if args.command == "staged":
            return emit_result(scan_staged(repo), "staged diff")
        if args.command == "tree":
            commit = resolve_commit(repo, args.ref)
            return emit_result(scan_tree(repo, commit), "tracked tree")
        if args.command == "range":
            return emit_result(scan_range(repo, args.base, args.head), "commit range")
        if args.command == "history":
            commit = resolve_commit(repo, args.ref)
            commits = list_commits(repo, commit)
            return emit_result(scan_commits(repo, commits), "reachable history")
    except GuardError as error:
        print(f"Repo guard could not complete: {error}", file=sys.stderr)
        return 2
    except Exception:
        print(
            "Repo guard could not complete due to an unexpected error; "
            "raw exception details were suppressed.",
            file=sys.stderr,
        )
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
