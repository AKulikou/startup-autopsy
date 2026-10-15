"""
Example ideas offered above the input field (docs/web_ui.md, "Example ideas").

They are chosen to show the range of verdicts, so the page names only the idea,
never what it is meant to show. The texts are read from the showcase and eval
idea files rather than copied here; personal ideas (ideas/private/) are never
listed.
"""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Example:
    key: str
    title: str
    source: str | None = None  # idea file relative to the project root
    text: str | None = None    # or the text itself, for a one-liner

    def load(self) -> str:
        if self.text is not None:
            return self.text
        return (ROOT / self.source).read_text(encoding="utf-8").strip()


EXAMPLES: tuple[Example, ...] = (
    Example("salon_bookkeeping", "Bookkeeping for beauty salons in Vilnius",
            source="ideas/salon_bookkeeping.txt"),
    Example("invoice_reminders", "Overdue-invoice reminders for B2B",
            source="eval/pipeline/ideas/good_b2b_invoice_reminders.txt"),
    Example("ticket_resale", "Ticket resale in France, Belgium and Italy",
            source="eval/pipeline/ideas/pair_ticket_resale_fr_be_it.txt"),
    Example("api_monitor", "API limit monitor for developers", source="ideas/api_monitor.txt"),
    # Long enough for the local check (15 letters), vague enough that the input
    # check asks for details, like the gate eval's "An app for dog owners".
    Example("one_liner", "A one-line idea", text="An app for fitness fans"),
)


def examples_for_page() -> list[dict]:
    return [{"key": e.key, "title": e.title, "text": e.load()} for e in EXAMPLES]
