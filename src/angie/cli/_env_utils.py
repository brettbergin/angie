"""Shared .env file read/write utilities for CLI commands."""

from __future__ import annotations

from pathlib import Path

_ENV_PATH = Path(".env")


def read_env(path: Path = _ENV_PATH) -> dict[str, str]:
    """Return the current .env as a dict, preserving existing values."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def write_env(updates: dict[str, str], path: Path = _ENV_PATH) -> None:
    """Write key=value pairs to .env, updating existing keys in-place."""
    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text().splitlines()

    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in updates:
                if updates[key]:
                    new_lines.append(f"{key}={updates[key]}")
                else:
                    new_lines.append(line)  # keep blank values unchanged
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append any keys that weren't already present
    for key, value in updates.items():
        if key not in updated_keys and value:
            new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n")


def mask(value: str | None, show: int = 4) -> str:
    """Return a masked representation of a secret value."""
    if not value:
        return ""
    if len(value) <= show:
        return "*" * len(value)
    return value[:show] + "****"
