from __future__ import annotations

from sqlalchemy import delete, select, update

from bot.database.models import (
    Attestation,
    Company,
    Group,
    KnowledgeFolder,
    KnowledgeMaterial,
    LearningPath,
    Mentorship,
    Object,
    Test,
    TraineeAttestation,
    TraineeLearningPath,
    TraineeManager,
    TraineeTestAccess,
    User,
    user_groups,
    user_roles,
)
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger


class UserRepository(BaseRepository):
    """Репозиторий для удаления пользователей (soft delete)."""

    async def delete(self, user_id: int, company_id: int) -> bool:
        """Мягкое удаление пользователя.

        Soft delete пользователя + hard delete M2M ассоциаций +
        деактивация связанных записей + nullify created_by_id.
        Операционные данные (TestResult, прогресс и др.) остаются для аудита.
        """
        try:
            # Проверяем существование и принадлежность к компании
            result = await self.session.execute(
                select(User).where(
                    User.id == user_id,
                    User.is_active == True,  # noqa: E712
                )
            )
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"Пользователь {user_id} не найден")
                return False

            if company_id is not None and user.company_id != company_id:
                logger.error(
                    f"Попытка удалить пользователя {user_id} из другой компании. "
                    f"Принадлежит: {user.company_id}, запрос: {company_id}"
                )
                return False

            logger.info(f"Начинаем мягкое удаление пользователя {user_id}: {user.full_name}")

            # 1. Soft delete пользователя
            if not await self._soft_delete(User, user_id, company_id):
                return False

            # 2. Hard delete M2M ассоциаций (чтобы не появлялся в списках групп/ролей)
            await self.session.execute(delete(user_roles).where(user_roles.c.user_id == user_id))
            await self.session.execute(delete(user_groups).where(user_groups.c.user_id == user_id))

            # 3. Деактивация связанных записей
            await self.session.execute(
                update(Mentorship)
                .where(
                    (Mentorship.mentor_id == user_id) | (Mentorship.trainee_id == user_id),
                    Mentorship.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )
            await self.session.execute(
                update(TraineeTestAccess)
                .where(
                    (TraineeTestAccess.trainee_id == user_id) | (TraineeTestAccess.granted_by_id == user_id),
                    TraineeTestAccess.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )
            await self.session.execute(
                update(TraineeLearningPath)
                .where(
                    (TraineeLearningPath.trainee_id == user_id) | (TraineeLearningPath.assigned_by_id == user_id),
                    TraineeLearningPath.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )
            await self.session.execute(
                update(TraineeAttestation)
                .where(
                    (TraineeAttestation.trainee_id == user_id)
                    | (TraineeAttestation.manager_id == user_id)
                    | (TraineeAttestation.assigned_by_id == user_id),
                    TraineeAttestation.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )
            await self.session.execute(
                update(TraineeManager)
                .where(
                    (TraineeManager.trainee_id == user_id)
                    | (TraineeManager.manager_id == user_id)
                    | (TraineeManager.assigned_by_id == user_id),
                    TraineeManager.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )

            # 4. Nullify created_by_id (сущности остаются в системе)
            await self.session.execute(update(Test).where(Test.creator_id == user_id).values(creator_id=None))
            await self.session.execute(
                update(Attestation).where(Attestation.created_by_id == user_id).values(created_by_id=None)
            )
            await self.session.execute(
                update(LearningPath).where(LearningPath.created_by_id == user_id).values(created_by_id=None)
            )
            await self.session.execute(
                update(KnowledgeMaterial).where(KnowledgeMaterial.created_by_id == user_id).values(created_by_id=None)
            )

            knowledge_folder_query = update(KnowledgeFolder).where(KnowledgeFolder.created_by_id == user_id)
            if company_id is not None:
                knowledge_folder_query = knowledge_folder_query.where(KnowledgeFolder.company_id == company_id)
            await self.session.execute(knowledge_folder_query.values(created_by_id=None))

            object_query = update(Object).where(Object.created_by_id == user_id)
            if company_id is not None:
                object_query = object_query.where(Object.company_id == company_id)
            await self.session.execute(object_query.values(created_by_id=None))

            group_query = update(Group).where(Group.created_by_id == user_id)
            if company_id is not None:
                group_query = group_query.where(Group.company_id == company_id)
            await self.session.execute(group_query.values(created_by_id=None))

            await self.session.execute(
                update(Company).where(Company.created_by_id == user_id).values(created_by_id=None)
            )

            await self.session.commit()
            logger.info(f"Пользователь {user_id} '{user.full_name}' мягко удален")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
            await self.session.rollback()
            return False
