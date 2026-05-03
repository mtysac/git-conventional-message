"""Config file support for git-msg.

Reads ~/.git-msg.toml and merges with CLI args.
CLI args always take precedence over config file values.

Example ~/.git-msg.toml:
    model = "mistral"
    scope = true
    verbose = false
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH: Path = Path.home() / ".git-msg.toml"

DEFAULTS: dict = {
    "model": os.environ.get("OLLAMA_MODEL", "llama3"),
    "ollama_url": os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    "scope": False,
    "verbose": False,
}


@dataclass
class Config:
    model: str = field(default_factory=lambda: DEFAULTS["model"])
    ollama_url: str = field(default_factory=lambda: DEFAULTS["ollama_url"])
    scope: bool = False
    verbose: bool = False

    @classmethod
    def load(cls) -> "Config":
        """Load config from ~/.git-msg.toml if it exists, else return defaults."""
        config = cls()

        if not CONFIG_PATH.exists():
            logger.debug("No config file found at %s, using defaults.", CONFIG_PATH)
            return config

        # Use tomllib (Python 3.11+) or fall back to manual parsing
        try:
            if sys.version_info >= (3, 11):
                import tomllib
                with open(CONFIG_PATH, "rb") as f:
                    data = tomllib.load(f)
            else:
                data = _parse_toml_simple(CONFIG_PATH)

            config.model = str(data.get("model", config.model))
            config.ollama_url = str(data.get("ollama_url", config.ollama_url))
            config.scope = bool(data.get("scope", config.scope))
            config.verbose = bool(data.get("verbose", config.verbose))
            logger.debug("Loaded config from %s: %s", CONFIG_PATH, data)

        except Exception as e:
            logger.warning("Could not parse %s: %s — using defaults.", CONFIG_PATH, e)

        return config


def _parse_toml_simple(path: Path) -> dict:
    """Minimal TOML parser for Python < 3.11 (handles flat key=value only)."""
    data: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if value.lower() == "true":
                    data[key] = True
                elif value.lower() == "false":
                    data[key] = False
                else:
                    data[key] = value
    return data


def write_example_config() -> None:
    """Write an example config to ~/.git-msg.toml if it doesn't exist."""
    if CONFIG_PATH.exists():
        print(f"Config already exists at {CONFIG_PATH}")
        return
    CONFIG_PATH.write_text(
        '# git-msg configuration\n'
        '# model = "llama3"\n'
        '# ollama_url = "http://localhost:11434"\n'
        '# scope = false\n'
        '# verbose = false\n',
        encoding="utf-8",
    )
    print(f"Example config written to {CONFIG_PATH}")
