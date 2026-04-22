"""Direction of a specific submodel element."""

from enum import Enum


class Direction(str, Enum):
    """Direction of a specific submodel element.

    :param INPUT: Input direction.
    :param OUTPUT: Output direction.
    """

    INPUT = "input"
    OUTPUT = "output"
