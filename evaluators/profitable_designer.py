"""
Prompt 1: The Profitable App Designer
Фокус: Product Design & Revenue Model
"""

from .base import BaseEvaluator


class ProfitableAppDesigner(BaseEvaluator):
    """
    Оценивает жизнеспособность ПО с упором на рекуррентный доход
    и минимальные операционные расходы.
    """
    
    def get_evaluator_name(self) -> str:
        return "💰 Profitable App Designer"
    
    def get_system_prompt(self) -> str:
        return """You are a SaaS product designer evaluating business ideas through revenue viability.
Be brutally honest. Separate enthusiasm from reality. Show numbers, not marketing."""
    
    def get_evaluation_prompt(self) -> str:
        return f"""Evaluate this for recurring revenue viability:

{self.business_idea}

1. WILLINGNESS TO PAY
   - What specific problem would users pay MONTHLY for?
   - Who pays? (Role, industry, income level — be specific)
   - Price point and why? Example: $9/mo vs $99/mo?

2. NO-CODE BUILD FEASIBILITY
   - What tools? (Airtable, Make, Zapier, Bubble?)
   - What can launch week 1?
   - What manual work remains?

3. REALISTIC REVENUE NUMBERS (show assumptions)
   - Month 3: __ users at $__/month = $__ revenue. Why this number?
   - Month 6: Growth rate % (organic/paid/partnership)
   - Cost to acquire one paying customer?

4. BIGGEST RISKS
   - What MUST be true for this to work?
   - What kills it in first 30 days?
   - What if users don't pay?

5. WHAT NEEDS VALIDATION FIRST?
   - One thing you'd prove before building
   - How would you test it?

**AT THE END - REQUIRED:**
SUMMARY: [One sentence verdict]
VERDICT_RECOMMENDATION: [VIABLE / VIABLE_IF / NEEDS_VALIDATION / RISKY / NOT_VIABLE]
CONFIDENCE_LEVEL: [0-100]
"""
