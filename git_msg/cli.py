"""CLI entry point and interactive mode for git-msg."""

import argparse
import logging
import sys
from argparse import Namespace

from git_msg.config import Config, write_example_config
from git_msg.git import get_staged_diff, truncate_diff
from git_msg.llm import check_ollama_running, generate_commit_message, list_models

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool) -> None:
    """Configure logging level based on --verbose flag."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=level,
    )


def parse_args(config: Config) -> Namespace:
    """Parse CLI arguments, using config file values as defaults."""
    parser = argparse.ArgumentParser(
        description="Generate a conventional commit message from staged git changes using a local LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  git-msg                    # feat: description\n"
            "  git-msg --scope            # feat(auth): description\n"
            "  git-msg --copy             # generate and copy to clipboard\n"
            "  git-msg --dry-run          # preview diff without calling model\n"
            "  git-msg --list-models      # show available Ollama models\n"
            "  git-msg --init-config      # create ~/.git-msg.toml\n"
        ),
    )
    parser.add_argument(
        "--model", "-m",
        default=config.model,
        help=f"Ollama model to use (default: {config.model})",
    )
    parser.add_argument(
        "--scope", "-s",
        action="store_true",
        default=config.scope,
        help="Include a scope in the message e.g. feat(scope): description",
    )
    parser.add_argument(
        "--copy", "-c",
        action="store_true",
        help="Copy the generated message to clipboard",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Print the diff that would be sent to the model without calling Ollama",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List all models available in Ollama and exit",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Create an example ~/.git-msg.toml config file and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=config.verbose,
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    import subprocess
    try:
        subprocess.run(
            ["clip"],
            input=text.encode("utf-16-le"),
            check=True,
            shell=True,
        )
        return True
    except Exception:
        pass
    for cmd in [["pbcopy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
        try:
            subprocess.run(cmd, input=text.encode(), check=True)
            return True
        except Exception:
            continue
    return False


def interactive_mode(message: str, diff: str, model: str, ollama_url: str, use_scope: bool) -> str:
    """Prompt the user to use, regenerate, edit, or quit after generation."""
    while True:
        print(f"\n  {message}\n")
        print("[u] Use   [r] Regenerate   [e] Edit   [q] Quit")
        choice = input("> ").strip().lower()

        if choice == "u":
            return message
        elif choice == "r":
            print("\nRegenerating...\n", file=sys.stderr)
            message = generate_commit_message(diff, model, ollama_url, use_scope)
        elif choice == "e":
            print("Edit message (press Enter to keep current):")
            edited = input(f"  [{message}] > ").strip()
            if edited:
                message = edited
            return message
        elif choice == "q":
            print("Aborted.")
            sys.exit(0)
        else:
            print("Invalid choice. Enter u, r, e, or q.")


def main() -> None:
    config: Config = Config.load()
    args: Namespace = parse_args(config)

    setup_logging(args.verbose)
    logger.debug("Config loaded: %s", config)
    logger.debug("Args: %s", args)

    # --- Handle utility flags first ---
    if args.init_config:
        write_example_config()
        sys.exit(0)

    if args.list_models:
        if not check_ollama_running(config.ollama_url):
            print("Error: Ollama is not running. Start it with: ollama serve", file=sys.stderr)
            sys.exit(1)
        models = list_models(config.ollama_url)
        if models:
            print("Available models:")
            for m in models:
                marker = " *" if m.startswith(args.model) else ""
                print(f"  {m}{marker}")
        else:
            print("No models found. Pull one with: ollama pull llama3")
        sys.exit(0)

    # --- Main flow ---
    diff: str = get_staged_diff()

    if not diff.strip():
        print("No staged changes found. Stage your changes with `git add` first.")
        sys.exit(0)

    diff = truncate_diff(diff)

    if args.dry_run:
        print("--- Diff that would be sent to the model ---\n")
        print(diff)
        print(f"\n--- Model: {args.model} | Scope: {'yes' if args.scope else 'no'} ---")
        sys.exit(0)

    print(f"Analyzing staged diff with {args.model}...\n", file=sys.stderr)
    message: str = generate_commit_message(diff, args.model, config.ollama_url, use_scope=args.scope)

    # Only run interactive mode when attached to a real terminal
    # Skipped when piping output e.g. git commit -m "$(git-msg)"
    if sys.stdout.isatty() and sys.stdin.isatty():
        message = interactive_mode(message, diff, args.model, config.ollama_url, args.scope)

    print(message)

    if args.copy:
        if copy_to_clipboard(message):
            print("\nCopied to clipboard.", file=sys.stderr)
        else:
            print("\nCould not copy to clipboard.", file=sys.stderr)
