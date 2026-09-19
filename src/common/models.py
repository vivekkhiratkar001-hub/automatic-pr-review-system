"""Shared integration contract ("Contract v1") for the AI-Based PR Review System.

This module is the single source of truth for the data exchanged between the
four team members' modules. It is intentionally implementation-independent:
it contains no GitHub request objects, no LLM/Ollama fields, no credentials,
and no database concerns.

CONTRACT FREEZE
---------------
Once committed, the models, enums and field names below are frozen.
Nobody may rename, remove, retype, or reorder them on their own.
If a change is required, PROPOSE it explicitly (issue / PR discussion
with all four members) and bump ``CONTRACT_VERSION`` -- do not modify
this file silently. ``tests/common/test_models.py`` contains guard tests
that fail if any model or enum drifts from Contract v1.

Conventions
-----------
* Requires Python 3.10+ and Pydantic v2.
* Every model forbids unknown fields (``extra="forbid"``), so a typo or an
  undeclared field fails loudly instead of being silently dropped.
* Every model round-trips through JSON
  (``model_dump_json`` / ``model_validate_json``). Enums serialize as their
  string values; ``metadata`` dicts are validated to be JSON serializable.
* Line numbers are 1-based. Diff-hunk numbers (``ChangedRegion``) follow
  unified-diff semantics and may be 0 (e.g. the old side of a new file).
"""

import json
from enum import Enum
from typing import Annotated, Any, Final

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_validator,
)

CONTRACT_VERSION: Final[str] = "v1"

__all__ = [
    "CONTRACT_VERSION",
    # Enums
    "Severity",
    "VerificationStatus",
    "FindingSource",
    "FindingDisposition",
    "FileStatus",
    # Models
    "ChangedRegion",
    "ChangedFile",
    "PRContext",
    "RepositoryRule",
    "CodeUnit",
    "AnalysisFinding",
    "AnalysisResult",
    "ReviewComment",
    "ReviewResult",
]


# ---------------------------------------------------------------------------
# Enums (str-based so they serialize to plain JSON strings)
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """How serious a rule violation or finding is."""

    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class VerificationStatus(str, Enum):
    """Outcome of verifying a repository rule against the code."""

    COMPLIANT = "COMPLIANT"
    VIOLATION = "VIOLATION"
    UNCERTAIN = "UNCERTAIN"


class FindingSource(str, Enum):
    """Which analyzer produced a finding."""

    AST = "AST"
    TREE_SITTER = "TREE_SITTER"
    PYLINT = "PYLINT"
    FLAKE8 = "FLAKE8"
    SECURITY_RULE = "SECURITY_RULE"
    COMPLEXITY = "COMPLEXITY"
    LLM = "LLM"


class FindingDisposition(str, Enum):
    """Verdict on a finding after validation/triage."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


class FileStatus(str, Enum):
    """Change status of a file within a pull request."""

    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    COPIED = "COPIED"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Shared type aliases and helpers
# ---------------------------------------------------------------------------

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


def _ensure_json_serializable(value: dict[str, Any]) -> dict[str, Any]:
    """Reject metadata that cannot be represented as strict JSON."""
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value must be JSON serializable: {exc}") from exc
    return value


JsonDict = Annotated[dict[str, Any], AfterValidator(_ensure_json_serializable)]


def _check_line_range(start: int | None, end: int | None) -> None:
    """Validate an optional (start, end) line range."""
    if end is not None and start is None:
        raise ValueError("end_line requires start_line to be set")
    if start is not None and end is not None and end < start:
        raise ValueError("end_line must be greater than or equal to start_line")


class ContractModel(BaseModel):
    """Base class for all Contract v1 models (not part of the public contract)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ---------------------------------------------------------------------------
# Pull-request input models
# ---------------------------------------------------------------------------


class ChangedRegion(ContractModel):
    """One diff hunk: a contiguous changed region within a file.

    Mirrors the unified-diff header ``@@ -old_start,old_count +new_start,new_count @@``.
    """

    file: NonEmptyStr
    old_start: NonNegativeInt
    old_count: NonNegativeInt
    new_start: NonNegativeInt
    new_count: NonNegativeInt
    patch: str | None = None


class ChangedFile(ContractModel):
    """A single file touched by the pull request."""

    path: NonEmptyStr
    status: FileStatus
    additions: NonNegativeInt
    deletions: NonNegativeInt
    patch: str | None = None
    language: str | None = None
    changed_regions: list[ChangedRegion] = Field(default_factory=list)


class PRContext(ContractModel):
    """Platform-neutral description of the pull request under review.

    By convention ``repository`` is the full name (``"owner/repository_name"``).
    """

    repository: NonEmptyStr
    owner: NonEmptyStr
    repository_name: NonEmptyStr
    pr_number: PositiveInt
    base_sha: NonEmptyStr
    head_sha: NonEmptyStr
    changed_files: list[ChangedFile] = Field(default_factory=list)
    description: str | None = None
    base_branch: str | None = None
    head_branch: str | None = None


# ---------------------------------------------------------------------------
# Rules and analysis models
# ---------------------------------------------------------------------------


class RepositoryRule(ContractModel):
    """A single coding/repository rule extracted from project documents."""

    rule_id: NonEmptyStr
    source_document: NonEmptyStr
    category: NonEmptyStr
    title: NonEmptyStr
    description: str
    severity: Severity
    rule_type: NonEmptyStr
    scope: NonEmptyStr
    original_text: str | None = None
    machine_checkable: bool
    verification_status: VerificationStatus | None = None


class CodeUnit(ContractModel):
    """A structural unit of source code (function, class, block, ...)."""

    file: NonEmptyStr
    language: NonEmptyStr
    node_type: NonEmptyStr
    name: str | None = None
    start_line: PositiveInt
    end_line: PositiveInt
    parent: str | None = None
    metadata: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_line_range(self) -> "CodeUnit":
        _check_line_range(self.start_line, self.end_line)
        return self


class AnalysisFinding(ContractModel):
    """One issue reported by an analyzer (static tool, rule check, or LLM)."""

    finding_id: NonEmptyStr
    source: FindingSource
    rule_id: str | None = None
    file: NonEmptyStr
    start_line: PositiveInt | None = None
    end_line: PositiveInt | None = None
    severity: Severity
    title: NonEmptyStr
    message: NonEmptyStr
    evidence: str | None = None
    recommendation: str | None = None
    confidence: Confidence
    deterministic: bool
    disposition: FindingDisposition | None = None
    changed_line: bool = False
    metadata: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_line_range(self) -> "AnalysisFinding":
        _check_line_range(self.start_line, self.end_line)
        return self


class AnalysisResult(ContractModel):
    """Everything the analysis stage hands to the review stage."""

    analysis_id: NonEmptyStr
    pr_number: PositiveInt
    head_sha: NonEmptyStr
    rules: list[RepositoryRule] = Field(default_factory=list)
    code_units: list[CodeUnit] = Field(default_factory=list)
    findings: list[AnalysisFinding] = Field(default_factory=list)
    summary: str | None = None


# ---------------------------------------------------------------------------
# Review output models
# ---------------------------------------------------------------------------


class ReviewComment(ContractModel):
    """An inline review comment anchored to a file and line range."""

    file: NonEmptyStr
    start_line: PositiveInt
    end_line: PositiveInt | None = None
    severity: Severity
    body: NonEmptyStr
    finding_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_line_range(self) -> "ReviewComment":
        _check_line_range(self.start_line, self.end_line)
        return self


class ReviewResult(ContractModel):
    """Final review output for a pull request."""

    review_id: NonEmptyStr
    pr_number: PositiveInt
    head_sha: NonEmptyStr
    summary: str
    findings: list[AnalysisFinding] = Field(default_factory=list)
    comments: list[ReviewComment] = Field(default_factory=list)
    block_merge: bool
    critical_count: NonNegativeInt
    error_count: NonNegativeInt
    warning_count: NonNegativeInt
    info_count: NonNegativeInt
