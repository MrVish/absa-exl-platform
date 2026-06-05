"""Subprocess helpers shared by checkers.

`run_with_timeout` wraps `subprocess.Popen` with a per-call timeout that
correctly kills the *entire* child process tree on Windows. Plain
`subprocess.run(..., timeout=)` is insufficient here: when it fires
`TimeoutExpired`, the implementation calls `Popen.kill()`, which on
Windows uses `TerminateProcess` on the immediate child only. Grandchildren
keep running, keep the stdout/stderr pipes open, and the subsequent
internal `communicate()` call hangs forever waiting for EOF.

The static_python and tests checkers shell out via `uv run pytest ...`,
which is a three-deep tree (`uv.exe` -> `pytest.exe` -> `python.exe`).
A hung fixture (`time.sleep(99999)` at import time) lives in the leaf
`python.exe`; killing only `uv.exe` leaves pytest+python alive and the
parent wedged. We use `taskkill /T /F` on Windows and `os.killpg` on
POSIX to walk the whole tree.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from pathlib import Path


def _kill_tree(pid: int) -> None:
    """Best-effort recursive kill of the process tree rooted at `pid`.

    Errors are swallowed: the goal is to make the parent's pipes drain
    so `communicate()` can return; if a child has already exited that's
    a no-op success.
    """
    if sys.platform == "win32":
        # /T = tree, /F = force. Returns nonzero if process already gone;
        # we don't care — we just need its pipes closed.
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        # POSIX: send SIGKILL to the whole process group.
        import signal

        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(pid), signal.SIGKILL)


def run_with_timeout(
    cmd: list[str],
    *,
    timeout_seconds: int,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Like `subprocess.run(cmd, capture_output=True, text=True,
    timeout=timeout_seconds)`, but on timeout it kills the *whole*
    process tree before re-raising `subprocess.TimeoutExpired`.

    Raises:
        subprocess.TimeoutExpired: if the process tree did not exit
            within `timeout_seconds`.
    """
    cwd_str = str(cwd) if cwd is not None else None
    if sys.platform == "win32":
        # Put the child in its own process group so taskkill /T finds it
        # even if it daemonises something.
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd_str,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd_str,
            start_new_session=True,
        )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as timeout_err:
        # Kill the *tree* before draining, then drain with a short cap.
        _kill_tree(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            # Tree-kill didn't drain pipes within 5s — give up on output
            # and re-raise. Pipes will be GC'd; the original timeout is
            # what callers care about.
            stdout, stderr = "", ""
        raise subprocess.TimeoutExpired(
            cmd=cmd,
            timeout=timeout_seconds,
            output=stdout,
            stderr=stderr,
        ) from timeout_err
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
    )
