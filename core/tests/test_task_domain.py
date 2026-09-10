from itertools import pairwise

import pytest

from nidavelir_core.tasks.domain import (
    InvalidTaskTransition,
    TaskState,
    allowed_transitions,
    ensure_transition_allowed,
)


def test_happy_path_lifecycle_is_allowed() -> None:
    lifecycle = [
        TaskState.BACKLOG,
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.AGENT_DONE,
        TaskState.VALIDATING,
        TaskState.APPROVED,
        TaskState.MERGED,
        TaskState.CLOSED,
    ]

    for current, requested in pairwise(lifecycle):
        ensure_transition_allowed(current, requested)


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(InvalidTaskTransition) as error:
        ensure_transition_allowed(TaskState.BACKLOG, TaskState.RUNNING)

    assert error.value.current is TaskState.BACKLOG
    assert error.value.requested is TaskState.RUNNING


def test_needs_changes_can_be_queued_again() -> None:
    assert TaskState.QUEUED in allowed_transitions(TaskState.NEEDS_CHANGES)


def test_terminal_states_have_no_follow_up() -> None:
    assert allowed_transitions(TaskState.CLOSED) == ()
    assert allowed_transitions(TaskState.CANCELLED) == ()
