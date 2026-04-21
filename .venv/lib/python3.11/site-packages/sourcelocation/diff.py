from __future__ import annotations

__all__ = (
    "ContextLine",
    "DeletedLine",
    "Diff",
    "FileDiff",
    "FileHunk",
    "Hunk",
    "HunkLine",
    "InsertedLine",
)

import abc
import typing as t
from dataclasses import dataclass


class HunkLine(abc.ABC):
    pass


@dataclass(frozen=True)
class InsertedLine(HunkLine):
    line: str

    def __str__(self) -> str:
        return f"+{self.line}"


@dataclass(frozen=True)
class DeletedLine(HunkLine):
    line: str

    def __str__(self) -> str:
        return f"-{self.line}"


@dataclass(frozen=True)
class ContextLine(HunkLine):
    line: str

    def __str__(self) -> str:
        return f" {self.line}"


@dataclass(frozen=True)
class Hunk:
    old_start_at: int
    new_start_at: int
    lines: t.Sequence[HunkLine]

    @classmethod
    def read_next(cls, lines: list[str]) -> Hunk:
        """Reads the next hunk from a line buffer from a unified format diff."""
        header = lines[0]
        assert header.startswith("@@ -")

        # sometimes the first line can occur on the same line as the header.
        # in that case, we inject a new line into the buffer
        end_header_at = header.index(" @@")
        bonus_line = header[end_header_at+3:]
        if bonus_line != "":
            lines.insert(1, bonus_line)

        header = header[4:end_header_at]
        left, _, right = header.partition(" +")
        old_start_at = int(left.split(",")[0])
        new_start_at = int(right.split(",")[0])

        old_line_num = old_start_at
        new_line_num = new_start_at
        _last_insertion_at = old_start_at

        hunk_lines: list[HunkLine] = []
        while True:
            # discarding the previous line ensures that we only consume lines
            # from the line buffer that belong to the hunk
            lines.pop(0)
            if not lines:
                break

            line = lines[0]

            # inserted line
            if line.startswith("+"):
                hunk_lines.append(InsertedLine(line[1:]))
                new_line_num += 1

            # deleted line
            elif line.startswith("-"):
                hunk_lines.append(DeletedLine(line[1:]))
                old_line_num += 1

            # context line
            elif line.startswith(" "):
                hunk_lines.append(ContextLine(line[1:]))
                new_line_num += 1
                old_line_num += 1

            # end of hunk
            else:
                break

        return Hunk(old_start_at, new_start_at, hunk_lines)

    def __str__(self) -> str:
        """Returns contents of this hunk as part of a unified format diff."""
        num_deleted = sum(
            1 for line in self.lines if isinstance(line, DeletedLine)
        )
        num_inserted = sum(
            1 for line in self.lines if isinstance(line, InsertedLine)
        )
        num_context = sum(
            1 for line in self.lines if isinstance(line, ContextLine)
        )

        num_old_lines = num_context + num_deleted
        num_new_lines = num_context + num_inserted

        header = "@@ -{},{} +{},{} @@"
        header = header.format(
            self.old_start_at,
            num_old_lines,
            self.new_start_at,
            num_new_lines,
        )
        body = [str(line) for line in self.lines]
        return "\n".join([header, *body])


@dataclass(frozen=True)
class FileHunk:
    old_filename: str
    new_filename: str
    hunk: Hunk


@dataclass(frozen=True)
class FileDiff:
    """Represents a set of changes to a single text-based file."""
    old_filename: str
    new_filename: str
    hunks: t.Sequence[Hunk]

    @classmethod
    def read_next(cls, lines: list[str]) -> FileDiff:
        """Reads the next file diff from the line buffer."""
        # keep munching lines until we hit one starting with '---'
        while True:
            if not lines:
                error = "illegal file diff format: couldn't find line starting with '---'"
                raise ValueError(error)
            line = lines[0]
            if line.startswith("---"):
                break
            lines.pop(0)

        assert lines[0].startswith("---")
        assert lines[1].startswith("+++")
        old_filename = lines.pop(0)[4:].strip()
        new_filename = lines.pop(0)[4:].strip()

        hunks: list[Hunk] = []
        while lines:
            if not lines[0].startswith("@@"):
                break
            hunk = Hunk.read_next(lines)
            hunks.append(hunk)

        return FileDiff(
            old_filename=old_filename,
            new_filename=new_filename,
            hunks=hunks,
        )

    @property
    def file_hunks(self) -> t.Iterator[FileHunk]:
        for hunk in self.hunks:
            yield FileHunk(
                old_filename=self.old_filename,
                new_filename=self.new_filename,
                hunk=hunk,
            )

    def __str__(self) -> str:
        """Returns a string encoding of this file diff in the unified diff format."""
        old_filename_line = f"--- {self.old_filename}"
        new_filename_line = f"+++ {self.new_filename}"
        lines = [old_filename_line, new_filename_line]
        lines += [str(h) for h in self.hunks]
        return "\n".join(lines)


@dataclass(frozen=True)
class Diff:
    """Represents a set of changes to one-or-more text-based files."""
    file_diffs: t.Sequence[FileDiff]

    @classmethod
    def from_file_hunks(cls, file_hunks: list[FileHunk]) -> Diff:
        """Constructs a Diff from a list of FileHunks."""
        # group by file
        old_and_new_filename_to_hunks: dict[tuple[str, str], list[Hunk]] = {}
        for file_hunk in file_hunks:
            key = (file_hunk.old_filename, file_hunk.new_filename)
            if key not in old_and_new_filename_to_hunks:
                old_and_new_filename_to_hunks[key] = []
            old_and_new_filename_to_hunks[key].append(file_hunk.hunk)

        # transform each group into a FileDiff
        file_diffs: list[FileDiff] = []
        for (old_filename, new_filename) in old_and_new_filename_to_hunks:
            hunks = old_and_new_filename_to_hunks[(old_filename, new_filename)]
            file_diff = FileDiff(
                old_filename=old_filename,
                new_filename=new_filename,
                hunks=hunks,
            )
            file_diffs.append(file_diff)

        return Diff(file_diffs)

    @classmethod
    def from_unidiff(cls, diff: str) -> Diff:
        """Constructs a Diff from a provided unified format diff."""
        lines = diff.split("\n")
        file_diffs: list[FileDiff] = []

        while lines:
            if lines[0] == "" or lines[0].isspace():
                lines.pop(0)
                continue
            file_diff = FileDiff.read_next(lines)
            file_diffs.append(file_diff)

        return Diff(file_diffs)

    @property
    def files(self) -> list[str]:
        """Returns a list of the names of the files that are changed by this diff."""
        return [fp.old_filename for fp in self.file_diffs]

    @property
    def file_hunks(self) -> t.Iterator[FileHunk]:
        for file_diff in self.file_diffs:
            yield from file_diff.file_hunks

    def __str__(self) -> str:
        """Returns the contents of this diff as a unified format diff."""
        file_diff = [str(p) for p in self.file_diffs]
        return "\n".join([*file_diff, ""])
