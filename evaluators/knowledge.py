"""
Domain knowledge for lenses, stored as Agent Skills in lens_knowledge/<name>/:
SKILL.md (frontmatter + instructions) and optional references/*.md. The same
folder works as a standalone skill in Claude Code or claude.ai; the pipeline
reads it and adds it to the lens's system prompt.
"""

from functools import lru_cache
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "lens_knowledge"


def strip_frontmatter(text: str) -> str:
    """Drop the YAML frontmatter: name and description matter to skill loaders, not to the lens."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end == -1:
            raise ValueError("SKILL.md frontmatter is not closed with '---'")
        text = text[end + len("\n---"):]
    return text.strip()


@lru_cache
def load_knowledge(name: str) -> str:
    """
    Return the skill's instructions followed by all its reference files.

    Raises FileNotFoundError if the skill folder or its SKILL.md is missing, so a
    typo in a lens definition fails loudly instead of running the lens without
    its knowledge.
    """
    folder = KNOWLEDGE_DIR / name
    parts = [strip_frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))]
    for reference in sorted((folder / "references").glob("*.md")):
        parts.append(f"## Reference: {reference.name}\n\n{reference.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)
