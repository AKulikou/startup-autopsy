"""
Prompt 2: The No-Code Stack Master
Фокус: Technical Feasibility & Time Constraints
"""

from .base import BaseEvaluator


class NoCodeStackMaster(BaseEvaluator):
    """
    Оценивает техническую осуществимость на no-code инструментах.
    7-дневный спринт — что реально запустится?
    """
    
    def get_evaluator_name(self) -> str:
        return "🔧 No-Code Stack Master"
    
    def get_system_prompt(self) -> str:
        return """You are a no-code architect building 7-day MVPs. Evaluate if this can be built with no-code tools.
Be specific about tools and honest about what's possible vs realistic in 7 days. Identify where no-code breaks."""
    
    def get_evaluation_prompt(self) -> str:
        return f"""Can this be built no-code in 7 days?

1. TECH STACK (specific tools only)
   - Frontend: Webflow? Bubble? Static HTML?
   - Backend: Make.com? Zapier? n8n?
   - Database: Airtable? Supabase? Google Sheets?
   - Payments: Stripe? Lemonsqueezy?
   - Why this combo? Better alternatives?

2. WHAT LAUNCHES DAY 7?
   - List 5 actual features someone would pay for
   - Not "AI features" or "advanced analytics" — reality
   - What 2-3 features can you skip?
   - What's day-7 vs month-2?

3. WHERE NO-CODE BREAKS
   - What requires custom code or manual work?
   - Biggest technical risk week 1?
   - When does no-code become a blocker?

4. REALISTIC DAY-7 DEMO
   - User flow: visits → [action] → [outcome]
   - Investor sees what?
   - What's obviously MVP/unpolished?

5. VERDICT
   - Launchable on day 7? Yes/No
   - If yes: with what caveats?
   - When does this need professional developers?

Be specific. Use tool names. Identify the biggest technical blocker.
"""
