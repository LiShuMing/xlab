"""Optional POSIX PTY acceptance: real TUI, keyboard navigation and terminal restore.

Run after cargo build: python3 tests/terminal_smoke.py
No frame/process data is exported. Only the tested child receives input/signals.
"""

import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import termios
import time

binary = Path(__file__).resolve().parents[1] / "target/debug/mac-lens"
master, slave = pty.openpty()
fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 42, 160, 0, 0))
before = termios.tcgetattr(master)
# Do not execute Python between fork and exec on macOS: CoreFoundation and
# higher-level frameworks may already be initialized in the Python host.
child = subprocess.Popen(
    [str(binary), "--interval-ms", "500"],
    stdin=slave, stdout=slave, stderr=slave,
    start_new_session=True, env={**os.environ, "TERM": "xterm-256color"},
)
os.close(slave)

try:
    frames = bytearray()

    def wait_for(text, timeout=15):
        deadline = time.monotonic() + timeout
        wanted = text.encode()
        while time.monotonic() < deadline:
            if wanted in frames:
                return
            if select.select([master], [], [], 0.1)[0]:
                try:
                    data = os.read(master, 65536)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    break
                if not data:
                    break
                frames.extend(data)
                if len(frames) > 1024 * 1024:
                    del frames[:len(frames) - 1024 * 1024]
        raise AssertionError(f"TUI did not render expected marker: {text}")

    wait_for("CPU / all logical cores")
    os.write(master, b" ")
    wait_for("PAUSED")
    os.write(master, b"\t")
    wait_for("SOURCES / scope")
    exit_key = b"\x03" if "--ctrl-c" in sys.argv[1:] else b"q"
    os.write(master, b"jkmf1 " + exit_key)
    # A terminal emulator keeps draining output while keys are processed. Merely
    # waiting here would fill the PTY output buffer and block the child's draw()
    # before it can consume the queued q, falsely reporting a hung application.
    deadline = time.monotonic() + 5
    while child.poll() is None and time.monotonic() < deadline:
        if select.select([master], [], [], 0.05)[0]:
            try:
                os.read(master, 65536)
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
    assert child.wait(timeout=1) == 0, "TUI returned a failure"
    after = termios.tcgetattr(master)
    mask = termios.ECHO | termios.ICANON
    assert before[3] & mask == after[3] & mask, "terminal echo/canonical mode not restored"
    key_name = "Ctrl-C" if exit_key == b"\x03" else "q"
    print(f"PASS real PTY: dashboard, pause, details, navigation, {key_name} and terminal restoration")
finally:
    os.close(master)
    if child.poll() is None:
        child.kill()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
