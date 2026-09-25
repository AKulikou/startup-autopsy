"""
Startup Autopsy CLI: pick an idea from ideas/ and run the analysis.

All analysis logic lives in core/ and evaluators/; this module handles only
logging setup and interactive idea selection.
"""

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.analysis_runner import AnalysisRunner
from core.idea_processor import IdeaProcessor

LOGS_DIR = Path("logs")
# Third-party loggers that would flood the DEBUG log file. The Anthropic SDK 1.x
# sends requests through httpx2/httpcore2, which log every request at INFO.
NOISY_LOGGERS = ("anthropic", "httpx2", "httpcore2")

logger = logging.getLogger(__name__)


def setup_logging() -> Path:
    """
    Console: one INFO line per event. File: the same plus DEBUG details
    (request ids, stop reasons, tracebacks). Returns the log file path.
    """
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / f"startup_autopsy_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    return log_file


def select_idea(processor: IdeaProcessor) -> str | None:
    """Ask the user to pick an idea by number or name. Returns None to exit."""
    ideas, path = processor.get_available_ideas()

    print("\nSTARTUP AUTOPSY - Business Idea Validator\n")
    if not ideas:
        print(f"No ideas found in {path}")
        return None

    print(f"Ideas in {path}:")
    for i, idea in enumerate(ideas, start=1):
        print(f"  {i:>2}. {idea}")

    choice = input("\nEnter a number or file name (Enter to exit): ").strip()
    if not choice:
        return None

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ideas):
            return ideas[idx]
    elif choice in ideas:
        return choice

    logger.warning(f"Invalid choice: {choice}")
    return None


def ask_analyze_anyway(gate: dict) -> bool:
    """Let the user run the analysis on an idea the input check found too vague."""
    return input("Analyze anyway? [y/N] ").strip().lower() in ("y", "yes")


def main() -> None:
    log_file = setup_logging()
    logger.debug(f"Log file: {log_file.resolve()}")

    processor = IdeaProcessor()
    idea_name = select_idea(processor)
    if not idea_name:
        print("Exit.")
        return

    AnalysisRunner(processor, confirm_vague_idea=ask_analyze_anyway).run(idea_name)
    print(f"Log: {log_file}")


if __name__ == "__main__":
    main()
