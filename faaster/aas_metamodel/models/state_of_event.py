"""State of an event."""

from enum import Enum


class StateOfEvent(str, Enum):
    """State of an event.

    :param ON: Event is on.
    :param OFF: Event is off.
    """

    ON = "on"
    OFF = "off"
