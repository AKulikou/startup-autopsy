"""
Вывод статистики расходов токенов и стоимости API запросов.
"""

import logging

logger = logging.getLogger(__name__)


class TokenSummary:
    """Форматирует и выводит таблицу расходов токенов."""
    
    # Стоимость токена для Claude
    COST_PER_1K_TOKENS = 0.003  # $0.003 за 1000 токенов
    
    @staticmethod
    def print_summary(results: list) -> None:
        """
        Выводит детальную таблицу расходов токенов в консоль.
        
        Args:
            results (list): Список результатов от evaluators
        """
        # Фильтруем только успешные результаты
        successful_results = [r for r in results if r["status"] == "success"]
        
        if not successful_results:
            logger.info("⚠ Нет успешных результатов для отображения статистики токенов.")
            return
        
        logger.info("\n" + "="*140)
        logger.info("📊 TOKEN USAGE SUMMARY (Development Only)")
        logger.info("="*140)
        logger.info("")
        
        # Таблица с детальным разбором
        logger.info(f"{'Evaluator':<30} | {'Total':<20} | {'Cost':<10}")
        logger.info(f"{'':<30} | {'(In / Out)':<20} | {'(USD)':<10}")
        logger.info("-"*140)
        
        total_input_all = 0
        total_output_all = 0
        total_cost_all = 0.0
        
        for result in successful_results:
            tokens = result.get("tokens_used", 0)
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            total_input_all += input_tokens
            total_output_all += output_tokens
            
            cost = TokenSummary._calculate_cost(tokens)
            total_cost_all += cost
            
            evaluator_name = result.get("evaluator_display", "Unknown")
            
            # ← Общие токены
            total_str = f"{input_tokens} / {output_tokens}"
            
            logger.info(
                f"{evaluator_name:<30} | {total_str:<20} | ${cost:<9.4f}"
            )
        
        # Итоговая строка
        logger.info("-"*140)
        total_tokens = total_input_all + total_output_all
        total_cost_final = TokenSummary._calculate_cost(total_tokens)
        total_str = f"{total_input_all} / {total_output_all}"
        logger.info(f"{'TOTAL':<30} | {total_str:<20} | ${total_cost_final:<9.4f}")
        logger.info("")
        
        logger.info("Details:")
        logger.info("  (In / Out) = (Input tokens / Output tokens)")
        logger.info("  — = Request not used")
        logger.info("="*140 + "\n")
    
    @staticmethod
    def _calculate_cost(tokens: int) -> float:
        """
        Рассчитывает стоимость в USD для количества токенов.
        
        Args:
            tokens (int): Количество токенов
        
        Returns:
            float: Приблизительная стоимость в USD
        """
        return (tokens / 1000) * TokenSummary.COST_PER_1K_TOKENS