from typing import List, Optional

from sqlalchemy import select

from bot.database.models import (
    Attestation,
    AttestationQuestionResult,
    AttestationResult,
    User,
)
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger


class AssessmentResultRepository(BaseRepository):
    async def create(
        self,
        trainee_id: int,
        attestation_id: int,
        manager_id: int,
        total_score: float,
        max_score: float,
        is_passed: bool,
        company_id: int = None,
    ) -> Optional[AttestationResult]:
        """Создание результата аттестации (с проверкой изоляции по компании)"""
        try:
            from bot.database.db import get_attestation_by_id, get_user_by_id

            # Проверяем изоляцию: trainee должен быть из той же компании
            if company_id is not None:
                trainee = await get_user_by_id(self.session, trainee_id)
                if not trainee or trainee.company_id != company_id:
                    logger.error(
                        f"Попытка создать результат аттестации для стажера из другой компании: trainee_id={trainee_id}, company_id={company_id}"
                    )
                    return None

                # Проверяем что attestation тоже из той же компании
                attestation = await get_attestation_by_id(self.session, attestation_id, company_id=company_id)
                if not attestation:
                    logger.error(f"Аттестация {attestation_id} не найдена или из другой компании")
                    return None

            result = AttestationResult(
                trainee_id=trainee_id,
                attestation_id=attestation_id,
                manager_id=manager_id,
                total_score=total_score,
                max_score=max_score,
                is_passed=is_passed,
            )

            self.session.add(result)
            await self.session.flush()

            logger.info(
                f"Создан результат аттестации для стажера {trainee_id}: {total_score}/{max_score}, пройдена: {is_passed}"
            )
            return result

        except Exception as e:
            logger.error(f"Ошибка создания результата аттестации: {e}")
            return None

    async def save_question_result(
        self, result_id: int, question_id: int, points_awarded: float, max_points: float
    ) -> bool:
        """Сохранение результата ответа на вопрос аттестации"""
        try:
            question_result = AttestationQuestionResult(
                attestation_result_id=result_id,
                question_id=question_id,
                points_awarded=points_awarded,
                max_points=max_points,
            )

            self.session.add(question_result)
            await self.session.flush()

            logger.info(f"Сохранен результат вопроса {question_id}: {points_awarded}/{max_points}")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения результата вопроса: {e}")
            return False

    async def get_for_trainee(self, trainee_id: int, company_id: int = None) -> List[AttestationResult]:
        """
        Получение результатов аттестаций стажера (с изоляцией по компании)
        """
        try:
            query = (
                select(AttestationResult)
                .join(User, AttestationResult.trainee_id == User.id)
                .where(AttestationResult.trainee_id == trainee_id, AttestationResult.is_active == True)
            )

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(User.company_id == company_id)

            query = query.order_by(AttestationResult.completed_date.desc())

            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка получения результатов аттестаций стажера {trainee_id}: {e}")
            return []

    async def get_specific(
        self, trainee_id: int, attestation_id: int, company_id: int = None
    ) -> Optional[AttestationResult]:
        """
        Получение результата конкретной аттестации для стажера с изоляцией по компании
        """
        try:
            query = (
                select(AttestationResult)
                .join(User, AttestationResult.trainee_id == User.id)
                .join(Attestation, AttestationResult.attestation_id == Attestation.id)
                .where(
                    AttestationResult.trainee_id == trainee_id,
                    AttestationResult.attestation_id == attestation_id,
                    AttestationResult.is_active == True,
                )
            )

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(User.company_id == company_id, Attestation.company_id == company_id)

            result = await self.session.execute(query.order_by(AttestationResult.completed_date.desc()))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка получения результата аттестации {attestation_id} для стажера {trainee_id}: {e}")
            return None

    async def get_pending_decisions(self, manager_id: int, company_id: int = None) -> List[AttestationResult]:
        """
        Получение ожидающих решения аттестаций для руководителя (с изоляцией компании)
        """
        try:
            query = (
                select(AttestationResult)
                .join(User, AttestationResult.manager_id == User.id)
                .where(
                    AttestationResult.manager_id == manager_id,
                    AttestationResult.manager_decision.is_(None),  # Решение еще не принято
                    AttestationResult.is_active == True,
                )
            )

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(User.company_id == company_id)

            result = await self.session.execute(query.order_by(AttestationResult.completed_date.desc()))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка получения ожидающих решений для руководителя {manager_id}: {e}")
            return []

    async def conduct(
        self,
        trainee_id: int,
        attestation_id: int,
        manager_id: int,
        scores: dict,
        company_id: int = None,
    ) -> Optional[AttestationResult]:
        """
        Проведение аттестации руководителем (с изоляцией по компании)
        scores - словарь {question_id: score}
        """
        try:
            # Получаем аттестацию с изоляцией
            query = select(Attestation).where(Attestation.id == attestation_id)

            # КРИТИЧЕСКАЯ ИЗОЛЯЦИЯ ПО КОМПАНИИ!
            if company_id is not None:
                query = query.where(Attestation.company_id == company_id)

            attestation_result = await self.session.execute(query)
            attestation = attestation_result.scalar_one_or_none()

            if not attestation:
                logger.error(f"Аттестация {attestation_id} не найдена")
                return None

            # Рассчитываем общий балл
            total_score = sum(scores.values())
            is_passed = total_score >= attestation.passing_score

            # Создаем результат аттестации (используем self.create для изоляции)
            result = await self.create(
                trainee_id,
                attestation_id,
                manager_id,
                total_score,
                attestation.max_score,
                is_passed,
                company_id=company_id,
            )

            if not result:
                return None

            logger.info(
                f"Аттестация проведена для стажера {trainee_id}, результат: {total_score}/{attestation.max_score}, пройдена: {is_passed}"
            )

            # НЕ автоматически переводим в сотрудники - решение принимает руководитель
            # await change_trainee_to_employee(session, trainee_id, result.id, company_id=company_id)

            return result

        except Exception as e:
            logger.error(f"Ошибка проведения аттестации: {e}")
            return None
