"""Reusable wizard abstraction with pluggable I/O.

The ``WizardIO`` protocol defines how a wizard interacts with the user
(prompts, progress feedback, display).  Each frontend (CLI, web UIX)
provides its own implementation.

Usage::

    from iconfucius.wizard import Wizard

    wiz = Wizard(my_io_adapter)
    if wiz.ask("Continue?", default_yes=True):
        result = wiz.run("Working...", some_func, arg1, arg2)
        wiz.show(result)
"""

from typing import Any, Callable, Protocol


class WizardIO(Protocol):
    """I/O adapter for wizard interactions.  Implement per frontend."""

    def prompt_yn(self, question: str, default_yes: bool = True) -> bool:
        """Ask a yes/no question.  Return True for yes, False for no."""
        ...

    def run_with_feedback(
        self, label: str, func: Callable, *args: Any, **kwargs: Any,
    ) -> Any:
        """Run *func* with progress feedback (spinner, progress bar, …)."""
        ...

    def display(self, text: str) -> None:
        """Show text to the user."""
        ...


class Wizard:
    """A sequence of interactive steps with pluggable I/O."""

    def __init__(self, io: WizardIO) -> None:
        self.io = io

    def ask(self, question: str, default_yes: bool = True) -> bool:
        """Ask a yes/no question."""
        return self.io.prompt_yn(question, default_yes)

    def run(self, label: str, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Run *func* with progress feedback."""
        return self.io.run_with_feedback(label, func, *args, **kwargs)

    def show(self, text: str) -> None:
        """Display text to the user."""
        self.io.display(text)
