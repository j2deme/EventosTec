# How to manage the workspace virtualenv

This project keeps a virtualenv folder at `venv/` in the repository root. The workspace is configured to use it by default.

If your virtual environment has a different name or location:

- Edit `.vscode/settings.json` and update `python.defaultInterpreterPath` to point to the correct Python executable.
- Update the PowerShell activation command in `terminal.integrated.profiles.windows` to reference the matching `Activate.ps1` path.

## PowerShell Core (pwsh) users

- The workspace includes a "PowerShell Core (venv)" profile that uses `pwsh` and runs the venv `Activate.ps1` on open. If you prefer `pwsh` and your `pwsh` is in a different path, update the `path` in `.vscode/settings.json`.

## Using the pytest task

- You can run the provided task `Run pytest (venv)` from the Command Palette (Tasks: Run Task) or with the keyboard shortcut for tasks in VS Code. The task runs `python -m pytest` using the configured interpreter in a new terminal.

## Notes

- If you prefer not to auto-activate the venv, change `terminal.integrated.defaultProfile.windows` in `.vscode/settings.json` to your preferred profile.
