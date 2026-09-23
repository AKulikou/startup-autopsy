"""
Prompt 8: The Reality Auditor
Фокус: Critical Assessment & Decision Framework
"""

from .base import BaseEvaluator


class RealityAuditor(BaseEvaluator):
    """
    Жёсткий скептический анализ.
    Найти то, что убьёт проект в первые 30 дней.
    """
    
    def get_evaluator_name(self) -> str:
        return "🎯 Reality Auditor"
    
    def get_system_prompt(self) -> str:
        return """You are an angel investor who's seen 500+ startups. Question every assumption.
Identify what assumptions are shaky and what kills the project. Be brutally realistic, not cynical."""
    
    def get_evaluation_prompt(self) -> str:
        return f"""Reality check on this business idea:

{self.business_idea}

1. CORE ASSUMPTION
   - What MUST be true for this to work?
   - How do you validate it in week 1?
   - What if you're wrong?

2. CUSTOMER ACQUISITION
   - "We'll use X to find customers" → HOW EXACTLY?
   - Day 30 reality: __ paying customers (realistic, not optimistic)
   - Cost per customer acquisition?

3. YOUR BLINDSPOTS
   - What are you not seeing?
   - Who already does this?
   - What would a real customer tell you?

4. THE 30-DAY CLIFF
   - What kills this in first month? (Churn? No customers? Burnout?)
   - When do you run out of money?
   - What's the one biggest risk?

5. GO/NO-GO DECISION
   - Is this "bad idea" or "needs validation first"?
   - What ONE thing would you need to prove in 30 days?
   - What makes you pull the plug?

Be ruthless. Show your math. Identify the single killer risk.

**AT THE END - REQUIRED:**
SUMMARY: [One sentence verdict]
VERDICT_RECOMMENDATION: [VIABLE / VIABLE_IF / NEEDS_VALIDATION / RISKY / NOT_VIABLE]
CONFIDENCE_LEVEL: [0-100]
"""
