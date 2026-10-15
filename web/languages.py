"""
Languages offered for a translated copy of the report (docs/web_ui.md, "Translation").

The page shows each language by its own name; the English name goes to the
translator (prompt and file name). The default comes first, the rest follow
alphabetically by their own names. English is not offered: the original is
English.
"""

# (English name for the translator, the language's own name for the page)
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("Lithuanian", "Lietuvių"),
    ("German", "Deutsch"),
    ("Estonian", "Eesti"),
    ("Spanish", "Español"),
    ("French", "Français"),
    ("Italian", "Italiano"),
    ("Latvian", "Latviešu"),
    ("Polish", "Polski"),
    ("Russian", "Русский"),
    ("Ukrainian", "Українська"),
)

NATIVE_NAMES = dict(LANGUAGES)


def languages_for_page() -> list[dict]:
    return [{"name": name, "label": label} for name, label in LANGUAGES]
