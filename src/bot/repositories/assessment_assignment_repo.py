from typing import List, Optional

from sqlalchemy import or_, select, update
from sqlalchemy.orm import selectinload

from bot.database.models import (
    Attestation,
    AttestationQuestion,
    LearningStage,
    Role,
    TraineeAttestation,
    User,
    user_groups,
    user_roles,
)
from bot.repositories.admin_repo import admin_inclusive_role_filter  # noqa: E402
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger


class AssessmentAssignmentRepository(BaseRepository):
    async def assign(
        self,
        trainee_id: int,
        manager_id: int,
        attestation_id: int,
        assigned_by_id: int,
        company_id: int = None,
    ) -> Optional[TraineeAttestation]:
        """Назначение аттестации стажеру наставником (с изоляцией по компании)"""
        try:
            from bot.database.db import get_attestation_by_id, get_user_by_id

            # Изоляция по компании - проверяем принадлежность всех участников
            if company_id is not None:
                trainee = await get_user_by_id(self.session, trainee_id)
                manager = await get_user_by_id(self.session, manager_id)
                attestation = await get_attestation_by_id(self.session, attestation_id, company_id=company_id)

                if not trainee or trainee.company_id != company_id:
                    logger.error(f"Стажер {trainee_id} не найден или не принадлежит компании {company_id}")
                    return None

                if not manager or manager.company_id != company_id:
                    logger.error(f"Руководитель {manager_id} не найден или не принадлежит компании {company_id}")
                    return None

                if not attestation:
                    logger.error(f"Аттестация {attestation_id} не найдена или не принадлежит компании {company_id}")
                    return None
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем дубликаты по всем параметрам включая manager_id
            existing = await self.session.execute(
                select(TraineeAttestation)
                .where(TraineeAttestation.trainee_id == trainee_id)
                .where(TraineeAttestation.manager_id == manager_id)
                .where(TraineeAttestation.attestation_id == attestation_id)
                .where(TraineeAttestation.is_active == True)
            )

            existing_assignment = existing.scalar_one_or_none()
            if existing_assignment:
                logger.warning(
                    f"Аттестация {attestation_id} уже назначена стажеру {trainee_id} с руководителем {manager_id}"
                )
                return existing_assignment  # Возвращаем существующее назначение вместо None

            # Дополнительная проверка: деактивируем все старые назначения этой же аттестации для этого стажера
            await self.session.execute(
                update(TraineeAttestation)
                .where(TraineeAttestation.trainee_id == trainee_id)
                .where(TraineeAttestation.attestation_id == attestation_id)
                .where(TraineeAttestation.is_active == True)
                .values(is_active=False)
            )
            logger.info(f"Деактивированы старые назначения аттестации {attestation_id} для стажера {trainee_id}")

            # Создаем назначение аттестации
            trainee_attestation = TraineeAttestation(
                trainee_id=trainee_id,
                manager_id=manager_id,
                attestation_id=attestation_id,
                assigned_by_id=assigned_by_id,
                status="assigned",
            )

            self.session.add(trainee_attestation)
            await self.session.flush()

            logger.info(f"Аттестация {attestation_id} назначена стажеру {trainee_id} с руководителем {manager_id}")
            return trainee_attestation

        except Exception as e:
            logger.error(f"Ошибка назначения аттестации: {e}")
            return None

    async def get_for_manager(self, manager_id: int, company_id: int = None) -> List[TraineeAttestation]:
        """Получение всех назначенных аттестаций для руководителя (с изоляцией по компании)"""
        try:
            from sqlalchemy.orm import selectinload

            query = (
                select(TraineeAttestation)
                .options(
                    selectinload(TraineeAttestation.trainee).selectinload(User.work_object),
                    selectinload(TraineeAttestation.attestation),
                    selectinload(TraineeAttestation.assigned_by),
                )
                .join(User, TraineeAttestation.trainee_id == User.id)
                .where(TraineeAttestation.manager_id == manager_id)
                .where(TraineeAttestation.is_active == True)
            )

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(User.company_id == company_id)

            query = query.order_by(TraineeAttestation.assigned_date.desc())

            result = await self.session.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Ошибка получения назначенных аттестаций для руководителя {manager_id}: {e}")
            return []

    async def get_by_id(self, assignment_id: int, company_id: int = None) -> Optional[TraineeAttestation]:
        """Получение назначенной аттестации по ID (с изоляцией по компании)"""
        try:
            from sqlalchemy.orm import selectinload

            query = (
                select(TraineeAttestation)
                .options(
                    selectinload(TraineeAttestation.trainee).selectinload(User.work_object),
                    selectinload(TraineeAttestation.trainee).selectinload(User.internship_object),
                    selectinload(TraineeAttestation.manager),
                    selectinload(TraineeAttestation.attestation).selectinload(
                        Attestation.questions.and_(AttestationQuestion.is_active == True)  # noqa: E712
                    ),
                    selectinload(TraineeAttestation.assigned_by),
                )
                .join(User, TraineeAttestation.trainee_id == User.id)
                .where(TraineeAttestation.id == assignment_id)
                .where(TraineeAttestation.is_active == True)
            )

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(User.company_id == company_id)

            result = await self.session.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Ошибка получения аттестации {assignment_id}: {e}")
            return None

    async def update_schedule(self, assignment_id: int, date: str, time: str, company_id: int = None) -> bool:
        """Обновление даты и времени аттестации с изоляцией по компании"""
        try:
            # Проверяем существование назначенной аттестации и принадлежность к компании
            trainee_attestation = await self.get_by_id(assignment_id, company_id=company_id)
            if not trainee_attestation:
                logger.error(
                    f"Назначенная аттестация {assignment_id} не найдена или не принадлежит компании {company_id}"
                )
                return False

            result = await self.session.execute(
                update(TraineeAttestation)
                .where(TraineeAttestation.id == assignment_id)
                .values(scheduled_date=date, scheduled_time=time)
            )

            await self.session.commit()

            if result.rowcount > 0:
                logger.info(f"Обновлены дата и время для аттестации {assignment_id}: {date} {time}")
                return True
            return False

        except Exception as e:
            logger.error(f"Ошибка обновления расписания аттестации {assignment_id}: {e}")
            return False

    async def start_session(self, assignment_id: int, company_id: int = None) -> bool:
        """Начало сессии прохождения аттестации с изоляцией по компании"""
        try:
            # Проверяем существование назначенной аттестации и принадлежность к компании
            trainee_attestation = await self.get_by_id(assignment_id, company_id=company_id)
            if not trainee_attestation:
                logger.error(
                    f"Назначенная аттестация {assignment_id} не найдена или не принадлежит компании {company_id}"
                )
                return False

            result = await self.session.execute(
                update(TraineeAttestation).where(TraineeAttestation.id == assignment_id).values(status="in_progress")
            )

            await self.session.commit()

            if result.rowcount > 0:
                logger.info(f"Начата сессия аттестации {assignment_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Ошибка начала сессии аттестации {assignment_id}: {e}")
            return False

    async def complete_session(
        self,
        assignment_id: int,
        total_score: float,
        max_score: float,
        is_passed: bool,
        company_id: int = None,
    ) -> bool:
        """Завершение сессии аттестации с результатами с изоляцией по компании"""
        try:
            # Проверяем существование назначенной аттестации и принадлежность к компании
            trainee_attestation = await self.get_by_id(assignment_id, company_id=company_id)
            if not trainee_attestation:
                logger.error(
                    f"Назначенная аттестация {assignment_id} не найдена или не принадлежит компании {company_id}"
                )
                return False

            # Обновляем статус назначения аттестации
            status = "completed" if is_passed else "failed"
            result = await self.session.execute(
                update(TraineeAttestation).where(TraineeAttestation.id == assignment_id).values(status=status)
            )

            if result.rowcount > 0:
                logger.info(
                    f"Завершена аттестация {assignment_id} со статусом {status}, результат: {total_score}/{max_score}"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Ошибка завершения аттестации {assignment_id}: {e}")
            return False

    async def get_status(self, trainee_id: int, attestation_id: int, company_id: int = None) -> str:
        """Получение статуса аттестации стажера: ⛔️ - не назначена, 🟡 - назначена, ✅ - пройдена (с изоляцией по компании)"""
        try:
            # Проверяем назначена ли аттестация
            query = (
                select(TraineeAttestation)
                .join(User, TraineeAttestation.trainee_id == User.id)
                .where(TraineeAttestation.trainee_id == trainee_id)
                .where(TraineeAttestation.attestation_id == attestation_id)
                .where(TraineeAttestation.is_active == True)
            )

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(User.company_id == company_id)

            assignment_result = await self.session.execute(query)
            assignment = assignment_result.scalar_one_or_none()

            if not assignment:
                return "\u26d4\ufe0f"  # Не назначена

            if assignment.status == "completed":
                return "\u2705"  # Пройдена
            elif assignment.status in ["assigned", "in_progress"]:
                return "\U0001f7e1"  # Назначена
            else:
                return "\u26d4\ufe0f"  # Провалена или отменена

        except Exception as e:
            logger.error(f"Ошибка получения статуса аттестации: {e}")
            return "\u26d4\ufe0f"

    async def get_managers(self, group_id: int, company_id: int = None) -> List[User]:
        """Получение списка руководителей для назначения аттестации (по группе стажера, с изоляцией по компании)"""
        try:
            query = (
                select(User)
                .join(user_roles, User.id == user_roles.c.user_id)
                .join(Role, user_roles.c.role_id == Role.id)
                .where(admin_inclusive_role_filter(["Руководитель"]))
                .where(User.is_active == True)
                .where(User.is_activated == True)
            )

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(User.company_id == company_id)

            result = await self.session.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Ошибка получения руководителей для аттестации: {e}")
            return []

    async def check_all_stages_completed(self, trainee_id: int) -> bool:
        """Проверка что стажер прошел ВСЕ этапы траектории перед аттестацией"""
        try:
            from bot.database.db import get_trainee_learning_path, get_trainee_stage_progress

            # Получаем траекторию стажера
            trainee_path = await get_trainee_learning_path(self.session, trainee_id)
            if not trainee_path:
                logger.warning(f"У стажера {trainee_id} нет назначенной траектории")
                return False

            # Получаем все этапы траектории
            stages_result = await self.session.execute(
                select(LearningStage)
                .where(LearningStage.learning_path_id == trainee_path.learning_path_id)
                .order_by(LearningStage.order_number)
            )
            all_stages = stages_result.scalars().all()

            if not all_stages:
                logger.warning(f"В траектории стажера {trainee_id} нет этапов")
                return False

            # Получаем прогресс стажера по этапам
            stages_progress = await get_trainee_stage_progress(self.session, trainee_path.id)

            # Проверяем что ВСЕ этапы завершены
            completed_stage_ids = [sp.stage_id for sp in stages_progress if sp.is_completed]
            all_stage_ids = [stage.id for stage in all_stages]

            uncompleted_stages = [stage_id for stage_id in all_stage_ids if stage_id not in completed_stage_ids]

            if uncompleted_stages:
                logger.info(f"Стажер {trainee_id} не завершил этапы: {uncompleted_stages}")
                return False

            logger.info(f"Стажер {trainee_id} успешно завершил ВСЕ этапы траектории")
            return True

        except Exception as e:
            logger.error(f"Ошибка проверки завершения этапов для стажера {trainee_id}: {e}")
            return False

    async def get_examiners(self, company_id: int = None) -> List[User]:
        """Получение списка экзаменаторов (руководители + сотрудники + рекрутеры)"""
        try:
            query = (
                select(User)
                .options(selectinload(User.roles))
                .join(user_roles, User.id == user_roles.c.user_id)
                .join(Role, user_roles.c.role_id == Role.id)
                .where(
                    admin_inclusive_role_filter(["Руководитель", "Сотрудник", "Рекрутер"]),
                    User.is_active == True,
                    User.is_activated == True,
                )
            )

            if company_id is not None:
                query = query.where(User.company_id == company_id)

            result = await self.session.execute(query)
            return list(result.scalars().unique().all())

        except Exception as e:
            logger.error(f"Ошибка получения экзаменаторов: {e}")
            return []

    async def get_for_examinee(self, examinee_id: int, company_id: int = None) -> List[TraineeAttestation]:
        """Получение назначенных экзаменов для сдающего"""
        try:
            query = (
                select(TraineeAttestation)
                .options(
                    selectinload(TraineeAttestation.manager),
                    selectinload(TraineeAttestation.attestation),
                    selectinload(TraineeAttestation.assigned_by),
                )
                .join(Attestation, TraineeAttestation.attestation_id == Attestation.id)
                .where(
                    TraineeAttestation.trainee_id == examinee_id,
                    TraineeAttestation.is_active == True,
                    Attestation.assessment_type == "exam",
                )
            )

            if company_id is not None:
                query = query.join(User, TraineeAttestation.trainee_id == User.id).where(User.company_id == company_id)

            query = query.order_by(TraineeAttestation.assigned_date.desc())

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Ошибка получения экзаменов для сдающего {examinee_id}: {e}")
            return []

    async def get_exam_assignments_for_examiner(
        self, examiner_id: int, company_id: int = None
    ) -> List[TraineeAttestation]:
        """Получение назначенных экзаменов для экзаменатора (аналог get_for_manager, но для экзаменов)"""
        try:
            query = (
                select(TraineeAttestation)
                .options(
                    selectinload(TraineeAttestation.trainee).selectinload(User.work_object),
                    selectinload(TraineeAttestation.trainee).selectinload(User.internship_object),
                    selectinload(TraineeAttestation.attestation),
                    selectinload(TraineeAttestation.assigned_by),
                )
                .join(Attestation, TraineeAttestation.attestation_id == Attestation.id)
                .join(User, TraineeAttestation.trainee_id == User.id)
                .where(
                    TraineeAttestation.manager_id == examiner_id,
                    TraineeAttestation.is_active == True,
                    Attestation.assessment_type == "exam",
                    TraineeAttestation.status.in_(["assigned", "in_progress"]),
                )
            )

            if company_id is not None:
                query = query.where(User.company_id == company_id)

            query = query.order_by(TraineeAttestation.assigned_date.desc())

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Ошибка получения экзаменов для экзаменатора {examiner_id}: {e}")
            return []

    async def get_users_for_exam_assignment(
        self,
        company_id: int,
        filter_type: str = "all",
        filter_id: int = None,
        search_query: str = None,
    ) -> List[User]:
        """Получение пользователей для назначения экзамена с фильтрацией"""
        try:
            # Исключаем стажёров — по ТЗ им нельзя назначить экзамен
            # Но не исключаем ADMIN, даже если у него нет других ролей
            admin_user_ids = (
                select(user_roles.c.user_id).join(Role, user_roles.c.role_id == Role.id).where(Role.name == "ADMIN")
            )
            trainee_role_subquery = (
                select(user_roles.c.user_id)
                .join(Role, user_roles.c.role_id == Role.id)
                .where(Role.name.in_(["Стажер", "Стажёр"]))
                .where(user_roles.c.user_id.not_in(admin_user_ids))
            )

            query = (
                select(User)
                .options(
                    selectinload(User.roles),
                    selectinload(User.groups),
                    selectinload(User.work_object),
                    selectinload(User.internship_object),
                )
                .where(
                    User.is_active == True,
                    User.is_activated == True,
                    User.company_id == company_id,
                    User.id.not_in(trainee_role_subquery),
                )
            )

            if filter_type == "group" and filter_id is not None:
                query = query.join(user_groups, User.id == user_groups.c.user_id).where(
                    user_groups.c.group_id == filter_id
                )
            elif filter_type == "object" and filter_id is not None:
                query = query.where(or_(User.work_object_id == filter_id, User.internship_object_id == filter_id))
            elif filter_type == "search" and search_query:
                query = query.where(User.full_name.ilike(f"%{search_query}%"))

            query = query.order_by(User.full_name)
            result = await self.session.execute(query)
            return list(result.scalars().unique().all())

        except Exception as e:
            logger.error(f"Ошибка получения пользователей для экзамена: {e}")
            return []

    async def cleanup_duplicates(self, user_id: int) -> int:
        """Очистка дублирующих аттестаций для пользователя"""
        try:
            # Находим все активные аттестации пользователя
            attestations_result = await self.session.execute(
                select(TraineeAttestation)
                .where(TraineeAttestation.trainee_id == user_id)
                .where(TraineeAttestation.is_active == True)
                .order_by(TraineeAttestation.assigned_date.desc())
            )
            all_attestations = attestations_result.scalars().all()

            if len(all_attestations) <= 1:
                return 0  # Нет дубликатов

            # Группируем по attestation_id
            attestation_groups = {}
            for att in all_attestations:
                if att.attestation_id not in attestation_groups:
                    attestation_groups[att.attestation_id] = []
                attestation_groups[att.attestation_id].append(att)

            duplicates_removed = 0

            # Для каждой группы оставляем только самое новое назначение
            for attestation_id, group in attestation_groups.items():
                if len(group) > 1:
                    # Сортируем по дате назначения (самое новое первым)
                    group.sort(key=lambda x: x.assigned_date, reverse=True)

                    # Деактивируем все кроме самого нового
                    for old_assignment in group[1:]:
                        old_assignment.is_active = False
                        duplicates_removed += 1
                        logger.info(
                            f"Деактивировано дублирующее назначение аттестации {attestation_id} для стажера {user_id} (ID: {old_assignment.id})"
                        )

            if duplicates_removed > 0:
                await self.session.flush()
                logger.info(
                    f"Очищено {duplicates_removed} дублирующих назначений аттестации для пользователя {user_id}"
                )

            return duplicates_removed

        except Exception as e:
            logger.error(f"Ошибка очистки дублирующих аттестаций для пользователя {user_id}: {e}")
            return 0

    async def cleanup_all_duplicates(self, company_id: int = None) -> dict:
        """Глобальная очистка всех дублирующих аттестаций в системе (с изоляцией по компании)"""
        try:
            from bot.database.db import get_user_by_id

            cleanup_report = {
                "users_processed": 0,
                "duplicates_found": 0,
                "duplicates_removed": 0,
                "affected_users": [],
            }

            # Находим всех пользователей с активными аттестациями с изоляцией
            query = (
                select(TraineeAttestation.trainee_id)
                .join(User, TraineeAttestation.trainee_id == User.id)
                .join(Attestation, TraineeAttestation.attestation_id == Attestation.id)
                .where(TraineeAttestation.is_active == True)
                .distinct()
            )

            # Изоляция по компании - КРИТИЧЕСКИ ВАЖНО!
            if company_id is not None:
                query = query.where(User.company_id == company_id, Attestation.company_id == company_id)

            users_with_attestations_result = await self.session.execute(query)
            user_ids = [row[0] for row in users_with_attestations_result.all()]

            cleanup_report["users_processed"] = len(user_ids)

            # Очищаем дубликаты для каждого пользователя
            for user_id in user_ids:
                duplicates_removed = await self.cleanup_duplicates(user_id)
                if duplicates_removed > 0:
                    cleanup_report["duplicates_removed"] += duplicates_removed
                    cleanup_report["affected_users"].append(user_id)

                    # Получаем имя пользователя для отчета
                    user = await get_user_by_id(self.session, user_id)
                    if user:
                        logger.info(f"Очищены дубликаты аттестаций для пользователя {user.full_name} (ID: {user_id})")

            if cleanup_report["duplicates_removed"] > 0:
                await self.session.commit()
                logger.info(
                    f"Глобальная очистка завершена: обработано {cleanup_report['users_processed']} пользователей, удалено {cleanup_report['duplicates_removed']} дубликатов"
                )
            else:
                logger.info("Дублирующие аттестации не найдены")

            return cleanup_report

        except Exception as e:
            logger.error(f"Ошибка глобальной очистки дублирующих аттестаций: {e}")
            await self.session.rollback()
            return {"error": str(e)}
