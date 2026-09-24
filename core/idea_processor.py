"""
Главный процессор идей.
Координирует: выбор → чтение → анализ → сохранение
"""

from pathlib import Path
from typing import Optional
from .file_manager import FileManager
from .result_writer import ResultWriter


class IdeaProcessor:
    """Главный координатор процесса анализа идей."""
    
    def __init__(self, ideas_dir: str = "ideas", results_dir: str = "results"):
        """
        Args:
            ideas_dir (str): Папка с идеями
            results_dir (str): Папка для результатов
        """
        self.file_manager = FileManager(ideas_dir)
        self.result_writer = ResultWriter(results_dir)
    
    def get_available_ideas(self) -> tuple[list, Path]:
        """
        Возвращает список доступных идей и путь поиска.
        
        Returns:
            tuple: (список идей, полный путь)
        """
        ideas = self.file_manager.list_ideas()
        path = self.file_manager.get_full_path()
        return ideas, path
    
    def load_idea(self, idea_name: str) -> Optional[str]:
        """
        Загружает идею по имени.
        
        Args:
            idea_name (str): Имя идеи
        
        Returns:
            Optional[str]: Содержимое идеи или None
        """
        try:
            return self.file_manager.read_idea(idea_name)
        except (FileNotFoundError, Exception) as e:
            print(f"❌ Ошибка: {e}")
            return None
    
    def save_analysis(self, idea_name: str, result: dict) -> Path:
        """
        Save one evaluator's result.

        Args:
            idea_name (str): Idea name
            result (dict): Successful result dict from Evaluator.evaluate()

        Returns:
            Path: Path to the result file
        """
        return self.result_writer.save_result(idea_name, result)
    
    def get_results_path(self) -> Path:
        """Возвращает путь к папке результатов."""
        return self.result_writer.get_results_directory()

    @property
    def results_dir(self):
        """Возвращает директорию результатов."""
        return self.result_writer.results_dir