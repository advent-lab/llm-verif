"""Provides data structures for representing source code locations.

Implements data structures to represent, e.g., characters, character ranges, lines, etc.
"""
__all__ = (
    "__version__",
    "Diff",
    "FileDiff",
    "FileHunk",
    "FileLine",
    "FileLineMap",
    "FileLineSet",
    "Hunk",
    "Location",
    "LocationRange",
    "FileLocation",
    "FileLocationRange",
    "FileLocationRangeSet",
)
__version__ = "1.1.8"

from sourcelocation.diff import (
    Diff,
    FileDiff,
    FileHunk,
    Hunk,
)
from sourcelocation.fileline import (
    FileLine,
    FileLineMap,
    FileLineSet,
)
from sourcelocation.location import (
    FileLocation,
    FileLocationRange,
    FileLocationRangeSet,
    Location,
    LocationRange,
)
