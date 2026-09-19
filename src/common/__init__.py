"""Shared integration contract package (Contract v1).

Import shared models from here or from ``src.common.models``.
Do not rename, remove, or change these models without an explicit,
team-approved contract proposal. See ``src/common/models.py``.
"""

from src.common.models import (
    CONTRACT_VERSION,
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

__all__ = [
    "CONTRACT_VERSION",
    "Severity",
    "VerificationStatus",
    "FindingSource",
    "FindingDisposition",
    "FileStatus",
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
