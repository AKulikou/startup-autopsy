"""
Startup Autopsy — Main Entry Point (Phase 2)

Запускает анализ бизнес-идей через 3 оценщика.
Просто точка входа — вся логика в core/ классах.

Структура проекта:
- logs/       ← Логи приложения
- results/    ← Markdown отчёты анализа
- ideas/      ← Текстовые файлы с бизнес-идеями
- evaluators/ ← Модули оценщиков
- core/       ← Ядро приложения (логика)
"""

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

from core.idea_processor import IdeaProcessor
from core.analysis_runner import AnalysisRunner

# Создаём папку logs/ если её нет
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Кастомный фильтр для отсеивания HTTP логов
class HTTPLogFilter(logging.Filter):
    """Отсеивает HTTP логи из httpx/anthropic."""
    def filter(self, record):
        # Отбрасываем записи содержащие HTTP Request
        if "HTTP Request:" in record.getMessage():
            return False
        return True

# Настройка логирования
log_filename = LOGS_DIR / f"startup_autopsy_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

file_handler = RotatingFileHandler(
    log_filename,
    maxBytes=5*1024*1024,
    backupCount=10,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))
console_handler.addFilter(HTTPLogFilter())  # ← ДОБАВЛЯЕМ ФИЛЬТР

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Отключаем лишние логи
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('anthropic').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('anthropic._http_client').setLevel(logging.WARNING)

def select_idea(processor: IdeaProcessor) -> str:
    """Интерактивный выбор идеи из доступных."""
    ideas, path = processor.get_available_ideas()
    
    logger.info("\n" + "="*70)
    logger.info("STARTUP AUTOPSY — Business Idea Validator (Phase 2)")
    logger.info("="*70)
    
    if not ideas:
        logger.info("\n❌ Идей не найдено.")
        return None
    
    logger.info("\n📋 Доступные идеи:")
    for i, idea in enumerate(ideas, 1):
        logger.info(f"   {i}. {idea}")
    
    logger.info(f"\n📁 Путь: {path}")
    logger.info("\n" + "-"*70)
    logger.info("Номер (1, 2...) или имя файла (или Enter для выхода):\n")
    
    choice = input("➜ Выберите: ").strip()
    
    if not choice:
        return None
    
    if choice.isdigit():
        idx = int(choice) - 1
        return ideas[idx] if 0 <= idx < len(ideas) else None
    
    return choice if choice in ideas else None


def main():
    """Главная функция — запуск приложения."""
    logger.info(f"📝 Логи записываются в: {LOGS_DIR.absolute()}")
    
    processor = IdeaProcessor()
    idea_name = select_idea(processor)
    
    if idea_name:
        runner = AnalysisRunner(processor)
        runner.run(idea_name)
    else:
        logger.info("⏹ Выход.")


if __name__ == "__main__":
    main()