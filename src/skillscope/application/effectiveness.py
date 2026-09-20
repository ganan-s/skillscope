"""Read-time observational signals for skill effectiveness.

These helpers project stored canonical events. They do not score skills.
"""

from __future__ import annotations

from skillscope.application.queries import EffectivenessObservations

_TURN_STATUSES = frozenset({"success", "error", "unknown"})


def observe_activation(
    *,
    turn_index: int | None,
    resource_read_count: int,
    same_path_activation_count: int,
    subsequent_task_count: int,
    turn_status: str | None,
) -> EffectivenessObservations:
    """Return evidence flags for one confirmed skill activation."""
    status = turn_status if turn_status in _TURN_STATUSES else "unknown"
    if turn_index is None:
        subsequent_task_count = 0
        status = "unknown"
    return EffectivenessObservations(
        resource_follow_through=resource_read_count > 0,
        repeated_in_conversation=same_path_activation_count > 1,
        followed_by_user_task=subsequent_task_count > 0,
        containing_turn_status=status,
    )
