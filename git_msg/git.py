"""Git operations for git-msg."""

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS: int = 6000
# Token budget: ~120 system prompt + ~1500 diff + ~80 output = ~1700 total
# Llama3 context window is 8k tokens (~32k chars), so 6000 chars is very safe.


def get_staged_diff() -> str:
    """Run git diff --cached and return the output as a string."""
    logger.debug("Running git diff --cached")
    result = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        logger.error("git diff failed: %s", result.stderr)
        print(f"Error running git diff: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    diff = result.stdout or ""
    logger.debug("Staged diff length: %d chars", len(diff))
    return diff


def truncate_diff(diff: str) -> str:
    """Truncate diff to MAX_DIFF_CHARS, cutting at a clean line boundary."""
    if len(diff) <= MAX_DIFF_CHARS:
        return diff

    logger.warning(
        "Diff is large (%d chars), truncating to %d chars to stay within model context limit.",
        len(diff),
        MAX_DIFF_CHARS,
    )
    print(
        f"Warning: diff is large ({len(diff)} chars), "
        f"truncating to {MAX_DIFF_CHARS} chars to stay within model context limit.\n",
        file=sys.stderr,
    )
    truncated: str = diff[:MAX_DIFF_CHARS]
    last_newline: int = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    return truncated + "\n\n[... diff truncated to fit model context limit ...]"
