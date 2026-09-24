"""
Access to business idea files in the ideas directory.
"""

from pathlib import Path


class FileManager:
    """Lists and reads idea files (*.txt) in the ideas directory."""

    def __init__(self, ideas_directory: str = "ideas"):
        self.ideas_dir = Path(ideas_directory)
        self.ideas_dir.mkdir(parents=True, exist_ok=True)

    def list_ideas(self) -> list[str]:
        """Return idea names (file names without the .txt extension), sorted."""
        return [f.stem for f in sorted(self.ideas_dir.glob("*.txt"))]

    def get_full_path(self) -> Path:
        """Return the absolute path of the ideas directory."""
        return self.ideas_dir.resolve()

    def read_idea(self, idea_name: str) -> str:
        """
        Read the text of an idea.

        Raises:
            FileNotFoundError: If the idea file does not exist
            OSError: If the file cannot be read
        """
        filepath = self.ideas_dir / f"{idea_name}.txt"
        if not filepath.is_file():
            raise FileNotFoundError(f"Idea file not found: {filepath.resolve()}")
        return filepath.read_text(encoding="utf-8")
