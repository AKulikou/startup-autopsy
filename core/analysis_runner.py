"""
Запуск анализа бизнес-идеи тремя оценщиками.
Управление процессом оценки, сохранением результатов и агрегацией.
"""

import logging
from datetime import datetime
from pathlib import Path

from evaluators.profitable_designer import ProfitableAppDesigner
from evaluators.no_code_stack import NoCodeStackMaster
from evaluators.reality_auditor import RealityAuditor
from core.idea_processor import IdeaProcessor
from core.report_aggregator import ReportAggregator
from core.token_summary import TokenSummary

logger = logging.getLogger(__name__)


class AnalysisRunner:
    """
    Управляет процессом запуска анализа бизнес-идеи.
    
    Отвечает за:
    1. Загрузку идеи
    2. Запуск evaluators
    3. Сохранение результатов
    4. Агрегацию отчётов
    5. Вывод статистики
    """
    
    def __init__(self, processor: IdeaProcessor):
        """
        Args:
            processor (IdeaProcessor): Процессор для работы с идеями
        """
        self.processor = processor
        self.aggregator = ReportAggregator()
    
    def run(self, idea_name: str) -> bool:
        """
        Запускает полный цикл анализа идеи.
        
        Args:
            idea_name (str): Имя идеи для анализа
        
        Returns:
            bool: True если анализ завершился успешно
        """
        # Шаг 1: Загружаем идею
        idea_content = self._load_idea(idea_name)
        if not idea_content:
            return False
        
        # Шаг 2: Запускаем оценщиков
        results = self._run_evaluators(idea_content)
        if not results:
            return False
        
        # Шаг 3: Сохраняем отчёты
        self._save_reports(results, idea_name)
        
        # Шаг 4: Генерируем и сохраняем synthesis
        self._generate_synthesis(results, idea_name)
        
        # Шаг 5: Выводим статистику токенов
        TokenSummary.print_summary(results)
        
        return True
    
    def _load_idea(self, idea_name: str) -> str:
        """
        Загружает содержимое идеи.
        
        Args:
            idea_name (str): Имя идеи
        
        Returns:
            str: Содержимое идеи или None если ошибка
        """
        idea_content = self.processor.load_idea(idea_name)
        if not idea_content:
            logger.error(f"❌ Не удалось загрузить идею: {idea_name}")
            return None
        
        logger.info(f"\n✓ Идея загружена ({len(idea_content)} символов)")
        logger.info("⏳ Анализирую (3 оценщика)...\n")
        
        return idea_content
    
    def _run_evaluators(self, idea_content: str) -> list:
        """
        Запускает всех оценщиков на идее.
        
        Args:
            idea_content (str): Содержимое идеи
        
        Returns:
            list: Список результатов от evaluators
        """
        evaluators = [
            ProfitableAppDesigner(idea_content),
            NoCodeStackMaster(idea_content),
            RealityAuditor(idea_content)
        ]
        
        results = []
        for evaluator in evaluators:
            result = evaluator.evaluate()
            results.append(result)
            
            # Логируем ошибки
            if result["status"] == "error":
                logger.error(f"❌ {result['evaluator_display']} — Error: {result.get('error', 'Unknown')}")
        
        return results
    
    def _save_reports(self, results: list, idea_name: str) -> None:
        """
        Сохраняет полные отчёты каждого оценщика.
        
        Args:
            results (list): Список результатов
            idea_name (str): Имя идеи
        """
        logger.info("\n💾 Сохраняю полные отчёты...")
        
        for result in results:
            if result["status"] == "success":
                result_path = self.processor.save_analysis(
                    idea_name,
                    result["analysis"],
                    result["tokens_used"],
                    result["evaluator_display"]
                )
                logger.info(f"  • {result['evaluator_display']}: {result_path.name}")
    
    def _generate_synthesis(self, results: list, idea_name: str) -> None:
        """
        Генерирует и сохраняет synthesis отчёт.
        
        Args:
            results (list): Список результатов
            idea_name (str): Имя идеи
        """
        logger.info("\n📊 Генерирую synthesis report...")
        
        synthesis = self.aggregator.aggregate(results)
        
        # Выводим synthesis на экран
        logger.info("\n" + synthesis)
        
        # Сохраняем в файл с таймстампом
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        synthesis_filename = f"{idea_name}_SYNTHESIS_{timestamp}.md"
        synthesis_path = self.processor.results_dir / synthesis_filename
        
        with open(synthesis_path, "w", encoding="utf-8") as f:
            f.write(synthesis)
        
        logger.info(f"✓ Synthesis сохранён: {synthesis_path.name}\n")
