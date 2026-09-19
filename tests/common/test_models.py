"""Tests for the shared Contract v1 models (src/common/models.py).

Besides behavioural tests, this file contains *contract guard* tests that pin
the exact enum values and field names. If one of them fails, someone changed
Contract v1 -- propose the change explicitly instead of editing these tests.
"""

import json
import math

import pytest
from pydantic import ValidationError

from src.common.models import (
    AnalysisFinding,
    AnalysisResult,
    ChangedFile,
    ChangedRegion,
    CodeUnit,
    FileStatus,
    FindingDisposition,
    FindingSource,
    PRContext,
    RepositoryRule,
    ReviewComment,
    ReviewResult,
    Severity,
    VerificationStatus,
)

# ---------------------------------------------------------------------------
# Factories: minimal valid payloads (plain dicts, so tests can tweak them)
# ---------------------------------------------------------------------------


def region_data(**overrides):
    data = {
        "file": "src/app.py",
        "old_start": 10,
        "old_count": 3,
        "new_start": 10,
        "new_count": 5,
        "patch": "@@ -10,3 +10,5 @@\n-old\n+new\n+new2",
    }
    data.update(overrides)
    return data


def file_data(**overrides):
    data = {
        "path": "src/app.py",
        "status": "MODIFIED",
        "additions": 2,
        "deletions": 1,
        "patch": "@@ -10,3 +10,5 @@",
        "language": "python",
        "changed_regions": [region_data()],
    }
    data.update(overrides)
    return data


def pr_data(**overrides):
    data = {
        "repository": "acme/widgets",
        "owner": "acme",
        "repository_name": "widgets",
        "pr_number": 42,
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "changed_files": [file_data()],
        "description": "Fix widget parsing",
        "base_branch": "main",
        "head_branch": "fix/parsing",
    }
    data.update(overrides)
    return data


def rule_data(**overrides):
    data = {
        "rule_id": "RULE-001",
        "source_document": "CONTRIBUTING.md",
        "category": "style",
        "title": "No bare except",
        "description": "Do not use bare except clauses.",
        "severity": "ERROR",
        "rule_type": "prohibition",
        "scope": "python",
        "original_text": "Never use a bare `except:`.",
        "machine_checkable": True,
        "verification_status": "VIOLATION",
    }
    data.update(overrides)
    return data


def unit_data(**overrides):
    data = {
        "file": "src/app.py",
        "language": "python",
        "node_type": "function_definition",
        "name": "parse",
        "start_line": 10,
        "end_line": 25,
        "parent": "Parser",
        "metadata": {"complexity": 4, "args": ["self", "text"]},
    }
    data.update(overrides)
    return data


def finding_data(**overrides):
    data = {
        "finding_id": "F-001",
        "source": "PYLINT",
        "rule_id": "RULE-001",
        "file": "src/app.py",
        "start_line": 12,
        "end_line": 14,
        "severity": "WARNING",
        "title": "Bare except",
        "message": "A bare except clause hides errors.",
        "evidence": "except:",
        "recommendation": "Catch a specific exception.",
        "confidence": 0.9,
        "deterministic": True,
        "disposition": "ACCEPTED",
        "changed_line": True,
        "metadata": {"pylint_id": "W0702"},
    }
    data.update(overrides)
    return data


def analysis_data(**overrides):
    data = {
        "analysis_id": "AN-1",
        "pr_number": 42,
        "head_sha": "b" * 40,
        "rules": [rule_data()],
        "code_units": [unit_data()],
        "findings": [finding_data()],
        "summary": "1 finding",
    }
    data.update(overrides)
    return data


def comment_data(**overrides):
    data = {
        "file": "src/app.py",
        "start_line": 12,
        "end_line": 14,
        "severity": "WARNING",
        "body": "Avoid bare except.",
        "finding_ids": ["F-001"],
    }
    data.update(overrides)
    return data


def review_data(**overrides):
    data = {
        "review_id": "RV-1",
        "pr_number": 42,
        "head_sha": "b" * 40,
        "summary": "One warning found.",
        "findings": [finding_data()],
        "comments": [comment_data()],
        "block_merge": False,
        "critical_count": 0,
        "error_count": 0,
        "warning_count": 1,
        "info_count": 0,
    }
    data.update(overrides)
    return data


ALL_MODELS = [
    (ChangedRegion, region_data),
    (ChangedFile, file_data),
    (PRContext, pr_data),
    (RepositoryRule, rule_data),
    (CodeUnit, unit_data),
    (AnalysisFinding, finding_data),
    (AnalysisResult, analysis_data),
    (ReviewComment, comment_data),
    (ReviewResult, review_data),
]
MODEL_IDS = [model.__name__ for model, _ in ALL_MODELS]


# ---------------------------------------------------------------------------
# Valid objects
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("model", "factory"), ALL_MODELS, ids=MODEL_IDS)
def test_valid_objects_are_created(model, factory):
    obj = model(**factory())
    assert isinstance(obj, model)


def test_valid_finding_fields_and_enum_coercion():
    finding = AnalysisFinding(**finding_data())
    assert finding.source is FindingSource.PYLINT
    assert finding.severity is Severity.WARNING
    assert finding.disposition is FindingDisposition.ACCEPTED
    assert finding.confidence == pytest.approx(0.9)
    assert finding.deterministic is True
    assert finding.changed_line is True


def test_optional_fields_can_be_omitted_or_none():
    region = ChangedRegion(file="a.py", old_start=0, old_count=0, new_start=1, new_count=3)
    assert region.patch is None

    changed = ChangedFile(path="a.py", status=FileStatus.ADDED, additions=3, deletions=0)
    assert changed.patch is None
    assert changed.language is None
    assert changed.changed_regions == []

    pr = PRContext(
        repository="acme/widgets",
        owner="acme",
        repository_name="widgets",
        pr_number=1,
        base_sha="a1",
        head_sha="b2",
    )
    assert pr.changed_files == []
    assert pr.description is None
    assert pr.base_branch is None
    assert pr.head_branch is None

    finding = AnalysisFinding(
        finding_id="F-2",
        source=FindingSource.LLM,
        file="a.py",
        severity=Severity.INFO,
        title="t",
        message="m",
        confidence=0.5,
        deterministic=False,
    )
    assert finding.rule_id is None
    assert finding.start_line is None
    assert finding.end_line is None
    assert finding.disposition is None
    assert finding.changed_line is False
    assert finding.metadata == {}


def test_default_collections_are_not_shared_between_instances():
    a = AnalysisResult(analysis_id="A", pr_number=1, head_sha="x")
    b = AnalysisResult(analysis_id="B", pr_number=1, head_sha="x")
    a.findings.append(AnalysisFinding(**finding_data()))
    assert b.findings == []


@pytest.mark.parametrize("status", list(FileStatus))
def test_every_file_status_is_accepted(status):
    assert ChangedFile(**file_data(status=status)).status is status


@pytest.mark.parametrize("source", list(FindingSource))
def test_every_finding_source_is_accepted(source):
    assert AnalysisFinding(**finding_data(source=source)).source is source


# ---------------------------------------------------------------------------
# Invalid severity (and other invalid enum values)
# ---------------------------------------------------------------------------


def test_severity_enum_rejects_unknown_value():
    with pytest.raises(ValueError):
        Severity("BLOCKER")


@pytest.mark.parametrize("bad", ["BLOCKER", "critical", "Error", "", "HIGH", None, 3])
def test_invalid_severity_rejected_on_finding(bad):
    with pytest.raises(ValidationError) as exc_info:
        AnalysisFinding(**finding_data(severity=bad))
    assert "severity" in str(exc_info.value)


@pytest.mark.parametrize(
    ("model", "factory"),
    [(RepositoryRule, rule_data), (ReviewComment, comment_data)],
    ids=["RepositoryRule", "ReviewComment"],
)
def test_invalid_severity_rejected_on_other_models(model, factory):
    with pytest.raises(ValidationError):
        model(**factory(severity="SEVERE"))


@pytest.mark.parametrize(
    ("model", "factory", "field", "bad"),
    [
        (AnalysisFinding, finding_data, "source", "SONARQUBE"),
        (AnalysisFinding, finding_data, "disposition", "MAYBE"),
        (RepositoryRule, rule_data, "verification_status", "PASSED"),
        (ChangedFile, file_data, "status", "MOVED"),
    ],
)
def test_invalid_other_enum_values_rejected(model, factory, field, bad):
    with pytest.raises(ValidationError):
        model(**factory(**{field: bad}))


def test_invalid_severity_rejected_on_assignment():
    finding = AnalysisFinding(**finding_data())
    with pytest.raises(ValidationError):
        finding.severity = "BLOCKER"


# ---------------------------------------------------------------------------
# Invalid confidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.01, -1, 1.01, 2, 100.0, float("nan"), float("inf"), "high", None])
def test_invalid_confidence_rejected(bad):
    with pytest.raises(ValidationError) as exc_info:
        AnalysisFinding(**finding_data(confidence=bad))
    assert "confidence" in str(exc_info.value)


@pytest.mark.parametrize("ok", [0, 0.0, 0.5, 1, 1.0])
def test_confidence_boundaries_accepted(ok):
    finding = AnalysisFinding(**finding_data(confidence=ok))
    assert 0.0 <= finding.confidence <= 1.0


def test_invalid_confidence_rejected_on_assignment():
    finding = AnalysisFinding(**finding_data())
    with pytest.raises(ValidationError):
        finding.confidence = 1.5


def test_confidence_is_required():
    data = finding_data()
    del data["confidence"]
    with pytest.raises(ValidationError):
        AnalysisFinding(**data)


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("model", "factory"), ALL_MODELS, ids=MODEL_IDS)
def test_json_round_trip(model, factory):
    original = model(**factory())
    as_json = original.model_dump_json()
    assert isinstance(json.loads(as_json), dict)  # valid strict JSON
    restored = model.model_validate_json(as_json)
    assert restored == original


@pytest.mark.parametrize(("model", "factory"), ALL_MODELS, ids=MODEL_IDS)
def test_model_dump_is_json_serializable(model, factory):
    obj = model(**factory())
    # Both the python-mode dump (str-based enums) and json-mode dump must work.
    json.dumps(obj.model_dump(), allow_nan=False)
    json.dumps(obj.model_dump(mode="json"), allow_nan=False)


def test_enums_serialize_as_plain_strings():
    payload = json.loads(AnalysisFinding(**finding_data()).model_dump_json())
    assert payload["severity"] == "WARNING"
    assert payload["source"] == "PYLINT"
    assert payload["disposition"] == "ACCEPTED"
    assert payload["confidence"] == 0.9


def test_nested_json_round_trip_preserves_types():
    result = ReviewResult(**review_data())
    restored = ReviewResult.model_validate_json(result.model_dump_json())
    assert isinstance(restored.findings[0], AnalysisFinding)
    assert isinstance(restored.comments[0], ReviewComment)
    assert restored.findings[0].severity is Severity.WARNING


@pytest.mark.parametrize("model_cls", [CodeUnit, AnalysisFinding])
def test_non_json_serializable_metadata_rejected(model_cls):
    factory = unit_data if model_cls is CodeUnit else finding_data
    with pytest.raises(ValidationError):
        model_cls(**factory(metadata={"bad": {1, 2, 3}}))
    with pytest.raises(ValidationError):
        model_cls(**factory(metadata={"bad": object()}))
    with pytest.raises(ValidationError):
        model_cls(**factory(metadata={"bad": math.nan}))


# ---------------------------------------------------------------------------
# Nested model creation
# ---------------------------------------------------------------------------


def test_pr_context_builds_nested_models_from_dicts():
    pr = PRContext(**pr_data())
    assert isinstance(pr.changed_files[0], ChangedFile)
    assert isinstance(pr.changed_files[0].changed_regions[0], ChangedRegion)
    assert pr.changed_files[0].status is FileStatus.MODIFIED
    assert pr.changed_files[0].changed_regions[0].new_count == 5


def test_nested_models_can_be_passed_as_instances():
    region = ChangedRegion(**region_data())
    changed = ChangedFile(**file_data(changed_regions=[region]))
    pr = PRContext(**pr_data(changed_files=[changed]))
    assert pr.changed_files[0].changed_regions[0] == region


def test_analysis_result_builds_nested_models():
    result = AnalysisResult(**analysis_data())
    assert isinstance(result.rules[0], RepositoryRule)
    assert isinstance(result.code_units[0], CodeUnit)
    assert isinstance(result.findings[0], AnalysisFinding)
    assert result.rules[0].severity is Severity.ERROR
    assert result.rules[0].verification_status is VerificationStatus.VIOLATION
    assert result.code_units[0].metadata["complexity"] == 4


def test_review_result_builds_nested_models():
    review = ReviewResult(**review_data())
    assert isinstance(review.findings[0], AnalysisFinding)
    assert isinstance(review.comments[0], ReviewComment)
    assert review.comments[0].finding_ids == [review.findings[0].finding_id]


def test_invalid_nested_value_is_rejected_with_location():
    bad = review_data(findings=[finding_data(confidence=3)])
    with pytest.raises(ValidationError) as exc_info:
        ReviewResult(**bad)
    assert exc_info.value.errors()[0]["loc"][:2] == ("findings", 0)


def test_deeply_nested_invalid_value_is_rejected():
    bad = pr_data(changed_files=[file_data(changed_regions=[region_data(new_start=-1)])])
    with pytest.raises(ValidationError):
        PRContext(**bad)


# ---------------------------------------------------------------------------
# Additional validation behaviour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "factory", "field", "value"),
    [
        (PRContext, pr_data, "pr_number", 0),
        (PRContext, pr_data, "repository", ""),
        (ChangedFile, file_data, "additions", -1),
        (ChangedFile, file_data, "path", ""),
        (ChangedRegion, region_data, "old_count", -1),
        (CodeUnit, unit_data, "start_line", 0),
        (AnalysisFinding, finding_data, "start_line", 0),
        (AnalysisFinding, finding_data, "finding_id", ""),
        (ReviewComment, comment_data, "start_line", 0),
        (ReviewResult, review_data, "critical_count", -1),
    ],
)
def test_out_of_range_or_empty_values_rejected(model, factory, field, value):
    with pytest.raises(ValidationError):
        model(**factory(**{field: value}))


@pytest.mark.parametrize(
    ("model", "factory"),
    [(CodeUnit, unit_data), (AnalysisFinding, finding_data), (ReviewComment, comment_data)],
    ids=["CodeUnit", "AnalysisFinding", "ReviewComment"],
)
def test_end_line_before_start_line_rejected(model, factory):
    with pytest.raises(ValidationError):
        model(**factory(start_line=20, end_line=10))


def test_finding_end_line_without_start_line_rejected():
    with pytest.raises(ValidationError):
        AnalysisFinding(**finding_data(start_line=None, end_line=5))


def test_finding_without_line_numbers_is_valid():
    finding = AnalysisFinding(**finding_data(start_line=None, end_line=None))
    assert finding.start_line is None and finding.end_line is None


def test_review_comment_end_line_optional():
    assert ReviewComment(**comment_data(end_line=None)).end_line is None


@pytest.mark.parametrize(("model", "factory"), ALL_MODELS, ids=MODEL_IDS)
def test_unknown_fields_are_rejected(model, factory):
    with pytest.raises(ValidationError):
        model(**factory(unexpected_field="nope"))


@pytest.mark.parametrize(("model", "factory"), ALL_MODELS, ids=MODEL_IDS)
def test_missing_required_fields_rejected(model, factory):
    with pytest.raises(ValidationError):
        model()


# ---------------------------------------------------------------------------
# Contract v1 guard tests: exact enum values and field names/order
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("enum_cls", "expected"),
    [
        (Severity, ["CRITICAL", "ERROR", "WARNING", "INFO"]),
        (VerificationStatus, ["COMPLIANT", "VIOLATION", "UNCERTAIN"]),
        (
            FindingSource,
            ["AST", "TREE_SITTER", "PYLINT", "FLAKE8", "SECURITY_RULE", "COMPLEXITY", "LLM"],
        ),
        (FindingDisposition, ["ACCEPTED", "REJECTED", "UNCERTAIN"]),
        (FileStatus, ["ADDED", "MODIFIED", "DELETED", "RENAMED", "COPIED", "UNKNOWN"]),
    ],
    ids=["Severity", "VerificationStatus", "FindingSource", "FindingDisposition", "FileStatus"],
)
def test_contract_v1_enum_values(enum_cls, expected):
    assert [member.name for member in enum_cls] == expected
    assert [member.value for member in enum_cls] == expected


CONTRACT_V1_FIELDS = {
    ChangedRegion: ["file", "old_start", "old_count", "new_start", "new_count", "patch"],
    ChangedFile: [
        "path", "status", "additions", "deletions", "patch", "language", "changed_regions",
    ],
    PRContext: [
        "repository", "owner", "repository_name", "pr_number", "base_sha", "head_sha",
        "changed_files", "description", "base_branch", "head_branch",
    ],
    RepositoryRule: [
        "rule_id", "source_document", "category", "title", "description", "severity",
        "rule_type", "scope", "original_text", "machine_checkable", "verification_status",
    ],
    CodeUnit: [
        "file", "language", "node_type", "name", "start_line", "end_line", "parent", "metadata",
    ],
    AnalysisFinding: [
        "finding_id", "source", "rule_id", "file", "start_line", "end_line", "severity",
        "title", "message", "evidence", "recommendation", "confidence", "deterministic",
        "disposition", "changed_line", "metadata",
    ],
    AnalysisResult: [
        "analysis_id", "pr_number", "head_sha", "rules", "code_units", "findings", "summary",
    ],
    ReviewComment: ["file", "start_line", "end_line", "severity", "body", "finding_ids"],
    ReviewResult: [
        "review_id", "pr_number", "head_sha", "summary", "findings", "comments",
        "block_merge", "critical_count", "error_count", "warning_count", "info_count",
    ],
}


@pytest.mark.parametrize(
    ("model", "expected"),
    list(CONTRACT_V1_FIELDS.items()),
    ids=[m.__name__ for m in CONTRACT_V1_FIELDS],
)
def test_contract_v1_field_names_are_frozen(model, expected):
    assert list(model.model_fields) == expected
