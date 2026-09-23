"""
Запись результатов анализа в файл.
Структурированный формат (Markdown).
"""

import re
from pathlib import Path
from datetime import datetime


class ResultWriter:
    """Запись результатов анализа в Markdown файл."""
    
    def __init__(self, results_directory: str = "results"):
        """
        Args:
            results_directory (str): Папка для сохранения результатов
        """
        self.results_dir = Path(results_directory)
        self._create_directory()
    
    def _create_directory(self):
        """Создаёт папку для результатов если её нет."""
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def _clean_evaluator_name(self, evaluator_name: str) -> str:
        """
        Очищает имя оценщика от emoji и форматирует для имени файла.
        
        Примеры:
            "💰 Profitable App Designer" → "profitable_app_designer"
            "🔧 No-Code Stack Master" → "no_code_stack_master"
            "🎯 Reality Auditor" → "reality_auditor"
        
        Args:
            evaluator_name (str): Исходное имя оценщика
        
        Returns:
            str: Очищенное имя для файла
        """
        # Удаляем всё что не буквы, цифры и пробелы
        # (убирает emoji и спецсимволы)
        cleaned = re.sub(r'[^\w\s]', '', evaluator_name)
        
        # Приводим к lowercase и заменяем пробелы на underscore
        cleaned = cleaned.lower().strip().replace(" ", "_")
        
        # Убираем множественные подряду идущие underscore
        cleaned = re.sub(r'_+', '_', cleaned)
        
        return cleaned
    
    def get_filename(self, idea_name: str, evaluator_name: str = None) -> str:
        """
        Генерирует имя файла результата с включением имени оценщика.
        Формат: IDEA_NAME_EVALUATOR_YYYY-MM-DD_HH-MM-SS.md
        
        Примеры:
            - "api_monitor_profitable_app_designer_2026-09-22_15-22-50.md"
            - "fitness_tracker_reality_auditor_2026-09-22_14-30-00.md"
        
        Args:
            idea_name (str): Имя идеи
            evaluator_name (str): Имя оценщика с emoji (опционально)
        
        Returns:
            str: Имя файла без emoji
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        if evaluator_name:
            # Очищаем имя оценщика от emoji
            clean_name = self._clean_evaluator_name(evaluator_name)
            return f"{idea_name}_{clean_name}_{timestamp}.md"
        
        return f"{idea_name}_{timestamp}.md"
    
    def save_result(self, idea_name: str, analysis: str, tokens_used: int, evaluator_name: str = None) -> Path:
        """
        Сохраняет результат анализа в Markdown файл.
        
        Args:
            idea_name (str): Имя идеи
            analysis (str): Текст анализа
            tokens_used (int): Количество использованных токенов
            evaluator_name (str): Имя оценщика (может содержать emoji)
        
        Returns:
            Path: Путь к сохранённому файлу
        """
        filename = self.get_filename(idea_name, evaluator_name)
        filepath = self.results_dir / filename
        
        content = self._format_markdown(idea_name, analysis, tokens_used)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return filepath
    
    def _format_markdown(self, idea_name: str, analysis: str, tokens_used: int) -> str:
        """
        Форматирует анализ в Markdown.
        
        Args:
            idea_name (str): Имя идеи
            analysis (str): Текст анализа
            tokens_used (int): Токены
        
        Returns:
            str: Форматированный Markdown
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        markdown = f"""# Startup Autopsy — Анализ идеи

**Идея:** {idea_name}  
**Дата анализа:** {timestamp}  
**Токенов использовано:** {tokens_used}

---

## Результат анализа

{analysis}

---

*Создано Startup Autopsy MCP Server*
"""
        return markdown
    
    def get_results_directory(self) -> Path:
        """
        Возвращает полный путь к директории результатов.
        
        Returns:
            Path: Абсолютный путь
        """
        return self.results_dir.resolve()