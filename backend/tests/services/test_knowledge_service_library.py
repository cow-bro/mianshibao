from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.models.knowledge_learning_progress import LearningStatus
from app.services.knowledge_service import KnowledgeService


def test_build_visibility_filters_public_mode():
    filters, params = KnowledgeService._build_visibility_filters("PUBLIC", user_id=9)
    assert filters == ["owner_user_id IS NULL"]
    assert params == {}


def test_build_visibility_filters_private_requires_user():
    filters, params = KnowledgeService._build_visibility_filters("PRIVATE", user_id=None)
    assert filters == ["1 = 0"]
    assert params == {}


def test_build_visibility_filters_both_with_user():
    filters, params = KnowledgeService._build_visibility_filters("BOTH", user_id=7)
    assert filters == ["(owner_user_id IS NULL OR owner_user_id = :user_id)"]
    assert params == {"user_id": 7}


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("unread", LearningStatus.UNREAD),
        ("READING", LearningStatus.READING),
        ("mastered", LearningStatus.MASTERED),
    ],
)
def test_to_learning_status_valid(raw: str, expected: LearningStatus):
    assert KnowledgeService._to_learning_status(raw) == expected


def test_to_learning_status_invalid_raises():
    with pytest.raises(AppException):
        KnowledgeService._to_learning_status("INVALID")
