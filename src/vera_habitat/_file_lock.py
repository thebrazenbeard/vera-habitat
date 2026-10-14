"""Cross-process advisory single-file lock for opt-in local Habitat saves.

The sidecar is permanent on purpose: deleting lockfiles creates inode races
where different processes hold different locks for the same checkpoint.
Trusted local directory and cooperating writers remain required. Not a
distributed/network filesystem mutex or a defense against hostile OS users.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import stat
import time
from typing import Iterator


@contextmanager
def exclusive_checkpoint_lock(target: Path, timeout_seconds: float) -> Iterator[None]:
    directory = target.parent
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("trusted existing checkpoint directory required")
    sidecar = target.with_name(target.name + ".lock")
    if sidecar.is_symlink():
        raise ValueError("checkpoint lock symlinks are unavailable")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0)
    fd = os.open(sidecar, flags, 0o600)
    locked = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode) or sidecar.is_symlink():
            raise ValueError("checkpoint lock must be a regular, non-symlink file")
        if os.fstat(fd).st_size == 0:
            os.write(fd, bytes([0]))
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                elif os.name == "posix":
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    raise RuntimeError("checkpoint lock platform unsupported")
                locked = True
                break
            except OSError as exc:
                # EACCES/EAGAIN (Unix) and Windows sharing/lock violations.
                if (exc.errno not in (errno.EAGAIN, errno.EACCES)
                        and getattr(exc, "winerror", None) not in (33, 36)):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError("checkpoint write lock is busy") from exc
                time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
        yield
    finally:
        try:
            if locked:
                os.lseek(fd, 0, os.SEEK_SET)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
