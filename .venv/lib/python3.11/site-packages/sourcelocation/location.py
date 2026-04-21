from __future__ import annotations

__all__ = (
    "Location",
    "LocationRange",
    "FileLocation",
    "FileLocationRange",
    "FileLocationRangeSet",
)

import os
import typing as _t
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """Represents a character location within an arbitrary file.

    Attributes
    ----------
    line: int
        A one-indexed line number.
    column: int
        A one-indexed column number.

    """

    line: int
    column: int

    @staticmethod
    def from_string(s: str) -> Location:
        line, _, column = s.partition(":")
        return Location(int(line), int(column))

    def __lt__(self, other: _t.Any) -> bool:
        if not isinstance(other, Location):
            return False
        if self.line == other.line:
            return self.column < other.column
        return self.line < other.line

    def __le__(self, other: _t.Any) -> bool:
        return self == other or self.__lt__(other)

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


@dataclass(frozen=True)
class FileLocation:
    """Represents a character location within a particular file.

    Attributes
    ----------
    filename: str
        The name of the file to which the character belongs.
    location: Location
        The location of the character within the given file.

    """

    filename: str
    location: Location

    def with_relative_location(self, base: str) -> FileLocation:
        """Creates a new instance with a relative file location."""
        filename = self.filename
        if os.path.isabs(filename):
            filename = os.path.relpath(filename, base)
        return FileLocation(
            filename,
            self.location,
        )

    def __lt__(self, other: _t.Any) -> bool:
        if not isinstance(other, FileLocation):
            return False
        if self.filename < other.filename:
            return True
        if self.filename > other.filename:
            return False
        return self.location < other.location

    def __le__(self, other: _t.Any) -> bool:
        return self == other or self.__lt__(other)

    @property
    def line(self) -> int:
        """The one-indexed line number for this location."""
        return self.location.line

    @property
    def column(self) -> int:
        """The one-indexed column number for this location."""
        return self.location.column

    @staticmethod
    def from_string(s: str) -> FileLocation:
        filename, _, location_string = s.rpartition("@")
        location = Location.from_string(location_string)
        return FileLocation(filename, location)

    def __str__(self) -> str:
        return f"{self.filename}@{self.location!s}"


@dataclass(frozen=True)
class LocationRange:
    """Captures a contiguous, non-inclusive range of locations."""

    start: Location
    stop: Location

    @staticmethod
    def from_string(s: str) -> LocationRange:
        start_s, _, stop_s = s.partition("::")
        start = Location.from_string(start_s)
        stop = Location.from_string(stop_s)
        return LocationRange(start, stop)

    def __lt__(self, other: _t.Any) -> bool:
        if not isinstance(other, LocationRange):
            return False
        if self.start < other.start:
            return True
        if self.start > other.start:
            return False
        return self.stop < other.stop

    def __le__(self, other: _t.Any) -> bool:
        return self == other or self.__lt__(other)

    def __str__(self) -> str:
        return f"{self.start!s}::{self.stop!s}"

    def __contains__(self, loc: Location) -> bool:
        """Determines whether a given location is within this range."""
        left = loc.line > self.start.line \
            or (loc.line == self.start.line and loc.column >= self.start.column)
        right = loc.line < self.stop.line \
            or (loc.line == self.stop.line and loc.column < self.stop.column)
        return left and right


@dataclass(frozen=True)
class FileLocationRange:
    """Represents a contiguous sequence of characters in a particular file."""

    filename: str
    location_range: LocationRange

    @staticmethod
    def from_string(s: str) -> FileLocationRange:
        filename, _, s_range = s.rpartition("@")
        location_range = LocationRange.from_string(s_range)
        return FileLocationRange(filename, location_range)

    def with_relative_location(self, base: str) -> FileLocationRange:
        """Creates a new instance with a relative file location."""
        filename = self.filename
        if os.path.isabs(filename):
            filename = os.path.relpath(filename, base)
        return FileLocationRange(
            filename,
            self.location_range,
        )

    @property
    def start(self) -> Location:
        """The start of this location range."""
        return self.location_range.start

    @property
    def stop(self) -> Location:
        """The end of this location range."""
        return self.location_range.stop

    def __lt__(self, other: _t.Any) -> bool:
        if not isinstance(other, FileLocationRange):
            return False
        if self.filename < other.filename:
            return True
        if self.filename > other.filename:
            return False
        return self.location_range < other.location_range

    def __le__(self, other: _t.Any) -> bool:
        return self == other or self.__lt__(other)

    def __str__(self) -> str:
        return f"{self.filename}@{self.location_range!s}"

    def __contains__(self, floc: FileLocation) -> bool:
        """Determines whether a given location is within this range."""
        in_file = floc.filename == self.filename
        in_range = floc.location in self.location_range
        return in_file and in_range


class FileLocationRangeSet:
    """An immutable set that is comprised of zero or more nonempty,
    disconnected file location ranges.

    Based on the RangeSet class in Guava.
    """

    def __init__(
        self,
        contents: _t.Iterable[FileLocationRange] | None = None,
    ) -> None:
        self._filename_to_ranges: dict[str, set[FileLocationRange]] = {}
        if not contents:
            contents = []
        for range_ in contents:
            filename = range_.filename
            if filename not in self._filename_to_ranges:
                self._filename_to_ranges[filename] = set()
            self._filename_to_ranges[filename].add(range_)

    def __iter__(self) -> _t.Iterator[FileLocationRange]:
        for ranges in self._filename_to_ranges.values():
            yield from ranges

    def __repr__(self) -> str:
        return f"FileLocationRangeSet({self._filename_to_ranges})"

    def with_relative_locations(self, base: str) -> FileLocationRangeSet:
        """Creates a new instance with relative file locations."""
        return FileLocationRangeSet(
            range_.with_relative_location(base)
            for range_ in self
        )

    def contains(self, location: FileLocation) -> bool:
        """Determines whether a given location is contained within this set."""
        ranges = self._filename_to_ranges.get(location.filename, set())
        return any(location in r for r in ranges)
