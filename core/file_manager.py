"""
Управление файлами идей.
Чтение, листинг, валидация.
"""

from pathlib import Path
from typing import Optional, List


class FileManager:
    """Управление файлами идей в папке 'ideas'."""
    
    def __init__(self, ideas_directory: str = "ideas"):
        """
        Args:
            ideas_directory (str): Путь к папке с идеями
        """
        self.ideas_dir = Path(ideas_directory)
        self._validate_directory()
    
    def _validate_directory(self):
        """Проверяет наличие папки с идеями."""
        if not self.ideas_dir.exists():
            self.ideas_dir.mkdir(parents=True, exist_ok=True)
    
    def list_ideas(self) -> List[str]:
        """
        Возвращает список всех доступных идей.
        
        Returns:
            List[str]: Список имён файлов без расширения
        """
        idea_files = sorted(self.ideas_dir.glob("*.txt"))
        return [f.stem for f in idea_files]
    
    def get_full_path(self) -> Path:
        """
        Возвращает полный путь к папке идей.
        
        Returns:
            Path: Абсолютный путь
        """
        return self.ideas_dir.resolve()
    
    def read_idea(self, filename: str) -> Optional[str]:
        """
        Читает содержимое файла с идеей.
        
        Args:
            filename (str): Имя файла (без .txt)
        
        Returns:
            Optional[str]: Содержимое файла или None
        """
        filepath = self.ideas_dir / f"{filename}.txt"
        full_path = filepath.resolve()
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                return content
        except FileNotFoundError:
            raise FileNotFoundError(f"Файл не найден: {full_path}")
        except Exception as e:
            raise Exception(f"Ошибка при чтении файла: {e}")
    
    def file_exists(self, filename: str) -> bool:
        """
        Проверяет наличие файла.
        
        Args:
            filename (str): Имя файла (без .txt)
        
        Returns:
            bool: True если файл существует
        """
        filepath = self.ideas_dir / f"{filename}.txt"
        return filepath.exists()