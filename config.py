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

# Model for the input check, the lenses and the synthesis. ANALYSIS_MODEL in .env
# overrides it, so an eval run can compare models without a code change.
DEFAULT_MODEL = "claude-sonnet-4-6"
MODEL = os.getenv("ANALYSIS_MODEL", "").strip() or DEFAULT_MODEL

# USD per million tokens: (input, output). Used only for the cost estimate
# printed after a run; check https://www.anthropic.com/pricing when changing MODEL.
MODEL_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    # Prompts up to 100K tokens; longer prompts cost 0.50 / 2.50 (a report is far below).
    "claude-haiku-5-5": (0.10, 0.50),
}

# Thinking before answering, for the lenses and the synthesis (the input check is
# a simple classification and never thinks). "off" or "adaptive" (the model
# decides how much to think). Thinking tokens are billed as output and count
# against MAX_TOKENS. Set THINKING in .env; an experiment until the eval decides.
THINKING_MODES = ("off", "adaptive")
THINKING = os.getenv("THINKING", "").strip().lower() or "off"
if THINKING not in THINKING_MODES:
    raise ConfigurationError(f"THINKING must be one of {', '.join(THINKING_MODES)}, got {THINKING!r}")

# Effort for the lenses and the synthesis: how much the model thinks and writes.
# Unset = the model's default (Opus 5.5: medium; Sonnet 4.6: high). Opus 5.5
# always thinks - THINKING=off only means no thinking parameter is sent - so on
# that model effort is the control for depth, cost and time. Set ANALYSIS_EFFORT
# in .env; Haiku 4.5 rejects it.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
ANALYSIS_EFFORT = os.getenv("ANALYSIS_EFFORT", "").strip().lower() or None
if ANALYSIS_EFFORT and ANALYSIS_EFFORT not in EFFORT_LEVELS:
    raise ConfigurationError(
        f"ANALYSIS_EFFORT must be one of {', '.join(EFFORT_LEVELS)}, got {ANALYSIS_EFFORT!r}"
    )

# Per-evaluator output limit; a truncated response is treated as an error.
MAX_TOKENS = 16000

# Lenses to run, by key (see evaluators/lenses.py for all defined lenses).
# All enabled lenses run at once, so an extra lens adds cost but little wall time.
# Rate limits have room (measured: five parallel lenses used about a quarter of an
# 80k output-tokens-per-minute limit), and the SDK retries 429 responses.
ENABLED_LENSES = (
    "profitable_designer",
    "no_code_stack",
    "launch_expert",
    "churn_eliminator",
    "viral_designer",
    "reality_auditor",
)

# Extra lenses to run after ENABLED_LENSES, for trying a defined lens without
# editing code: comma-separated keys in .env, e.g. EXTRA_LENSES=unit_economics.
# An unknown key fails at startup, like one in ENABLED_LENSES.
def parse_lens_keys(value: str) -> tuple[str, ...]:
    return tuple(key.strip() for key in value.split(",") if key.strip())


EXTRA_LENSES = tuple(
    key for key in parse_lens_keys(os.getenv("EXTRA_LENSES", "")) if key not in ENABLED_LENSES
)

# Optional translated copies of the reports, for readers who prefer another
# language. The analysis always runs in English and the English reports stay the
# source of truth. Set in .env, e.g. REPORT_TRANSLATION=Lithuanian (any language);
# unset = English only. The MCP server can also take the language per call.
REPORT_TRANSLATION = os.getenv("REPORT_TRANSLATION", "").strip() or None
# Translation only restates a finished report, so the cheapest model is enough.
# Haiku 5.5 thinks by default (effort medium); low effort keeps thinking short.
TRANSLATION_MODEL = "claude-haiku-5-5"
TRANSLATION_EFFORT = "low"
# A section whose first answer is rejected (left in English, another language) is
# asked again once, with a stricter prompt and a little more thinking.
TRANSLATION_RETRY_EFFORT = "medium"
# Also translate the per-lens reports (about six more calls per run).
TRANSLATE_LENS_REPORTS = os.getenv("TRANSLATE_LENS_REPORTS", "").strip().lower() in ("1", "true", "yes")

# Lens selection per idea: one small call (gate/lens_fit.py) skips an enabled lens whose
# applicability condition (Lens.applies_to) does not fit the idea. Lenses without
# a condition always run. Set LENS_SELECTION=on in .env; an experiment until the
# eval decides.
LENS_SELECTION = os.getenv("LENS_SELECTION", "").strip().lower() in ("1", "true", "yes", "on")

# Web search for the lenses whose conclusions rest on facts the model may
# remember wrongly (competitors in a market, laws, current prices): a real run
# named a competitor that had left the country years before. Set WEB_SEARCH=on
# in .env; an experiment until the eval decides. Each search costs
# WEB_SEARCH_PRICE on top of the tokens, and search results add input tokens.
WEB_SEARCH = os.getenv("WEB_SEARCH", "").strip().lower() in ("1", "true", "yes", "on")
WEB_SEARCH_LENSES = ("reality_auditor", "legal_counsel")
WEB_SEARCH_MAX_USES = 3
WEB_SEARCH_PRICE = 0.01  # USD per search (10 USD per 1,000)
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": WEB_SEARCH_MAX_USES}

# Domain lenses fit only some ideas, so they run only with LENS_SELECTION on and
# only where the lens fit check finds their condition holds. They follow
# ENABLED_LENSES in the order the synthesis reads them.
DOMAIN_LENSES = (
    "ai_tool_creator",
    "legal_counsel",
    "software_architect",
)
