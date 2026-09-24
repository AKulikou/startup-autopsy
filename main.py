"""
Startup Autopsy CLI: pick an idea from ideas/ and run the analysis.

All analysis logic lives in core/ and evaluators/; this module handles only
logging setup and interactive idea selection.
"""

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from core.analysis_runner import AnalysisRunner
from core.idea_processor import IdeaProcessor

LOGS_DIR = Path("logs")
NOISY_LOGGERS = ("urllib3", "anthropic", "httpx", "httpcore")

logger = logging.getLogger(__name__)


class HTTPLogFilter(logging.Filter):
    """Hides HTTP request lines from the console."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "HTTP Request:" not in record.getMessage()


def setup_logging() -> Path:
    """Log to a timestamped file and to the console. Returns the log file path."""
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / f"startup_autopsy_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.addFilter(HTTPLogFilter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    return log_file


def select_idea(processor: IdeaProcessor) -> Optional[str]:
    """Ask the user to pick an idea by number or name. Returns None to exit."""
    ideas, path = processor.get_available_ideas()

    logger.info("\n" + "=" * 70)
    logger.info("STARTUP AUTOPSY — Business Idea Validator")
    logger.info("=" * 70)

    if not ideas:
        logger.info(f"\nNo ideas found in {path}")
        return None

    logger.info("\nAvailable ideas:")
    for i, idea in enumerate(ideas, start=1):
        logger.info(f"   {i}. {idea}")

    logger.info(f"\nDirectory: {path}")
    logger.info("-" * 70)

    choice = input("Enter a number or file name (Enter to exit): ").strip()
    if not choice:
        return None

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ideas):
            return ideas[idx]
    elif choice in ideas:
        return choice

    logger.info(f"Invalid choice: {choice}")
    return None


def main() -> None:
    log_file = setup_logging()
    logger.info(f"Logging to: {log_file.resolve()}")

    processor = IdeaProcessor()
    idea_name = select_idea(processor)
    if idea_name:
        AnalysisRunner(processor).run(idea_name)
    else:
        logger.info("Exit.")


if __name__ == "__main__":
    main()
