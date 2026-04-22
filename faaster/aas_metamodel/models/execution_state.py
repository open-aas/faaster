"""Module defining the ExecutionState enumeration."""

from enum import Enum


class ExecutionState(str, Enum):
    """Enumeration for the execution states.

    :param INITIATED: The operation is ready to be executed (initial state).
    :param RUNNING: The operation is running.
    :param COMPLETED: The operation is completed.
    :param CANCELED: The operation was canceled externally.
    :param FAILED: The operation failed.
    :param TIMEOUT: The operation has timed out due to given client or server timeout.
    """

    INITIATED = "Initiated"
    RUNNING = "Running"
    COMPLETED = "Completed"
    CANCELED = "Canceled"
    FAILED = "Failed"
    TIMEOUT = "Timeout"
