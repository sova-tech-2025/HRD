from __future__ import annotations

from sqlalchemy import select, update

from bot.database.models import (
    LearningPath,
    LearningSession,
    LearningStage,
    TraineeLearningPath,
)
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger
from bot.utils.timezone import moscow_now


class LearningPathRepository(BaseRepository):
    """Репозиторий для удаления траекторий, этапов и сессий (soft delete)."""

    async def delete(self, trajectory_id: int, company_id: int) -> bool:
        """Мягкое удаление траектории + каскадный soft delete этапов и сессий.

        НЕ удаляет: тесты, результаты тестов, прогресс стажёров,
        аттестации — они остаются в БД для аудита.
        """
        try:
            # Проверяем существование траектории
            result = await self.session.execute(
                select(LearningPath).where(
                    LearningPath.id == trajectory_id,
                    LearningPath.is_active == True,  # noqa: E712
                    LearningPath.company_id == company_id,
                )
            )
            trajectory = result.scalar_one_or_none()
            if not trajectory:
                logger.error(f"Траектория {trajectory_id} не найдена или не принадлежит компании {company_id}")
                return False

            # Nullify attestation_id (освобождаем аттестацию для повторного использования)
            if trajectory.attestation_id:
                await self.session.execute(
                    update(LearningPath).where(LearningPath.id == trajectory_id).values(attestation_id=None)
                )

            # Soft delete траектории
            if not await self._soft_delete(LearningPath, trajectory_id, company_id):
                return False

            # Получаем ID этапов для каскадного soft delete сессий
            stages_result = await self.session.execute(
                select(LearningStage.id).where(LearningStage.learning_path_id == trajectory_id)
            )
            stage_ids = [row[0] for row in stages_result.all()]

            # Каскадный soft delete этапов
            await self._bulk_soft_delete(LearningStage, LearningStage.learning_path_id == trajectory_id)

            # Каскадный soft delete сессий (по всем этапам траектории)
            if stage_ids:
                await self._bulk_soft_delete(LearningSession, LearningSession.stage_id.in_(stage_ids))

            # Деактивация назначений траектории стажёрам
            await self.session.execute(
                update(TraineeLearningPath)
                .where(
                    TraineeLearningPath.learning_path_id == trajectory_id,
                    TraineeLearningPath.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )

            await self.session.commit()
            logger.info(f"Траектория {trajectory_id} '{trajectory.name}' мягко удалена с каскадом")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления траектории {trajectory_id}: {e}")
            await self.session.rollback()
            return False

    async def delete_stage(self, stage_id: int) -> bool:
        """Мягкое удаление этапа + каскадный soft delete сессий.

        Проверяет: нет стажёров с назначенной траекторией.
        """
        try:
            # Проверяем существование этапа
            result = await self.session.execute(
                select(LearningStage).where(
                    LearningStage.id == stage_id,
                    LearningStage.is_active == True,  # noqa: E712
                )
            )
            stage = result.scalar_one_or_none()
            if not stage:
                logger.error(f"Этап {stage_id} не найден")
                return False

            # Проверяем: нет стажёров с назначенной траекторией
            from bot.database.db import check_stage_has_trainees

            if await check_stage_has_trainees(self.session, stage_id):
                logger.warning(f"Нельзя удалить этап {stage_id}: есть стажёры с назначенной траекторией")
                return False

            # Soft delete этапа
            await self.session.execute(
                update(LearningStage)
                .where(LearningStage.id == stage_id)
                .values(is_active=False, deleted_at=moscow_now())
            )

            # Каскадный soft delete сессий этапа
            await self._bulk_soft_delete(LearningSession, LearningSession.stage_id == stage_id)

            await self.session.commit()
            logger.info(f"Этап {stage_id} '{stage.name}' мягко удален с каскадом")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления этапа {stage_id}: {e}")
            await self.session.rollback()
            return False

    async def delete_session(self, session_id: int) -> bool:
        """Мягкое удаление сессии.

        Проверяет: нет стажёров с назначенной траекторией.
        """
        try:
            # Проверяем существование сессии
            result = await self.session.execute(
                select(LearningSession).where(
                    LearningSession.id == session_id,
                    LearningSession.is_active == True,  # noqa: E712
                )
            )
            learning_session = result.scalar_one_or_none()
            if not learning_session:
                logger.error(f"Сессия {session_id} не найдена")
                return False

            # Проверяем: нет стажёров с назначенной траекторией
            from bot.database.db import check_session_has_trainees

            if await check_session_has_trainees(self.session, session_id):
                logger.warning(f"Нельзя удалить сессию {session_id}: есть стажёры с назначенной траекторией")
                return False

            # Soft delete сессии
            await self.session.execute(
                update(LearningSession)
                .where(LearningSession.id == session_id)
                .values(is_active=False, deleted_at=moscow_now())
            )

            await self.session.commit()
            logger.info(f"Сессия {session_id} '{learning_session.name}' мягко удалена")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления сессии {session_id}: {e}")
            await self.session.rollback()
            return False
