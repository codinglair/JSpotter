"""Shared profile and path handling for JSpotter scripts."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def profile_dir(value: str | Path | None) -> Path:
    """Resolve a profile directory without requiring it to already exist."""
    path = Path(value) if value else REPO_ROOT
    return path.expanduser().resolve()


def load_profile_config(directory: str | Path | None) -> tuple[Path, dict]:
    directory = profile_dir(directory)
    path = directory / "config.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"Profile configuration not found: {path}. "
            "Copy templates/config.template.json into the profile directory."
        )
    with path.open(encoding="utf-8") as handle:
        return directory, json.load(handle)


def configured_path(directory: Path, config: dict, key: str, default: str) -> Path:
    paths = config.get("paths", {})
    legacy = {
        "journal": config.get("journal", {}).get("path"),
        "output": config.get("output_dir"),
        "resume_output": config.get("resume_dir"),
    }
    value = paths.get(key, legacy.get(key) or default)
    path = Path(value)
    return path if path.is_absolute() else directory / path


def add_profile_argument(parser) -> None:
    parser.add_argument(
        "--profile-dir",
        default=None,
        help="Directory containing config.json, MASTER_PROFILE.md, journal, and outputs",
    )


def safe_output_path(path: Path, overwrite: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
    return path
