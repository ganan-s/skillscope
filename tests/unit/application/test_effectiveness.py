from __future__ import annotations

from skillscope.application.effectiveness import observe_activation


def test_observe_activation_when_follow_through_exists_sets_evidence_flags() -> None:
    observations = observe_activation(
        turn_index=0,
        resource_read_count=1,
        same_path_activation_count=2,
        subsequent_task_count=1,
        turn_status="success",
    )

    assert observations.resource_follow_through is True
    assert observations.repeated_in_conversation is True
    assert observations.followed_by_user_task is True
    assert observations.containing_turn_status == "success"


def test_observe_activation_when_turn_index_is_missing_reports_unknown() -> None:
    observations = observe_activation(
        turn_index=None,
        resource_read_count=0,
        same_path_activation_count=1,
        subsequent_task_count=3,
        turn_status="error",
    )

    assert observations.resource_follow_through is False
    assert observations.repeated_in_conversation is False
    assert observations.followed_by_user_task is False
    assert observations.containing_turn_status == "unknown"
