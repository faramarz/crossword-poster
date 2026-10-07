"""Exception types for problems the user can fix (bad input, missing browser), as opposed to bugs."""

from __future__ import annotations


class UserError(Exception):
    """A problem with the user's input or environment.

    The command line prints ``message`` (and ``hint`` when given) in plain language instead of a traceback.
    """

    exit_code = 2

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return self.message if not self.hint else f"{self.message}\n  How to fix: {self.hint}"


class EnvironmentProblem(UserError):
    """The machine is missing something the tool needs (for example Chromium)."""

    exit_code = 3


class IncompleteGrid(UserError):
    """Some answers did not fit and the user asked (``--require-all``) for that to be an error."""

    exit_code = 1
