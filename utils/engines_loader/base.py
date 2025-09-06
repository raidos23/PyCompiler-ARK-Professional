# SPDX-License-Identifier: GPL-3.0-only
# Base interface for pluggable compilation engines

from __future__ import annotations

from typing import Optional, Tuple, List, Dict

class CompilerEngine:
    """
    Base class for a pluggable compilation engine.

    An engine is responsible for:
    - building the command (program, args) for a given file and GUI state
    - performing preflight checks (venv tools, system dependencies)
    - post-success hooks (e.g., open output folder)

    Engines must be stateless or keep minimal transient state; GUI state is
    provided via the `gui` object.
    """

    id: str = "base"
    name: str = "BaseEngine"

    def preflight(self, gui, file: str) -> bool:
        """Perform preflight checks and setup. Return True if OK, False to abort."""
        return True

    def build_command(self, gui, file: str) -> List[str]:
        """Return the full command list including the program at index 0."""
        raise NotImplementedError

    def program_and_args(self, gui, file: str) -> Optional[Tuple[str, List[str]]]:
        """
        Resolve the program (executable path) and its arguments for QProcess.
        Default implementation splits build_command into program and args.
        Return None to abort.
        """
        cmd = self.build_command(gui, file)
        if not cmd:
            return None
        return cmd[0], cmd[1:]

    def on_success(self, gui, file: str) -> None:
        """Hook called when a build is successful."""
        pass

    def create_tab(self, gui):
        """
        Optionally create and return a QWidget tab and its label for the GUI.
        Return value: (widget, label: str) or None if the engine does not add a tab.
        The engine is responsible for creating its own controls and wiring signals.
        """
        return None

    def environment(self, gui, file: str) -> Optional[Dict[str, str]]:
        """
        Optionally return a mapping of environment variables to inject for the engine process.
        Values here will override the current process environment. Return None for no changes.
        """
        return None
