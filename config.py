"""
Configuration: API key, model and analysis settings.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
API_KEY_PREFIX = "sk-ant-"
ANTHROPIC_API_KEY = os.getenv(API_KEY_ENV_VAR)


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


# Fail fast: a missing key would otherwise surface as an error from every evaluator.
if not ANTHROPIC_API_KEY or not ANTHROPIC_API_KEY.startswith(API_KEY_PREFIX):
    raise ConfigurationError(
        f"{API_KEY_ENV_VAR} is missing or invalid "
        f"(expected a key starting with '{API_KEY_PREFIX}').\n"
        "Copy .env.example to .env in the project root and set your API key there."
    )

MODEL = "claude-sonnet-4-6"

# USD per million tokens: (input, output). Used only for the cost estimate
# printed after a run; check https://www.anthropic.com/pricing when changing MODEL.
MODEL_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.00, 15.00),
}

# Per-evaluator output limit; a truncated response is treated as an error.
MAX_TOKENS = 16000

# Lenses to run, by key (see evaluators/lenses.py for all eight).
# Evaluators run sequentially for now, so each extra lens adds ~1 minute.
ENABLED_LENSES = (
    "profitable_designer",
    "no_code_stack",
    "launch_expert",
    "churn_eliminator",
    "reality_auditor",
)
