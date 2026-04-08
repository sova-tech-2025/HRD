from __future__ import annotations

from sqlalchemy import func, select, update

from bot.database.models import Test, TestQuestion
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger
from bot.utils.timezone import moscow_now


class TestRepository(BaseRepository):
    """Репозиторий для удаления тестов и вопросов (soft delete)."""

    async def delete(self, test_id: int, company_id: int) -> bool:
        """Мягкое удаление теста + каскадный soft delete вопросов."""
        try:
            # Soft delete теста
            if not await self._soft_delete(Test, test_id, company_id):
                logger.error(f"Тест {test_id} не найден или не принадлежит компании {company_id}")
                return False

            # Каскадный soft delete вопросов
            await self._bulk_soft_delete(TestQuestion, TestQuestion.test_id == test_id)

            await self.session.commit()
            logger.info(f"Тест {test_id} мягко удален с вопросами")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления теста {test_id}: {e}")
            await self.session.rollback()
            return False

    async def delete_question(self, question_id: int, company_id: int) -> bool:
        """Мягкое удаление вопроса + пересчёт max_score теста."""
        try:
            # Получаем вопрос для пересчёта max_score
            result = await self.session.execute(
                select(TestQuestion).where(
                    TestQuestion.id == question_id,
                    TestQuestion.is_active == True,  # noqa: E712
                )
            )
            question = result.scalar_one_or_none()
            if not question:
                return False

            # Проверяем принадлежность теста к компании
            test_result = await self.session.execute(
                select(Test).where(
                    Test.id == question.test_id,
                    Test.company_id == company_id,
                )
            )
            if not test_result.scalar_one_or_none():
                logger.error(f"Тест {question.test_id} не принадлежит компании {company_id}")
                return False

            # Soft delete вопроса
            await self.session.execute(
                update(TestQuestion)
                .where(TestQuestion.id == question_id)
                .values(is_active=False, deleted_at=moscow_now())
            )

            # Пересчёт max_score теста (только по активным вопросам)
            score_result = await self.session.execute(
                select(func.sum(TestQuestion.points)).where(
                    TestQuestion.test_id == question.test_id,
                    TestQuestion.is_active == True,  # noqa: E712
                )
            )
            max_score = score_result.scalar() or 0

            await self.session.execute(update(Test).where(Test.id == question.test_id).values(max_score=max_score))

            await self.session.commit()
            logger.info(f"Вопрос {question_id} мягко удален, max_score теста {question.test_id} = {max_score}")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления вопроса {question_id}: {e}")
            await self.session.rollback()
            return False
