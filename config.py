"""
Конфигурация для Startup Autopsy.
Параметры Claude API и настройки проекта.
"""

import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv(override=True)

# API ключ (из .env файла)
API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
ANTHROPIC_API_KEY = os.getenv(API_KEY_ENV_VAR)
API_KEY_PREFIX = "sk-ant-"

class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""

# Fail Fast проверка
if not ANTHROPIC_API_KEY or not ANTHROPIC_API_KEY.startswith(API_KEY_PREFIX):
    raise ConfigurationError(
        f"{API_KEY_ENV_VAR} is missing or invalid "
        f"(expected a key starting with '{API_KEY_PREFIX}').\n"
        "Copy .env.example to .env in the project root and set your API key there."
    )

# Модель Claude (какую версию использовать)
MODEL = "claude-sonnet-4-6"  # Последняя версия
# или для лучшего качества:
# MODEL = "claude-opus-4-8"

# Максимум токенов для первого запроса (анализ идеи)
MAX_TOKENS = 16000

# Lenses to run, by key (see evaluators/lenses.py for all eight).
# Evaluators run sequentially for now, so each extra lens adds ~1 minute.
ENABLED_LENSES = ("profitable_designer", "no_code_stack", "reality_auditor")

