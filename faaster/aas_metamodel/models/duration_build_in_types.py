"""Enumeration listing all xsd build in types with respect to duration."""

from enum import Enum


class DurationBuildInTypes(str, Enum):
    """Enumeration listing all xsd build in types with respect to duration."""

    DAY_TIME_DURATION = "xs: DayTimeDuration"
    YEAR_MONTH_DURATION = "xs: YearMonthDuration"
