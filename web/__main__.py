"""
Start the web UI on this machine only:

    python -m web            # http://127.0.0.1:8000
    python -m web --port 8080
"""

import argparse
import logging

import uvicorn

from main import setup_logging
from web.app import create_app

HOST = "127.0.0.1"  # never 0.0.0.0: the API key in .env pays for every run

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Startup Autopsy web UI (local only)")
    parser.add_argument("--port", type=int, default=8000)
    port = parser.parse_args().port

    log_file = setup_logging()
    logger.info(f"Startup Autopsy web UI: http://{HOST}:{port}  (Ctrl+C to stop; log: {log_file})")
    # log_config=None: uvicorn's own messages go through the logging set up above.
    uvicorn.run(create_app(), host=HOST, port=port, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
