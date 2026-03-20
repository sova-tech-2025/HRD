from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from bot.database.models import (
    Attestation,
    AttestationQuestion,
    LearningPath,
)
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger


class AssessmentRepository(BaseRepository):
    """Repository for attestation CRUD operations."""

    async def create(
        self,
        name: str,
        passing_score: float,
        creator_id: int,
        company_id: int = None,
        assessment_type: str = "attestation",
    ) -> Optional[Attestation]:
        """Создание новой аттестации/экзамена (с привязкой к компании)"""
        try:
            attestation = Attestation(
                name=name,
                passing_score=passing_score,
                max_score=0,  # Будет обновлено при добавлении вопросов
                created_by_id=creator_id,
                company_id=company_id,
                assessment_type=assessment_type,
            )

            self.session.add(attestation)
            await self.session.flush()
            await self.session.commit()

            logger.info(f"Аттестация '{name}' создана с ID: {attestation.id}")
            return attestation

        except Exception as e:
            logger.error(f"Ошибка создания аттестации: {e}")
            await self.session.rollback()

            return None

    async def add_question(
        self, attestation_id: int, question_text: str, max_points: float, question_number: int
    ) -> Optional[AttestationQuestion]:
        """Добавление вопроса к аттестации"""
        try:
            question = AttestationQuestion(
                attestation_id=attestation_id,
                question_number=question_number,
                question_text=question_text,
                max_points=max_points,
            )

            self.session.add(question)
            await self.session.flush()

            # Обновляем максимальный балл аттестации
            attestation = await self.session.get(Attestation, attestation_id)
            if attestation:
                attestation.max_score += max_points

            await self.session.commit()

            logger.info(f"Вопрос добавлен к аттестации {attestation_id}")
            return question

        except Exception as e:
            logger.error(f"Ошибка добавления вопроса к аттестации: {e}")
            await self.session.rollback()
            return None

    async def get_all(self, company_id: int = None, assessment_type: str = "attestation") -> List[Attestation]:
        """Получение всех аттестаций/экзаменов (с фильтрацией по компании и типу)

        КРИТИЧЕСКИ ВАЖНО: Если company_id = None, возвращается пустой список (deny-by-default)
        для предотвращения утечки данных между компаниями.
        """
        try:
            # КРИТИЧЕСКАЯ БЕЗОПАСНОСТЬ: deny-by-default
            if company_id is None:
                logger.warning(
                    "get_all_attestations вызван с company_id=None - возвращаем пустой список для безопасности"
                )
                return []

            try:
                query = (
                    select(Attestation)
                    .options(selectinload(Attestation.questions))
                    .where(
                        Attestation.is_active == True,
                        Attestation.company_id == company_id,
                        Attestation.assessment_type == assessment_type,
                    )
                    .order_by(Attestation.created_date.desc())
                )

                result = await self.session.execute(query)
                attestations = result.scalars().all()
                return list(attestations)
            except Exception as table_error:
                logger.error(f"Ошибка получения аттестаций (таблица не существует?): {table_error}")
                return []

        except Exception as e:
            logger.error(f"Ошибка получения аттестаций: {e}")
            return []

    async def get_by_id(self, attestation_id: int, company_id: int = None) -> Optional[Attestation]:
        """Получение аттестации по ID с вопросами (с изоляцией по компании)"""
        try:
            query = (
                select(Attestation).options(selectinload(Attestation.questions)).where(Attestation.id == attestation_id)
            )

            # Добавляем фильтр по company_id для изоляции
            if company_id is not None:
                query = query.where(Attestation.company_id == company_id)

            result = await self.session.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Ошибка получения аттестации {attestation_id}: {e}")
            return None

    async def check_in_use(self, attestation_id: int, company_id: int = None) -> bool:
        """Проверка, используется ли аттестация в траекториях (с изоляцией по компании)"""
        try:
            # Проверяем, есть ли траектории с данной аттестацией
            query = select(LearningPath).where(LearningPath.attestation_id == attestation_id)

            # Добавляем фильтр по company_id для изоляции
            if company_id is not None:
                query = query.where(LearningPath.company_id == company_id)

            result = await self.session.execute(query)
            learning_paths = result.scalars().all()

            logger.info(f"Проверка использования аттестации {attestation_id}: найдено {len(learning_paths)} траекторий")
            return len(learning_paths) > 0

        except Exception as e:
            logger.error(f"Ошибка проверки использования аттестации {attestation_id}: {e}")
            return True  # В случае ошибки считаем, что аттестация используется (безопасно)

    async def delete(self, attestation_id: int, company_id: int = None) -> bool:
        """Удаление аттестации (с изоляцией по компании)"""
        try:
            # Сначала проверяем, не используется ли аттестация
            if await self.check_in_use(attestation_id, company_id=company_id):
                logger.warning(f"Попытка удалить используемую аттестацию {attestation_id}")
                return False

            # Получаем аттестацию для логирования с изоляцией
            query = select(Attestation).where(Attestation.id == attestation_id)

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(Attestation.company_id == company_id)

            result = await self.session.execute(query)
            attestation = result.scalar_one_or_none()

            if not attestation:
                logger.warning(f"Аттестация {attestation_id} не найдена для удаления")
                return False

            # Удаляем все вопросы аттестации
            await self.session.execute(
                delete(AttestationQuestion).where(AttestationQuestion.attestation_id == attestation_id)
            )

            # Удаляем саму аттестацию
            await self.session.execute(delete(Attestation).where(Attestation.id == attestation_id))

            await self.session.commit()

            logger.info(f"Аттестация '{attestation.name}' (ID: {attestation_id}) успешно удалена")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Ошибка удаления аттестации {attestation_id}: {e}")
            return False

    async def get_trajectories_using(self, attestation_id: int, company_id: int = None) -> List[str]:
        """Получение названий траекторий, использующих данную аттестацию (с изоляцией по компании)"""
        try:
            # Получаем траектории с данной аттестацией
            query = select(LearningPath).where(LearningPath.attestation_id == attestation_id)

            # Добавляем фильтр по company_id для изоляции
            if company_id is not None:
                query = query.where(LearningPath.company_id == company_id)

            result = await self.session.execute(query)
            learning_paths = result.scalars().all()

            # Извлекаем названия траекторий
            trajectory_names = []
            for path in learning_paths:
                if hasattr(path, "name") and path.name:
                    trajectory_names.append(path.name)
                else:
                    # Fallback для mock объектов
                    trajectory_names.append(f"Траектория {path.id}")

            logger.info(f"Получены названия траекторий для аттестации {attestation_id}: {trajectory_names}")
            return trajectory_names

        except Exception as e:
            logger.error(f"Ошибка получения названий траекторий для аттестации {attestation_id}: {e}")
            return ["Неизвестные траектории"]  # Fallback в случае ошибки

    async def save_with_trajectory_and_group(
        self, trajectory_data: dict, attestation_id: int, group_id: int, company_id: int = None
    ) -> bool:
        """Сохранение траектории с аттестацией и привязкой к группе (с привязкой к компании)"""
        try:
            from bot.database.db import save_trajectory_to_database

            # Добавляем недостающие данные
            trajectory_data["group_id"] = group_id
            trajectory_data["attestation_id"] = attestation_id

            # Создаем траекторию
            learning_path = await save_trajectory_to_database(self.session, trajectory_data, company_id)
            if not learning_path:
                return False

            # Обновляем аттестацию, привязывая её к траектории
            if attestation_id:
                update_stmt = (
                    update(LearningPath)
                    .where(LearningPath.id == learning_path.id)
                    .values(attestation_id=attestation_id)
                )
                await self.session.execute(update_stmt)
                await self.session.commit()

            logger.info(f"Траектория {learning_path.id} привязана к группе {group_id} и аттестации {attestation_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка привязки траектории к группе и аттестации: {e}")
            await self.session.rollback()
            return False

    async def update_learning_path_attestation(
        self, path_id: int, new_attestation_id: Optional[int], company_id: int = None
    ) -> bool:
        """Изменение аттестации траектории обучения (может быть None для удаления) с изоляцией по компании"""
        try:
            from bot.database.db import get_learning_path_by_id

            # Проверяем существование траектории и принадлежность к компании
            learning_path = await get_learning_path_by_id(self.session, path_id, company_id=company_id)
            if not learning_path:
                logger.error(f"Траектория с ID {path_id} не найдена или не принадлежит компании {company_id}")
                return False

            # Если указана новая аттестация, проверяем её существование и принадлежность к компании
            if new_attestation_id is not None:
                attestation = await self.get_by_id(new_attestation_id, company_id=company_id)
                if not attestation:
                    logger.error(
                        f"Аттестация с ID {new_attestation_id} не найдена или не принадлежит компании {company_id}"
                    )
                    return False

            old_attestation_id = learning_path.attestation_id
            stmt = update(LearningPath).where(LearningPath.id == path_id)

            # Изоляция по компании - КРИТИЧЕСКИ ВАЖНО!
            if company_id is not None:
                stmt = stmt.where(LearningPath.company_id == company_id)

            await self.session.execute(stmt.values(attestation_id=new_attestation_id))
            await self.session.commit()

            action = "удалена" if new_attestation_id is None else f"изменена на {new_attestation_id}"
            logger.info(f"Аттестация траектории {path_id} {action} (была: {old_attestation_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка изменения аттестации траектории {path_id}: {e}")
            await self.session.rollback()
            return False
