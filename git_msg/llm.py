"""LLM integration for git-msg — Ollama backend."""

import json
import logging
import sys
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

CONVENTIONAL_TYPES: tuple = (
    "feat", "fix", "docs", "style", "refactor",
    "perf", "test", "chore", "ci", "build", "revert",
)

SYSTEM_PROMPT_NO_SCOPE: str = """You are an expert at writing Git conventional commit messages.

Given a git diff, output a single line in exactly this format:
<type>: <description>

Where type is one of: feat fix docs style refactor perf test chore ci build revert
Description: imperative mood, lowercase, no period, MUST be under 50 characters.

Output the single line only. No explanation. No punctuation at the end."""

SYSTEM_PROMPT_WITH_SCOPE: str = """You are an expert at writing Git conventional commit messages.

Given a git diff, output a single line in exactly this format:
<type>(<scope>): <description>

Where type is one of: feat fix docs style refactor perf test chore ci build revert
Scope: the module, file, or area affected (e.g. auth, api, cli)
Description: imperative mood, lowercase, no period, MUST be under 50 characters.

Output the single line only. No explanation. No punctuation at the end."""


def extract_commit_header(text: str) -> str:
    """Extract just the conventional commit header line from model output.

    Models sometimes prefix the answer with phrases like
    'Here is the commit message:'. This finds the first line that
    looks like a real conventional commit header and returns it.
    """
    for line in text.splitlines():
        line = line.strip()
        if any(line.startswith(t) for t in CONVENTIONAL_TYPES):
            return line
    # Fallback: return the first non-empty line
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return text.strip()


def check_ollama_running(ollama_url: str) -> bool:
    """Return True if the Ollama server is reachable."""
    try:
        urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=3)
        logger.debug("Ollama is reachable at %s", ollama_url)
        return True
    except Exception as e:
        logger.debug("Ollama not reachable: %s", e)
        return False


def list_models(ollama_url: str) -> list[str]:
    """Return a list of model names available in Ollama."""
    try:
        with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=5) as resp:
            data: dict = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.error("Failed to list models: %s", e)
        return []


def generate_commit_message(
    diff: str,
    model: str,
    ollama_url: str,
    use_scope: bool = False,
) -> str:
    """Send the diff to Ollama and return a conventional commit message header."""
    if not check_ollama_running(ollama_url):
        print(
            "Error: Ollama is not running.\n"
            "Start it with:  ollama serve\n"
            f"Then pull a model: ollama pull {model}",
            file=sys.stderr,
        )
        sys.exit(1)

    system_prompt: str = SYSTEM_PROMPT_WITH_SCOPE if use_scope else SYSTEM_PROMPT_NO_SCOPE
    logger.debug("Sending diff to model '%s' (scope=%s)", model, use_scope)

    payload: bytes = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Generate a conventional commit message for this diff:\n\n{diff}",
            },
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 80},
    }).encode()

    req = urllib.request.Request(
        f"{ollama_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body: dict = json.loads(resp.read().decode())
            raw: str = body["message"]["content"]
            logger.debug("Raw model output: %s", raw)
            return extract_commit_header(raw)
    except urllib.error.URLError as e:
        logger.error("Ollama request failed: %s", e)
        print(f"Error communicating with Ollama: {e}", file=sys.stderr)
        sys.exit(1)
