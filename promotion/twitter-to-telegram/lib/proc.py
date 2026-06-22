"""Run subprocesses with a hard timeout that kills the whole process group.

A plain `subprocess.run(timeout=...)` only kills the direct child on timeout, so
a yt-dlp / gallery-dl / ffmpeg that has spawned its own children can linger and
keep the task alive. We start the child in a new session and, on timeout, kill
the entire process group so nothing is left hanging.
"""

from __future__ import annotations

import os
import signal
import subprocess


class ProcessTimeout(Exception):
    def __init__(self, cmd: list[str], timeout: float):
        super().__init__(f"{cmd[0]} timed out after {timeout}s")
        self.cmd = cmd
        self.timeout = timeout


def run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    """Run `cmd`, capturing stdout/stderr as text. Raise ProcessTimeout on hang."""
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()  # reap the killed group
            raise ProcessTimeout(cmd, timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
