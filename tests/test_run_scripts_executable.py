"""Every tool's run.py must be committed as executable.

Stavrobot spawns run.py directly, so a missing executable bit fails with EACCES before any
plugin code runs. The check reads the git index, not the working-tree file mode, because the
committed mode is what Stavrobot receives."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_all_run_scripts_are_executable_in_git():
    output = subprocess.run(
        ["git", "ls-files", "-s", "--", "*/run.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    entries = [line.split(maxsplit=3) for line in output.splitlines()]
    assert entries, "no run.py files found in the git index"
    not_executable = [entry[3] for entry in entries if entry[0] != "100755"]
    assert not not_executable, f"run.py files not committed as 100755: {not_executable}"
