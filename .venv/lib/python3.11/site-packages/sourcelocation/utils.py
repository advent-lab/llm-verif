from __future__ import annotations

__all__ = ("dedent",)


def dedent(string: str) -> str:
    def num_leading_spaces(string: str) -> int:
        length = len(string)
        length_without_prefix = len(string.lstrip(" "))
        return length - length_without_prefix

    spaces_to_remove: int | None = None
    lines = string.split("\n")
    for line in lines:
        if not line or line.isspace():
            continue
        leading_spaces = num_leading_spaces(line)
        if spaces_to_remove is None or leading_spaces < spaces_to_remove:
            spaces_to_remove = leading_spaces

    return "\n".join(
        line[spaces_to_remove:] for line in lines
    )
