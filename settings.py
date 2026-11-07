"""Load Gemini settings from the repository .env without exposing secrets."""
import os
from pathlib import Path
import shlex

ENV_FILE = Path(__file__).resolve().with_name(".env")


def gemini_settings(default_model, env_file=None):
    """Explicit process variables override .env, including an empty API key.

    Supports KEY=value, optional export, quotes, and comments. Values are
    literal; shell commands and variable references are never evaluated.
    """
    values = {}
    try:
        contents = Path(env_file or ENV_FILE).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        contents = ""
    for line in contents.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in ("GEMINI_API_KEY", "GEMINI_MODEL"):
            continue
        try:
            tokens = shlex.split(value, comments=True, posix=True)
        except ValueError:
            continue
        if len(tokens) <= 1:
            values[key] = tokens[0] if tokens else ""
    return (
        os.environ.get("GEMINI_API_KEY", values.get("GEMINI_API_KEY", "")).strip(),
        os.environ.get("GEMINI_MODEL", values.get("GEMINI_MODEL", default_model)).strip(),
    )
