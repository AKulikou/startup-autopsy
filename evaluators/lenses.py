"""
Analytical lenses used to evaluate a business idea.

Each lens is one independent perspective (see docs/prompt_framework.md).
A lens defines only *what to look at*; the evaluation standards shared by all
lenses live in ANALYSIS_STANDARDS, and the output format is defined by the
EvaluatorResult schema.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Lens:
    key: str             # stable identifier, used in config and file names
    name: str            # display name for reports
    role: str            # who the model acts as
    focus: str           # the single question this lens answers
    questions: tuple[str, ...]


ANALYSIS_STANDARDS = """\
You are one of several independent evaluators of a business idea. Each evaluator
looks through a different lens; stay strictly within yours and do not cover angles
that belong to other lenses. If you notice a serious problem outside your lens, record
it briefly as a red flag instead of analysing it.

Standards for your analysis:
- Be brutally honest. No marketing language, no encouragement for its own sake.
  "Interesting concept" is not the same as "viable business".
- Every number needs context: the assumption behind it and what would change it.
  Show the math.
- Be specific: name concrete customer segments, tools, competitors and channels
  ("EU day traders with €5k+ portfolios", not "active traders").
- Separate what is possible from what is probable.
- Focus on risks that can kill the project, not on minor improvements.
- Distinguish "the idea is flawed" from "the idea is not yet validated".
- If the idea description lacks information you need, say what is missing and
  state the assumption you made instead of it.
- Write in English, whatever the language of the idea description.
- When quoting anything, including the idea description, use single quotes ('like
  this'), not double quotes: your answer is JSON, and an unescaped double quote
  ends the field it is in.
- In the text, describe the verdict in plain words; do not quote verdict codes
  such as NOT_VIABLE or VIABLE_IF.
"""


LENSES: tuple[Lens, ...] = (
    Lens(
        key="profitable_designer",
        name="Profitable App Designer",
        role="a SaaS product designer who has launched several profitable subscription products",
        focus="Would people pay for this every month, and how much revenue is realistic?",
        questions=(
            "What specific, recurring problem would a user pay for monthly? Who exactly pays "
            "(role, industry, income level)?",
            "What price point is realistic, and why that price rather than half or double?",
            "Which parts of the service can run on automation, and what daily manual work remains?",
            "What is a realistic revenue range at month 3 and month 6? Show users × price, "
            "and state the assumptions behind each number.",
        ),
    ),
    Lens(
        key="no_code_stack",
        name="No-Code Stack Master",
        role="a no-code architect who ships working MVPs in 7 days",
        focus="Can a sellable MVP be built with no-code tools in 7 days?",
        questions=(
            "Which specific tool would you use for each component (frontend, backend logic, "
            "database, payments, integrations), and why is this combination better than "
            "the alternatives for this idea?",
            "What is the day-by-day plan from day 1 to launch?",
            "Which features ship on day 7 that someone would actually pay for, and what is "
            "deliberately postponed?",
            "Where does no-code break: what needs custom code or manual work, and at what "
            "point would professional developers be required?",
        ),
    ),
    Lens(
        key="ai_tool_creator",
        name="AI Tool Creator",
        role="a founder of AI-powered subscription tools",
        focus="Is the AI capability genuinely useful and differentiated, and can it find paying customers?",
        questions=(
            "What concrete AI capability makes this useful rather than a curiosity? Could a "
            "user get the same result from a general-purpose chatbot?",
            "What interface and positioning would make it look credible to paying customers?",
            "What pricing model fits, and why that price point given the underlying AI costs?",
            "What is the concrete plan to acquire the first 10 paying customers? Name real "
            "channels, communities or people, not 'do marketing'.",
        ),
    ),
    Lens(
        key="saas_revenue_builder",
        name="SaaS Revenue Builder",
        role="a SaaS growth lead who has taken products from MVP to sustainable revenue",
        focus="Is there a realistic path from MVP to sustainable recurring revenue?",
        questions=(
            "What pricing tiers make sense, and what conversion rate between them is "
            "realistic? Explain the reasoning.",
            "Which features would reduce churn after the first month?",
            "Which low-cost acquisition strategy fits this product and audience?",
            "Project revenue at months 3, 6 and 12 as two clearly separated scenarios: "
            "conservative and optimistic, with the assumptions that differ between them.",
        ),
    ),
    Lens(
        key="viral_designer",
        name="Viral Product Designer",
        role="a product designer specialising in organic growth and network effects",
        focus="Can this grow through users themselves, without paid acquisition?",
        questions=(
            "What is the core value proposition in one sentence?",
            "At which moment in the user journey would sharing feel natural, and what "
            "would motivate it?",
            "Is there a network effect that makes the product more valuable as more people "
            "use it? If not, say so plainly.",
            "What conditions must actually hold for organic growth to happen? Separate "
            "required conditions from hopeful assumptions.",
        ),
    ),
    Lens(
        key="launch_expert",
        name="Launch Expert",
        role="a launch strategist who has run dozens of product launches",
        focus="What can realistically be achieved in the first week after launch?",
        questions=(
            "What pre-launch waitlist strategy fits this idea, and where would the waitlist "
            "come from?",
            "What should the launch-day sequence and timing look like?",
            "What incentive would convince early adopters to pay in the first week?",
            "What first-week results are realistic given the audience the founder actually "
            "has? If the audience size is unknown, state the assumption and show how the "
            "numbers scale with it.",
        ),
    ),
    Lens(
        key="churn_eliminator",
        name="Churn Eliminator",
        role="a retention specialist focused on subscription unit economics",
        focus="Will users stay, and what keeps them from cancelling?",
        questions=(
            "What onboarding would demonstrate real value in the first session?",
            "Which feature could become part of a user's daily or weekly routine?",
            "Which behavioural signals would predict a cancellation before it happens?",
            "What churn reduction is realistic within 30 days, and under which conditions "
            "would these tactics fail?",
        ),
    ),
    Lens(
        key="reality_auditor",
        name="Reality Auditor",
        role="an angel investor who has reviewed more than 500 startups",
        focus=(
            "Before committing serious time: is this worth pursuing at all? This lens covers "
            "the whole idea: legal, technical and market blockers are all within it."
        ),
        questions=(
            "Which parts of the idea depend on unrealistic assumptions?",
            "Who already solves this problem, and why would a customer switch?",
            "What is the true timeline to a first working version, not the ideal case?",
            "What evidence in the first weeks would justify continuing, and what would "
            "justify stopping?",
        ),
    ),
)


def select_lenses(keys: tuple[str, ...]) -> tuple[Lens, ...]:
    """
    Return the lenses with the given keys, in the given order.

    Raises ValueError on unknown keys, so a typo in configuration fails loudly
    instead of silently skipping a lens.
    """
    by_key = {lens.key: lens for lens in LENSES}
    unknown = [key for key in keys if key not in by_key]
    if unknown:
        raise ValueError(
            f"Unknown lens key(s): {', '.join(unknown)}. "
            f"Available: {', '.join(by_key)}"
        )
    return tuple(by_key[key] for key in keys)
