"""Runs Django in a child process with its own environment. Settings are read once at import time, so tests
that need DJANGO_DEBUG off (or a missing key) can't change them inside the test process."""

import os
import secrets
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]


def long_random_key() -> str:
    """A key that passes Django's deploy check (50+ characters, many distinct ones), new on every run."""
    return secrets.token_urlsafe(50)


def child_env(overrides: dict | None = None) -> dict:
    """The parent environment without any DJANGO_* variable, then DEBUG off and a random key. A value of None
    in `overrides` removes that variable."""
    env = {name: value for name, value in os.environ.items() if not name.startswith("DJANGO_")}
    env.update(
        DJANGO_SETTINGS_MODULE="config.settings",
        DJANGO_DEBUG="false",
        DJANGO_SECRET_KEY=long_random_key(),
    )
    for name, value in (overrides or {}).items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def manage(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run `manage.py <args>` from the backend folder."""
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=BACKEND,
        env=child_env(env),
        capture_output=True,
        text=True,
        timeout=180,
    )


def python(code: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a snippet of Python with Django's settings, from the backend folder."""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND,
        env=child_env(env),
        capture_output=True,
        text=True,
        timeout=180,
    )
