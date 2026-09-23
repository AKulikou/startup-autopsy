"""
Базовый класс для всех оценщиков.
Каждый оценщик наследуется от этого класса и переопределяет методы.
"""

import re
from abc import ABC, abstractmethod
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, MODEL, MAX_TOKENS, VERDICT_COMPLETION_TOKENS


class BaseEvaluator(ABC):
    """
    Абстрактный базовый класс для всех оценщиков бизнес-идей.
    
    Каждый подкласс должен:
    1. Переопределить get_system_prompt() — уникальный стиль оценки
    2. Переопределить get_evaluation_prompt() — уникальные вопросы анализа
    3. Переопределить get_evaluator_name() — красивое имя для отчётов
    """
    
    def __init__(self, business_idea: str):
        """
        Инициализация оценщика.
        
        Args:
            business_idea (str): Описание бизнес-идеи для анализа
        """
        self.business_idea = business_idea
        self.last_analysis = None
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = MODEL
        self.max_tokens = MAX_TOKENS
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Возвращает системный промпт для этого оценщика.
        Переопределяется каждым подклассом.
        
        Returns:
            str: Инструкции для Claude (роль, стиль, требования)
        """
        pass
    
    @abstractmethod
    def get_evaluation_prompt(self) -> str:
        """
        Возвращает пользовательский промпт (вопросы для анализа).
        Переопределяется каждым подклассом.
        
        Returns:
            str: Вопросы, которые нужно задать о бизнес-идее
        """
        pass
    
    @abstractmethod
    def get_evaluator_name(self) -> str:
        """
        Возвращает красивое имя оценщика для отчётов.
        Переопределяется в подклассах.
        
        Returns:
            str: Человекочитаемое имя (например, "Profitable App Designer")
        """
        pass
    
    def _has_verdict(self, text: str) -> bool:
        """
        Проверяет, содержит ли текст вердикт и уверенность.
        
        Args:
            text (str): Текст анализа
        
        Returns:
            bool: True если найдены оба VERDICT_RECOMMENDATION и CONFIDENCE_LEVEL
        """
        has_verdict = "VERDICT_RECOMMENDATION:" in text
        has_confidence = "CONFIDENCE_LEVEL:" in text
        return has_verdict and has_confidence
    
    def evaluate(self) -> dict:
        """
        Основной метод анализа. Делает второй запрос если вердикт обрезан.
        
        Returns:
            dict: Результат анализа с вердиктом, уверенностью и токенами
        """
        try:
            # Инициализируем раздельно для каждого запроса
            req1_input_tokens = 0
            req1_output_tokens = 0
            req2_input_tokens = 0
            req2_output_tokens = 0
            verdict_request_used = False

            # ===== ПЕРВЫЙ ЗАПРОС =====
            response1 = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.get_system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": f"{self.get_evaluation_prompt()}\n\nBusiness Idea:\n{self.business_idea}"
                    }
                ]
            )

            analysis = response1.content[0].text
            req1_input_tokens = response1.usage.input_tokens
            req1_output_tokens = response1.usage.output_tokens
            self.last_analysis = analysis

            # ===== ВТОРОЙ ЗАПРОС (если нужен) =====
            if not self._has_verdict(analysis):
                response2 = self.client.messages.create(
                    model=self.model,
                    max_tokens=VERDICT_COMPLETION_TOKENS,
                    system="You are a business analyst. Complete the analysis by adding VERDICT_RECOMMENDATION and CONFIDENCE_LEVEL if missing. Keep the analysis unchanged, just append the missing fields.",
                    messages=[
                        {
                            "role": "user",
                            "content": f"""Complete this analysis by adding at the very end:

VERDICT_RECOMMENDATION: [VIABLE / VIABLE_IF / NEEDS_VALIDATION / RISKY / NOT_VIABLE]
CONFIDENCE_LEVEL: [0-100]

Original analysis:
{analysis}"""
                        }
                    ]
                )
                
                verdict_text = response2.content[0].text
                analysis = analysis + "\n\n" + verdict_text
                verdict_request_used = True
                
                req2_input_tokens = response2.usage.input_tokens
                req2_output_tokens = response2.usage.output_tokens
                
                self.last_analysis = analysis

            # ===== ВЫЧИСЛЯЕМ ОБЩИЕ ТОКЕНЫ =====
            total_input_tokens = req1_input_tokens + req2_input_tokens
            total_output_tokens = req1_output_tokens + req2_output_tokens
            total_tokens = total_input_tokens + total_output_tokens

            # ===== ВОЗВРАЩАЕМ РЕЗУЛЬТАТ =====
            return {
                "evaluator": self.__class__.__name__,
                "evaluator_display": self.get_evaluator_name(),
                "status": "success",
                "analysis": analysis,
                "summary": self.extract_summary(analysis),
                "verdict": self.get_verdict(),
                "confidence": self.get_confidence(),
                # Общие суммы
                "tokens_used": total_tokens,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "verdict_request_used": verdict_request_used,
                # Разбор по запросам
                "req1_input_tokens": req1_input_tokens,
                "req1_output_tokens": req1_output_tokens,
                "req2_input_tokens": req2_input_tokens,
                "req2_output_tokens": req2_output_tokens,
            }            
        except Exception as e:
            return {
                "evaluator": self.__class__.__name__,
                "evaluator_display": self.get_evaluator_name(),
                "status": "error",
                "error": str(e)
            }
    
    def extract_summary(self, analysis: str) -> str:
        """
        Извлекает summary из анализа Claude.
        Ищет строку "SUMMARY:" и берёт текст до вердикта.
        
        Args:
            analysis (str): Полный текст анализа
            
        Returns:
            str: Summary текст (полностью, без обрезаний)
        """
        if "SUMMARY:" in analysis:
            summary_start = analysis.find("SUMMARY:") + len("SUMMARY:")
            summary_text = analysis[summary_start:].strip()
            
            # Берём до следующего маркера
            end_markers = ["VERDICT_RECOMMENDATION:", "CONFIDENCE_LEVEL:"]
            end_pos = len(summary_text)
            
            for marker in end_markers:
                pos = summary_text.find(marker)
                if pos != -1:
                    end_pos = min(end_pos, pos)
            
            return summary_text[:end_pos].strip()
        
        # Fallback: первое полное предложение
        lines = analysis.split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("---"):
                if "." in line:
                    return line.split(".")[0] + "."
                return line
        
        return "No summary available"
    
    def get_verdict(self) -> str:
        """
        Парсит вердикт из последнего анализа.
        
        Returns:
            str: VIABLE / VIABLE_IF / NEEDS_VALIDATION / RISKY / NOT_VIABLE / UNCERTAIN
        """
        if not self.last_analysis:
            return "UNCERTAIN"
        
        if "NOT_VIABLE" in self.last_analysis:
            return "NOT_VIABLE"
        if "VIABLE_IF" in self.last_analysis:
            return "VIABLE_IF"
        if "NEEDS_VALIDATION" in self.last_analysis:
            return "NEEDS_VALIDATION"
        if "RISKY" in self.last_analysis:
            return "RISKY"
        if "VIABLE" in self.last_analysis:
            return "VIABLE"
        
        return "UNCERTAIN"
    
    def get_confidence(self) -> float:
        """
        Парсит уверенность из анализа.
        Ищет "CONFIDENCE_LEVEL: ХХ"
        
        Returns:
            float: Уверенность 0.0-1.0
        """
        if not self.last_analysis or "CONFIDENCE_LEVEL:" not in self.last_analysis:
            return 0.75
        
        try:
            for line in self.last_analysis.split('\n'):
                if 'CONFIDENCE_LEVEL:' in line:
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        conf_value = int(numbers[0])
                        return conf_value / 100 if conf_value > 1 else conf_value
        except Exception:
            pass
        
        return 0.75
    
    @property
    def full_prompt(self) -> str:
        """Полный промпт для отладки."""
        return f"""
=== SYSTEM PROMPT ===
{self.get_system_prompt()}

=== EVALUATION PROMPT ===
{self.get_evaluation_prompt()}

=== BUSINESS IDEA ===
{self.business_idea}
"""