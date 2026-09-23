"""
Агрегатор результатов анализа.
Объединяет результаты от 3+ оценщиков в один executive summary.
"""

from typing import List, Dict
from pathlib import Path
from collections import Counter


class ReportAggregator:
    """Объединяет результаты от нескольких оценщиков."""
    
    def __init__(self, results_directory: str = "results"):
        self.results_dir = Path(results_directory)
    
    def aggregate(self, results: List[Dict]) -> str:
        """
        Генерирует объединённый отчёт из результатов нескольких оценщиков.
        
        Args:
            results: Список результатов от evaluators
        
        Returns:
            str: Markdown-отчёт
        """
        # Фильтруем успешные результаты
        successful = [r for r in results if r.get("status") == "success"]
        
        if not successful:
            return self._error_report(results)
        
        # Строим компоненты отчёта
        header = self._build_header()
        summaries = self._build_summaries(successful)
        metrics_table = self._build_metrics_table(successful)
        consensus = self._find_consensus(successful)
        differences = self._find_differences(successful)
        next_steps = self._generate_next_steps(successful)
        
        # Собираем всё вместе
        markdown = f"""{header}

## 📝 EVALUATOR SUMMARIES (Quick Overview)

{summaries}

## 📈 EVALUATORS COMPARISON

{metrics_table}

## 🤝 WHERE THEY AGREE

{consensus}

## 🤔 WHERE THEY DISAGREE

{differences}

## 🎯 RECOMMENDED NEXT STEPS

{next_steps}

---
*Report aggregated from {len(successful)} evaluators*
"""
        return markdown
    
    def _build_header(self) -> str:
        """Заголовок отчёта."""
        return """═══════════════════════════════════════════════════════════════
STARTUP AUTOPSY — SYNTHESIS REPORT
═══════════════════════════════════════════════════════════════"""
    
    def _build_summaries(self, results: List[Dict]) -> str:
        """
        Построить быстрый обзор из summary каждого оценщика.
        Дает quick scan всех трех перспектив.
        """
        summaries = []
        
        for result in results:
            evaluator = result.get("evaluator_display", "Unknown")
            summary = result.get("summary", "No summary available")
            verdict = result.get("verdict", "")
            confidence = result.get("confidence", "")
            
            # Обрезаем summary если слишком длинный (>200 символов)
            if len(summary) > 200:
                summary = summary[:197] + "..."
            
            summaries.append(
                f"**{evaluator}** ({verdict}, {confidence} confidence)\n{summary}\n"
            )
        
        return "\n".join(summaries)
    
    def _build_metrics_table(self, results: List[Dict]) -> str:
        """Таблица сравнения оценщиков."""
        table = "| Evaluator | Verdict | Confidence | Tokens |\n"
        table += "|-----------|---------|------------|--------|\n"
        
        for result in results:
            evaluator = result.get("evaluator_display", "Unknown")
            verdict = result.get("verdict", "N/A")
            confidence = result.get("confidence", "")
            tokens = result.get("tokens_used", 0)
            table += f"| {evaluator} | {verdict} | {confidence} | {tokens} |\n"
        
        return table
    
    def _find_consensus(self, results: List[Dict]) -> str:
        """
        Анализирует что оценщики держат в согласии.
        Смотрит на summaries и общие темы в анализах.
        """
        if len(results) < 2:
            return "Only one evaluator — no consensus to assess."
        
        # Собираем ключевые слова/риски из summaries
        consensus_points = []
        
        # Анализируем вердикты
        verdicts = [r.get("verdict", "") for r in results]
        verdict_counter = Counter(verdicts)
        
        # Если 2+ оценщика имеют одинаковый вердикт
        most_common_verdict = verdict_counter.most_common(1)
        if most_common_verdict and most_common_verdict[0][1] >= 2:
            verdict, count = most_common_verdict[0]
            if verdict != "UNCERTAIN":
                consensus_points.append(
                    f"**Verdict alignment:** {count}/{len(results)} evaluators lean toward {verdict}"
                )
        
        # Анализируем анализы на общие риски
        all_text = " ".join([r.get("analysis", "") for r in results]).lower()
        
        # Ищем повторяющиеся риски/темы
        risk_keywords = {
            "stripe": "Payment processor risk flagged",
            "chargeback": "High chargeback risk consensus",
            "pact app": "Pact App failure as precedent noted",
            "legal": "Legal/regulatory concerns identified",
            "gym partnership": "Gym partnership dependency mentioned",
            "user churn": "High churn risk consensus",
            "apple health": "Apple Health integration difficulty noted",
            "fraud": "User fraud/cheating risk identified",
        }
        
        for keyword, risk_desc in risk_keywords.items():
            count = sum(1 for r in results if keyword in r.get("analysis", "").lower())
            if count >= 2:
                consensus_points.append(f"**{risk_desc}** (mentioned by {count} evaluators)")
        
        # Ищем общие рекомендации
        if any("validation" in r.get("analysis", "").lower() for r in results):
            consensus_points.append("**Validation-first approach recommended** across evaluators")
        
        if not consensus_points:
            consensus_points = [
                "Core business model viability questioned by multiple evaluators",
                "Payment/legal infrastructure needs careful review"
            ]
        
        return "\n".join([f"- {point}" for point in consensus_points])
    
    def _find_differences(self, results: List[Dict]) -> str:
        """
        Находит расхождения между оценщиками и объясняет почему.
        """
        if len(results) < 2:
            return "Only one evaluator — no differences to assess."
        
        verdicts = [(r.get("evaluator_display", "Unknown"), r.get("verdict", ""), r.get("confidence", 0)) for r in results]
        
        # Проверяем разброс вердиктов
        verdict_set = set(v[1] for v in verdicts)
        
        if len(verdict_set) == 1:
            return f"All evaluators agree on verdict: **{verdicts[0][1]}**"
        
        # Есть разброс — анализируем почему
        differences = []
        
        # Сортируем по вердикту
        differences.append("**Verdict split across evaluators:**\n")
        for evaluator, verdict, confidence in sorted(verdicts, key=lambda x: x[2], reverse=True):
            differences.append(f"- {evaluator}: **{verdict}** ({confidence})")
        
        differences.append("\n**Why they disagree:**")
        
        # Ищем причины разногласий
        no_code = next((r for r in results if "No-Code" in r.get("evaluator_display", "")), None)
        reality = next((r for r in results if "Reality" in r.get("evaluator_display", "")), None)
        profitable = next((r for r in results if "Profitable" in r.get("evaluator_display", "")), None)
        
        if no_code and reality:
            no_code_verdict = no_code.get("verdict", "")
            reality_verdict = reality.get("verdict", "")
            
            if "VIABLE" in no_code_verdict and "NOT_VIABLE" in reality_verdict:
                differences.append(
                    "- **No-Code** focuses on technical feasibility (MVP CAN be built), "
                    "while **Reality** focuses on market viability (MVP WON'T find customers)"
                )
            elif no_code_verdict != reality_verdict:
                differences.append(
                    "- **No-Code** evaluates buildability, **Reality** evaluates business sustainability — "
                    "different frameworks lead to different verdicts"
                )
        
        if profitable:
            prof_verdict = profitable.get("verdict", "")
            if "RISKY" in prof_verdict:
                differences.append(
                    f"- **Profitable Designer** sees unit economics problem: CAC > LTV by month 3"
                )
        
        return "\n".join(differences)
    
    def _generate_next_steps(self, results: List[Dict]) -> str:
        """
        Генерирует конкретные рекомендации на основе вердиктов и анализов.
        """
        steps = []
        verdicts = [r.get("verdict", "") for r in results]
        
        # Базовый шаг
        steps.append("**Before building:**")
        
        # Анализируем что нужно валидировать
        has_legal_risk = any("legal" in r.get("analysis", "").lower() for r in results)
        has_stripe_risk = any("stripe" in r.get("analysis", "").lower() for r in results)
        has_market_risk = any("NOT_VIABLE" in r.get("verdict", "") or "RISKY" in r.get("verdict", "") for r in results)
        
        if has_stripe_risk:
            steps.append(
                "1. **Get written approval from Stripe** that they'll support automatic penalty charges. "
                "If declined → idea is dead."
            )
        
        if has_legal_risk:
            steps.append(
                "2. **Consult fintech/payment law attorney** on automatic charges tied to body weight metrics. "
                "Understand HIPAA/GDPR/ADA exposure."
            )
        
        if has_market_risk:
            steps.append(
                "3. **Research why Pact App failed** (2008-2020). Understand if structural or executional problem."
            )
        
        # Если есть разброс вердиктов
        if len(set(verdicts)) > 1:
            steps.append(
                "4. **De-risk by testing ONE assumption** before building:\n"
                "   - Post survey: 'Would you let an app auto-charge your card if you gain weight?'\n"
                "   - Get 100+ responses with 15%+ saying 'yes, I'd pay today'\n"
                "   - If below 15% → core mechanic is rejected by market"
            )
        
        # Специфичные рекомендации
        if "VIABLE_IF" in verdicts:
            steps.append(
                "5. **If proceeding (conditional):**\n"
                "   - Start with positive-only incentives (no penalties)\n"
                "   - Manual weight logging MVP (no Apple Health integration)\n"
                "   - Get 20-30 beta users who explicitly understand penalty mechanics\n"
                "   - Measure: retention at day 30, chargeback rate, Net Promoter Score"
            )
        
        if all("NOT_VIABLE" in v for v in verdicts):
            steps.append(
                "**OR: Kill the idea.** Multiple evaluators flagged structural problems:\n"
                "   - User fraud is unsolvable without hardware integration\n"
                "   - Legal exposure is real regardless of market fit\n"
                "   - Pact App precedent shows market doesn't scale\n"
                "   - Consider pivoting to positive-only model (HealthyWage)"
            )
        
        if not steps or len(steps) == 1:
            # Fallback если ничего не подошло
            steps.append("1. Review full reports in results/ directory")
            steps.append("2. Focus on items where evaluators disagree most")
            steps.append("3. Validate top 1-2 assumptions with real users")
            steps.append("4. Build MVP and measure against predictions")
        
        return "\n\n".join(steps)
    
    def _error_report(self, results: List[Dict]) -> str:
        """Отчёт об ошибках."""
        errors = [r for r in results if r.get("status") == "error"]
        error_text = "\n".join([f"• {e.get('error', 'Unknown')}" for e in errors])
        return f"❌ Analysis failed:\n\n{error_text}"
