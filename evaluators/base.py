"""
Базовый класс для всех оценщиков.
Каждый оценщик наследуется от этого класса и переопределяет методы.
"""

from abc import ABC, abstractmethod
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, MODEL, MAX_TOKENS
from evaluators.schemas import EvaluatorResult


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
    
    def evaluate(self) -> dict:
        """
        Run the evaluation and return a result dict.

        Returns a dict with "status": "success" and the structured fields,
        or "status": "error" with an error message. Never raises.
        """
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.get_system_prompt(),
                messages=[{
                    "role": "user",
                    "content": f"{self.get_evaluation_prompt()}\n\nBusiness Idea:\n{self.business_idea}",
                }],
                output_format=EvaluatorResult,
            )

            # Check why generation stopped before trusting the output
            if response.stop_reason == "max_tokens":
                raise RuntimeError(
                    f"Response truncated at max_tokens={self.max_tokens}; "
                    "increase MAX_TOKENS in config.py"
                )
            if response.stop_reason == "refusal":
                raise RuntimeError("Model refused to evaluate this idea")

            result = response.parsed_output
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            return {
                "evaluator": self.__class__.__name__,
                "evaluator_display": self.get_evaluator_name(),
                "status": "success",
                **result.model_dump(mode="json"),
                "tokens_used": input_tokens + output_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

        except Exception as e:
            return {
                "evaluator": self.__class__.__name__,
                "evaluator_display": self.get_evaluator_name(),
                "status": "error",
                "error": str(e),
            }
    
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