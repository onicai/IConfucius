"""Tests for iconfucius.wizard — reusable wizard abstraction."""

from unittest.mock import MagicMock

from iconfucius.wizard import Wizard


def _make_io(**overrides):
    """Build a mock WizardIO with optional method overrides."""
    io = MagicMock()
    for name, impl in overrides.items():
        setattr(io, name, impl)
    return io


# ---------------------------------------------------------------------------
# Wizard.ask
# ---------------------------------------------------------------------------


class TestWizardAsk:
    def test_delegates_to_prompt_yn(self):
        io = _make_io(prompt_yn=MagicMock(return_value=True))
        wiz = Wizard(io)
        assert wiz.ask("Continue?") is True
        io.prompt_yn.assert_called_once_with("Continue?", True)

    def test_passes_default_yes_false(self):
        io = _make_io(prompt_yn=MagicMock(return_value=False))
        wiz = Wizard(io)
        assert wiz.ask("Proceed?", default_yes=False) is False
        io.prompt_yn.assert_called_once_with("Proceed?", False)


# ---------------------------------------------------------------------------
# Wizard.run
# ---------------------------------------------------------------------------


class TestWizardRun:
    def test_delegates_to_run_with_feedback(self):
        io = _make_io(run_with_feedback=MagicMock(return_value=42))
        wiz = Wizard(io)
        result = wiz.run("Working...", lambda x: x + 1, 10)
        assert result == 42
        io.run_with_feedback.assert_called_once()
        args = io.run_with_feedback.call_args
        assert args[0][0] == "Working..."

    def test_passes_kwargs(self):
        io = _make_io(run_with_feedback=MagicMock(return_value="ok"))
        wiz = Wizard(io)
        wiz.run("Label", str, 123, encoding="utf-8")
        call_kwargs = io.run_with_feedback.call_args.kwargs
        assert call_kwargs["encoding"] == "utf-8"


# ---------------------------------------------------------------------------
# Wizard.show
# ---------------------------------------------------------------------------


class TestWizardShow:
    def test_delegates_to_display(self):
        io = _make_io()
        wiz = Wizard(io)
        wiz.show("Hello, world!")
        io.display.assert_called_once_with("Hello, world!")
