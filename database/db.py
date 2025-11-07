from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload, joinedload
from sqlalchemy import select, insert, delete, func, update, or_, and_, text
from typing import AsyncGenerator, Optional, List
import asyncio
from datetime import datetime

from config import DATABASE_URL
from database.models import (
    Base, Role, Permission, User, user_roles, role_permissions,
    Test, TestQuestion, TestResult, InternshipStage, Mentorship, TraineeTestAccess,
    Group, user_groups, Object, user_objects,
    LearningPath, LearningStage, LearningSession, session_tests,
    Attestation, AttestationQuestion,
    TraineeLearningPath, TraineeStageProgress, TraineeSessionProgress,
    AttestationResult, TraineeManager, TraineeAttestation, AttestationQuestionResult,
    KnowledgeFolder, KnowledgeMaterial, folder_group_access
)
from utils.logger import logger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=100,  # Увеличено для поддержки 500-1000 пользователей
    max_overflow=100,
    pool_timeout=30,
    pool_recycle=900,  # Исправлено: 15 минут вместо 1 часа для свежести подключений
    pool_pre_ping=True
)
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    

    await create_initial_data()

    await update_role_permissions_for_existing_db()
    await migrate_new_tables()
    await update_existing_users_role_date()
    # Только диагностика дубликатов, НЕ автоматическая очистка
    await cleanup_all_duplicate_attestations_on_startup()

async def create_initial_data():
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Role))
        count = result.scalar()
        if count == 0:
            roles = [
                Role(name="Рекрутер", description="Специалист по подбору и управлению персоналом"),
                Role(name="Наставник", description="Прокачанный сотрудник, который ведет стажеров"),
                Role(name="Стажер", description="Новый сотрудник на испытательном сроке"),
                Role(name="Сотрудник", description="Постоянный работник компании после прохождения аттестации"),
                Role(name="Руководитель", description="Руководитель для проведения аттестаций стажеров")
            ]
            session.add_all(roles)
            
            permissions = [
                Permission(name="view_profile", description="Просмотр собственного профиля"),
                Permission(name="edit_profile", description="Редактирование собственного профиля"),
                Permission(name="view_trainee_list", description="Просмотр списка Стажеров"),
                Permission(name="manage_trainees", description="Управление Стажерами"),
                Permission(name="manage_users", description="Управление пользователями"),
                Permission(name="manage_roles", description="Управление ролями"),
                Permission(name="conduct_attestations", description="Проведение аттестаций стажеров"),
                Permission(name="create_tests", description="Создание тестов"),
                Permission(name="edit_tests", description="Редактирование тестов"),
                Permission(name="take_tests", description="Прохождение тестов"),
                Permission(name="view_test_results", description="Просмотр результатов тестов"),
                Permission(name="assign_mentors", description="Назначение наставников"),
                Permission(name="view_mentorship", description="Просмотр информации о наставничестве"),
                Permission(name="grant_test_access", description="Предоставление доступа к тестам"),
                Permission(name="manage_groups", description="Управление группами пользователей"),
                Permission(name="manage_objects", description="Управление объектами"),
                Permission(name="view_knowledge_base", description="Просмотр базы знаний")
            ]
            session.add_all(permissions)
            
            await session.commit()
            
            roles_query = await session.execute(select(Role))
            roles = roles_query.scalars().all()
            
            permissions_query = await session.execute(select(Permission))
            permissions = permissions_query.scalars().all()
            

            for role in roles:
                if role.name != "Руководитель":
                    for perm in permissions:
                        if perm.name in ["view_profile", "edit_profile"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            # Рекрутер (1) - создает траектории, тесты, управляет пользователями
            for role in roles:
                if role.name == "Рекрутер":
                    for perm in permissions:
                        if perm.name in ["view_trainee_list", "manage_trainees", "assign_mentors", "view_mentorship", "create_tests", "edit_tests", "take_tests", "view_test_results", "manage_groups", "manage_objects"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            # Наставник (2) - ведет стажеров, открывает этапы, предоставляет доступ к тестам, проходит тесты от рекрутера
            for role in roles:
                if role.name == "Наставник":
                    for perm in permissions:
                        if perm.name in ["take_tests", "view_test_results", "grant_test_access", "view_mentorship", "view_knowledge_base"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            # Стажер (3) - проходит тесты, смотрит результаты, общается с наставником, просматривает базу знаний
            for role in roles:
                if role.name == "Стажер":
                    for perm in permissions:
                        if perm.name in ["take_tests", "view_test_results", "view_mentorship", "view_knowledge_base"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            # Сотрудник (4) - прошедший аттестацию стажер, может проходить назначенные тесты, просматривать базу знаний
            for role in roles:
                if role.name == "Сотрудник":
                    for perm in permissions:
                        if perm.name in ["take_tests", "view_test_results", "view_knowledge_base"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            # Руководитель (5) - проводит аттестации, может проходить тесты
            for role in roles:
                if role.name == "Руководитель":
                    for perm in permissions:
                        if perm.name in ["view_profile", "edit_profile", "conduct_attestations", "take_tests", "view_test_results", "view_knowledge_base"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            # Создание базовых этапов стажировки
            stages = [
                InternshipStage(name="Введение", description="Ознакомление с компанией", order_number=1),
                InternshipStage(name="Базовые навыки", description="Изучение основных процессов", order_number=2),
                InternshipStage(name="Практическое применение", description="Работа с реальными задачами", order_number=3),
                InternshipStage(name="Аттестация", description="Финальная проверка знаний", order_number=4)
            ]
            session.add_all(stages)
            
            await session.commit()
            logger.info("Начальные данные успешно созданы")


async def migrate_employee_to_mentor_roles():
    """Одноразовая миграция: создание роли 'Наставник' и настройка прав для 'Сотрудник'
    
    Миграция пользователей выполняется ТОЛЬКО при первом создании роли 'Наставник'.
    При последующих запуках только обновляются права доступа для роли 'Сотрудник'.
    """
    async with async_session() as session:
        try:
            logger.info("Начинаем миграцию ролей Сотрудник -> Наставник...")
            
            # Создаем роль "Наставник" если её нет
            mentor_role = await get_role_by_name(session, "Наставник")
            mentor_role_created = False
            
            if not mentor_role:
                logger.info("Создаем роль 'Наставник'...")
                mentor_role = Role(name="Наставник", description="Прокачанный сотрудник, который ведет стажеров")
                session.add(mentor_role)
                await session.flush()
                mentor_role_created = True
                
                # Назначаем права для роли "Наставник"
                permissions_query = await session.execute(select(Permission))
                permissions = permissions_query.scalars().all()
                
                for perm in permissions:
                    if perm.name in ["view_profile", "edit_profile", "view_test_results", "grant_test_access", "view_mentorship"]:
                        stmt = insert(role_permissions).values(
                            role_id=mentor_role.id,
                            permission_id=perm.id
                        )
                        await session.execute(stmt)
                
                logger.info("Создана роль 'Наставник' с правами доступа")
            else:
                logger.info("Роль 'Наставник' уже существует, пропускаем миграцию пользователей")
            
            # Миграция пользователей только если роль была только что создана
            # Это предотвращает повторное выполнение миграции при каждом запуске
            if mentor_role_created:
                logger.info("Выполняем одноразовую миграцию пользователей Сотрудник -> Наставник...")
                
                # Получаем роль "Сотрудник"
                employee_role = await get_role_by_name(session, "Сотрудник")
                if employee_role:
                    # Получаем всех пользователей с ролью "Сотрудник"
                    users_with_employee_role = await session.execute(
                        select(User)
                        .join(user_roles, User.id == user_roles.c.user_id)
                        .where(user_roles.c.role_id == employee_role.id)
                    )
                    users = users_with_employee_role.scalars().all()
                    
                    # Переводим пользователей с роли "Сотрудник" на "Наставник"
                    for user in users:
                        # Удаляем связь с ролью "Сотрудник"
                        await session.execute(
                            delete(user_roles)
                            .where(user_roles.c.user_id == user.id)
                            .where(user_roles.c.role_id == employee_role.id)
                        )
                        
                        # Добавляем связь с ролью "Наставник"
                        await session.execute(
                            insert(user_roles)
                            .values(user_id=user.id, role_id=mentor_role.id)
                        )
                        
                        logger.info(f"Пользователь {user.full_name} (ID: {user.id}) переведен с роли 'Сотрудник' на 'Наставник'")
                
                logger.info("Одноразовая миграция пользователей завершена")
            
            # Обновляем права роли "Сотрудник" (это безопасно делать каждый раз)
            employee_role = await get_role_by_name(session, "Сотрудник")
            if employee_role:
                
                # Обновляем права роли "Сотрудник" для новой функции (прошедшие аттестацию стажеры)
                # Удаляем старые права
                await session.execute(
                    delete(role_permissions).where(role_permissions.c.role_id == employee_role.id)
                )
                
                # Назначаем новые права для роли "Сотрудник"
                permissions_query = await session.execute(select(Permission))
                permissions = permissions_query.scalars().all()
                
                for perm in permissions:
                    if perm.name in ["view_profile", "edit_profile", "take_tests", "view_test_results"]:
                        stmt = insert(role_permissions).values(
                            role_id=employee_role.id,
                            permission_id=perm.id
                        )
                        await session.execute(stmt)
                
                logger.info("Обновлены права роли 'Сотрудник' для прошедших аттестацию стажеров")
            
            await session.commit()
            logger.info("Миграция ролей завершена успешно")
            
        except Exception as e:
            logger.error(f"Ошибка миграции ролей: {e}")
            await session.rollback()


async def update_existing_users_role_date():
    """Обновление даты назначения роли для существующих пользователей"""
    async with async_session() as session:
        try:
            # Обновляем пользователей, у которых role_assigned_date равен NULL
            result = await session.execute(
                update(User)
                .where(User.role_assigned_date.is_(None))
                .values(role_assigned_date=User.registration_date)
            )
            updated_count = result.rowcount
            if updated_count > 0:
                await session.commit()
                logger.info(f"Обновлена дата назначения роли для {updated_count} пользователей")
        except Exception as e:
            logger.error(f"Ошибка обновления даты назначения роли: {e}")
            await session.rollback()


async def update_role_permissions_for_existing_db():
    """Обновление прав ролей для существующих баз данных"""
    async with async_session() as session:
        try:
            logger.info("Обновление прав доступа для ролей...")
            
            # Получаем роль Сотрудник
            employee_role = await get_role_by_name(session, "Сотрудник")
            if employee_role:
                # Удаляем права create_tests и edit_tests у Сотрудника
                await remove_permission_from_role(session, employee_role.id, "create_tests")
                await remove_permission_from_role(session, employee_role.id, "edit_tests")
                logger.info("Удалены права create_tests и edit_tests у роли Сотрудник")
            
            logger.info("Обновление прав доступа завершено")
        except Exception as e:
            logger.error(f"Ошибка обновления прав доступа: {e}")


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> Optional[User]:
    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы
                selectinload(User.internship_object),  # Загружаем объект стажировки
                selectinload(User.roles),  # Загружаем роли пользователя
                selectinload(User.groups)  # Загружаем группы пользователя
            )
            .where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения пользователя по tg_id {tg_id}: {e}")
        return None


async def check_phone_exists(session: AsyncSession, phone_number: str) -> bool:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.phone_number == phone_number)
    )
    count = result.scalar()
    return count > 0


async def get_user_by_phone(session: AsyncSession, phone_number: str) -> Optional[User]:
    """Получение пользователя по номеру телефона с загрузкой связанных объектов"""
    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы
                selectinload(User.internship_object),  # Загружаем объект стажировки
                selectinload(User.roles),  # Загружаем роли пользователя
                selectinload(User.groups)  # Загружаем группы пользователя
            )
            .where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения пользователя по телефону {phone_number}: {e}")
        return None


async def create_user(session: AsyncSession, user_data: dict, role_name: str, bot=None) -> User:
    try:
        user = User(
            tg_id=user_data['tg_id'],
            username=user_data.get('username'),
            full_name=user_data['full_name'],
            phone_number=user_data['phone_number']
        )
        session.add(user)
        await session.flush()
        
        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one()

        stmt = insert(user_roles).values(
            user_id=user.id,
            role_id=role.id
        )
        await session.execute(stmt)
        
        await session.commit()
        
        # Отправляем уведомления рекрутерам если создан новый стажёр
        if role_name == "Стажер" and bot:
            await send_notification_about_new_trainee_registration(session, bot, user.id)
        
        return user
    except Exception as e:
        logger.error(f"Ошибка создания пользователя: {e}")
        await session.rollback()
        raise


async def create_user_without_role(session: AsyncSession, user_data: dict, bot=None) -> User:
    """Создание пользователя без роли (для последующей активации рекрутером)"""
    try:
        user = User(
            tg_id=user_data['tg_id'],
            username=user_data.get('username'),
            full_name=user_data['full_name'],
            phone_number=user_data['phone_number'],
            is_activated=False  # Пользователь неактивирован до обработки рекрутером
        )
        session.add(user)
        await session.flush()
        await session.commit()
        
        # Отправляем уведомления рекрутерам о новом пользователе
        if bot:
            await send_notification_about_new_user_registration(session, bot, user.id)
        
        logger.info(f"Пользователь {user.id} создан без роли для последующей активации")
        return user
    except Exception as e:
        logger.error(f"Ошибка создания пользователя без роли: {e}")
        await session.rollback()
        raise


async def check_user_permission(session: AsyncSession, user_id: int, permission_name: str) -> bool:
    stmt = select(func.count()).select_from(User).join(
        user_roles, User.id == user_roles.c.user_id
    ).join(
        role_permissions, user_roles.c.role_id == role_permissions.c.role_id
    ).join(
        Permission, role_permissions.c.permission_id == Permission.id
    ).where(
        User.id == user_id,
        Permission.name == permission_name
    )
    
    result = await session.execute(stmt)
    count = result.scalar()
    return count > 0


async def get_user_roles(session: AsyncSession, user_id: int) -> List[Role]:
    try:
        stmt = select(Role).join(
            user_roles, Role.id == user_roles.c.role_id
        ).where(
            user_roles.c.user_id == user_id
        )
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения ролей для пользователя {user_id}: {e}")
        return []


async def add_user_role(session: AsyncSession, user_id: int, role_name: str) -> bool:
    try:
        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one_or_none()
        
        if not role:
            return False
        
        check_stmt = select(func.count()).select_from(user_roles).where(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role.id
        )
        check_result = await session.execute(check_stmt)
        
        has_role = check_result.scalar()
        if has_role > 0:
            return True
        
        stmt = insert(user_roles).values(
            user_id=user_id,
            role_id=role.id
        )
        await session.execute(stmt)
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления роли пользователю {user_id}: {e}")
        await session.rollback()
        return False


async def remove_user_role(session: AsyncSession, user_id: int, role_name: str) -> bool:
    try:
        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one_or_none()
        
        if not role:
            return False
        
        stmt = delete(user_roles).where(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role.id
        )
        await session.execute(stmt)
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления роли у пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def get_all_users(session: AsyncSession) -> List[User]:
    """ Получение списка всех пользователей"""

    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            )
            .order_by(User.registration_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех пользователей: {e}")
        return []


async def get_all_trainees(session: AsyncSession) -> List[User]:
    """Получение списка всех активированных стажеров"""

    try:
        stmt = select(User).join(
            user_roles, User.id == user_roles.c.user_id
        ).join(
            Role, user_roles.c.role_id == Role.id
        ).where(
            Role.name == "Стажер",
            User.is_activated == True  # Только активированные стажеры
        ).order_by(User.registration_date.desc())
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех стажёров: {e}")
        return []


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """Получение пользователя по его ID с загрузкой связанных объектов"""

    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы
                selectinload(User.internship_object),  # Загружаем объект стажировки
                selectinload(User.roles),  # Загружаем роли пользователя
                selectinload(User.groups)  # Загружаем группы пользователя
            )
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения пользователя по ID {user_id}: {e}")
        return None


async def update_user_profile(session: AsyncSession, user_id: int, update_data: dict) -> bool:
    """Обновление профиля пользователя"""

    try:
        stmt = update(User).where(User.id == user_id)
        
        valid_fields = ['full_name', 'phone_number', 'username', 'is_active']
        update_values = {k: v for k, v in update_data.items() if k in valid_fields}
        
        if not update_values:
            return False
        
        stmt = stmt.values(**update_values)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления профиля пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def get_users_by_role(session: AsyncSession, role_name: str) -> List[User]:
    """Получение всех пользователей с указанной ролью """
    try:
        stmt = select(User).join(
            user_roles, User.id == user_roles.c.user_id
        ).join(
            Role, user_roles.c.role_id == Role.id
        ).where(
            Role.name == role_name
        ).order_by(User.full_name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения пользователей с ролью {role_name}: {e}")
        return []

# ========== ФУНКЦИИ ДЛЯ АКТИВАЦИИ ПОЛЬЗОВАТЕЛЕЙ ==========

async def get_unactivated_users(session: AsyncSession) -> List[User]:
    """Получение списка неактивированных пользователей (исключая администраторов)"""
    try:
        # Исключаем пользователей с ролями Руководитель и Рекрутер,
        # так как они автоматически активируются
        result = await session.execute(
            select(User)
            .where(User.is_activated == False)
            .where(~User.roles.any(Role.name.in_(["Руководитель", "Рекрутер"])))
            .order_by(User.registration_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения неактивированных пользователей: {e}")
        return []


async def activate_user(session: AsyncSession, user_id: int, role_name: str, 
                       group_id: int, internship_object_id: int, 
                       work_object_id: int, bot=None) -> bool:
    """Активация пользователя с назначением роли, группы и объектов"""
    try:
        # Получаем пользователя
        user = await get_user_by_id(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
        
        # Назначаем роль
        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one_or_none()
        if not role:
            logger.error(f"Роль {role_name} не найдена")
            return False
        
        # Добавляем роль пользователю
        stmt = insert(user_roles).values(user_id=user.id, role_id=role.id)
        await session.execute(stmt)
        
        # Добавляем в группу
        stmt = insert(user_groups).values(user_id=user.id, group_id=group_id)
        await session.execute(stmt)
        
        # Обновляем объекты и статус активации
        from datetime import datetime
        update_stmt = update(User).where(User.id == user_id).values(
            is_activated=True,
            internship_object_id=internship_object_id,
            work_object_id=work_object_id,
            role_assigned_date=datetime.now()
        )
        await session.execute(update_stmt)
        
        await session.commit()
        
        # Отправляем уведомление пользователю
        if bot:
            await send_notification_about_activation(session, bot, user_id, role_name, 
                                                   group_id, internship_object_id, work_object_id)
        
        logger.info(f"Пользователь {user_id} успешно активирован")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка активации пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def get_user_with_details(session: AsyncSession, user_id: int) -> Optional[User]:
    """Получение пользователя с загрузкой всех связанных данных"""
    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            )
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения пользователя с деталями {user_id}: {e}")
        return None


async def get_all_roles(session: AsyncSession) -> List[Role]:
    """Получение списка всех ролей"""

    try:
        result = await session.execute(select(Role).order_by(Role.name))
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех ролей: {e}")
        return []


async def get_all_permissions(session: AsyncSession) -> List[Permission]:
    """Получение списка всех прав доступа """

    try:
        result = await session.execute(select(Permission).order_by(Permission.name))
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех прав: {e}")
        return []

async def get_role_permissions(session: AsyncSession, role_id: int) -> List[Permission]:
    """Получение всех прав для указанной роли"""

    try:
        stmt = select(Permission).join(
            role_permissions, Permission.id == role_permissions.c.permission_id
        ).where(
            role_permissions.c.role_id == role_id
        ).order_by(Permission.name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения прав для роли {role_id}: {e}")
        return []

async def add_permission_to_role(session: AsyncSession, role_id: int, permission_name: str) -> bool:
    """Добавление права роли"""

    try:
        perm_result = await session.execute(
            select(Permission).where(Permission.name == permission_name)
        )
        permission = perm_result.scalar_one_or_none()
        
        if not permission:
            logger.error(f"Право {permission_name} не найдено")
            return False
        
        check_stmt = select(func.count()).select_from(role_permissions).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission.id
        )
        check_result = await session.execute(check_stmt)
        
        has_permission = check_result.scalar()
        if has_permission > 0:
            logger.info(f"Роль {role_id} уже имеет право {permission_name}")
            return True
        
        stmt = insert(role_permissions).values(
            role_id=role_id,
            permission_id=permission.id
        )
        await session.execute(stmt)
        
        await session.commit()
        logger.info(f"Право {permission_name} добавлено роли {role_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления права {permission_name} к роли {role_id}: {e}")
        await session.rollback()
        return False

async def remove_permission_from_role(session: AsyncSession, role_id: int, permission_name: str) -> bool:
    """Удаление права у роли"""

    try:
        perm_result = await session.execute(
            select(Permission).where(Permission.name == permission_name)
        )
        permission = perm_result.scalar_one_or_none()
        
        if not permission:
            logger.error(f"Право {permission_name} не найдено")
            return False
        
        stmt = delete(role_permissions).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission.id
        )
        await session.execute(stmt)
        
        await session.commit()
        logger.info(f"Право {permission_name} удалено у роли {role_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления права {permission_name} у роли {role_id}: {e}")
        await session.rollback()
        return False

async def create_new_permission(session: AsyncSession, name: str, description: str) -> Optional[Permission]:
    """Создание нового права доступа"""
    try:
        check_stmt = select(func.count()).select_from(Permission).where(Permission.name == name)
        check_result = await session.execute(check_stmt)
        
        exists = check_result.scalar()
        if exists > 0:
            logger.error(f"Право с именем {name} уже существует")
            return None
        
        permission = Permission(
            name=name,
            description=description
        )
        session.add(permission)
        await session.commit()
        
        logger.info(f"Создано новое право: {name}")
        return permission
    except Exception as e:
        logger.error(f"Ошибка создания нового права {name}: {e}")
        await session.rollback()
        return None

async def get_role_by_name(session: AsyncSession, role_name: str) -> Optional[Role]:
    """Получение роли по имени"""

    try:
        result = await session.execute(select(Role).where(Role.name == role_name))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения роли по имени {role_name}: {e}")
        return None

async def get_permission_by_name(session: AsyncSession, permission_name: str) -> Optional[Permission]:
    """Получение права по имени"""

    try:
        result = await session.execute(select(Permission).where(Permission.name == permission_name))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения права по имени {permission_name}: {e}")
        return None


# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ГРУППАМИ
# =================================

async def create_group(session: AsyncSession, name: str, created_by_id: int) -> Optional[Group]:
    """Создание новой группы"""
    try:
        # Проверяем, не существует ли группа с таким именем
        check_stmt = select(func.count()).select_from(Group).where(Group.name == name)
        check_result = await session.execute(check_stmt)
        
        exists = check_result.scalar()
        if exists > 0:
            logger.error(f"Группа с именем {name} уже существует")
            return None
        
        group = Group(
            name=name,
            created_by_id=created_by_id
        )
        session.add(group)
        await session.commit()
        
        logger.info(f"Создана новая группа: {name}")
        return group
    except Exception as e:
        logger.error(f"Ошибка создания группы {name}: {e}")
        await session.rollback()
        return None


async def get_all_groups(session: AsyncSession) -> List[Group]:
    """Получение всех активных групп"""
    try:
        result = await session.execute(
            select(Group)
            .options(
                selectinload(Group.users).selectinload(User.roles)
            )
            .where(Group.is_active == True)
            .order_by(Group.name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех групп: {e}")
        return []


async def get_group_by_id(session: AsyncSession, group_id: int) -> Optional[Group]:
    """Получение группы по ID"""
    try:
        result = await session.execute(select(Group).where(Group.id == group_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения группы по ID {group_id}: {e}")
        return None


async def get_group_by_name(session: AsyncSession, name: str) -> Optional[Group]:
    """Получение группы по имени"""
    try:
        result = await session.execute(select(Group).where(Group.name == name))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения группы по имени {name}: {e}")
        return None


async def update_group_name(session: AsyncSession, group_id: int, new_name: str) -> bool:
    """Изменение названия группы"""
    try:
        # Проверяем, не существует ли группа с новым именем
        check_stmt = select(func.count()).select_from(Group).where(
            Group.name == new_name,
            Group.id != group_id
        )
        check_result = await session.execute(check_stmt)
        
        exists = check_result.scalar()
        if exists > 0:
            logger.error(f"Группа с именем {new_name} уже существует")
            return False
        
        stmt = update(Group).where(Group.id == group_id).values(name=new_name)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Название группы {group_id} изменено на {new_name}")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения названия группы {group_id}: {e}")
        await session.rollback()
        return False


async def delete_group(session: AsyncSession, group_id: int, deleted_by_id: int) -> bool:
    """Физическое удаление группы"""
    try:
        # Проверяем существование группы
        group = await get_group_by_id(session, group_id)
        if not group:
            logger.error(f"Группа {group_id} не найдена")
            return False
        
        # Проверяем, есть ли пользователи в группе
        users_in_group = await get_group_users(session, group_id)
        if users_in_group:
            logger.warning(f"Нельзя удалить группу {group_id}: в ней есть пользователи ({len(users_in_group)} чел.)")
            return False
        
        # Проверяем, используется ли группа в траекториях
        learning_paths = await get_learning_paths_by_group(session, group_id)
        if learning_paths:
            logger.warning(f"Нельзя удалить группу {group_id}: она используется в траекториях ({len(learning_paths)} шт.)")
            return False
        
        # Проверяем, используется ли группа в базе знаний
        folders_result = await session.execute(
            select(KnowledgeFolder).join(
                folder_group_access, KnowledgeFolder.id == folder_group_access.c.folder_id
            ).where(
                folder_group_access.c.group_id == group_id,
                KnowledgeFolder.is_active == True
            )
        )
        folders = folders_result.scalars().all()
        if folders:
            logger.warning(f"Нельзя удалить группу {group_id}: она используется в базе знаний ({len(folders)} папок)")
            return False
        
        # Удаляем связи пользователей с группой
        await session.execute(
            delete(user_groups).where(user_groups.c.group_id == group_id)
        )
        
        # Удаляем связи группы с папками базы знаний
        await session.execute(
            delete(folder_group_access).where(folder_group_access.c.group_id == group_id)
        )
        
        # Физическое удаление группы
        await session.execute(
            delete(Group).where(Group.id == group_id)
        )
        await session.commit()
        
        logger.info(f"Группа {group_id} '{group.name}' физически удалена пользователем {deleted_by_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка удаления группы {group_id}: {e}")
        await session.rollback()
        return False


async def get_group_users(session: AsyncSession, group_id: int) -> List[User]:
    """Получение всех пользователей группы"""
    try:
        stmt = select(User).join(
            user_groups, User.id == user_groups.c.user_id
        ).where(
            user_groups.c.group_id == group_id
        ).order_by(User.full_name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения пользователей группы {group_id}: {e}")
        return []


async def get_all_users_in_group(session: AsyncSession, group_id: int) -> List[User]:
    """Получение ВСЕХ пользователей из группы (включая все роли) для рассылки"""
    try:
        stmt = select(User).join(
            user_groups, User.id == user_groups.c.user_id
        ).where(
            user_groups.c.group_id == group_id,
            User.is_activated == True,
            User.is_active == True
        ).options(
            joinedload(User.roles)  # Загружаем роли заранее для фильтрации
        ).order_by(User.full_name)
        
        result = await session.execute(stmt)
        return result.scalars().unique().all()
        
    except Exception as e:
        logger.error(f"Ошибка получения пользователей из группы {group_id}: {e}")
        return []


async def get_employees_in_group(session: AsyncSession, group_id: int) -> List[User]:
    """Получение только сотрудников из группы (для массовой рассылки Task 8)"""
    try:
        # Получаем роль сотрудника
        employee_role = await get_role_by_name(session, "Сотрудник")
        if not employee_role:
            return []
        
        stmt = select(User).join(
            user_groups, User.id == user_groups.c.user_id
        ).join(
            user_roles, User.id == user_roles.c.user_id
        ).where(
            user_groups.c.group_id == group_id,
            user_roles.c.role_id == employee_role.id,
            User.is_activated == True,
            User.is_active == True
        ).order_by(User.full_name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения сотрудников группы {group_id}: {e}")
        return []


async def get_trainees_in_group(session: AsyncSession, group_id: int) -> List[User]:
    """Получение только стажеров из группы (для массовой рассылки)"""
    try:
        # Получаем роль стажера
        trainee_role = await get_role_by_name(session, "Стажер")
        if not trainee_role:
            return []
        
        stmt = select(User).join(
            user_groups, User.id == user_groups.c.user_id
        ).join(
            user_roles, User.id == user_roles.c.user_id
        ).where(
            user_groups.c.group_id == group_id,
            user_roles.c.role_id == trainee_role.id,
            User.is_activated == True,
            User.is_active == True
        ).order_by(User.full_name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting trainees in group {group_id}: {e}")
        return []

async def get_mentors_in_group(session: AsyncSession, group_id: int) -> List[User]:
    """Получение только наставников из группы (для массовой рассылки)"""
    try:
        # Получаем роль наставника
        mentor_role = await get_role_by_name(session, "Наставник")
        if not mentor_role:
            return []
        
        stmt = select(User).join(
            user_groups, User.id == user_groups.c.user_id
        ).join(
            user_roles, User.id == user_roles.c.user_id
        ).where(
            user_groups.c.group_id == group_id,
            user_roles.c.role_id == mentor_role.id,
            User.is_activated == True,
            User.is_active == True
        ).order_by(User.full_name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения стажеров группы {group_id}: {e}")
        return []


async def get_user_groups(session: AsyncSession, user_id: int) -> List[Group]:
    """Получение всех групп пользователя"""
    try:
        stmt = select(Group).join(
            user_groups, Group.id == user_groups.c.group_id
        ).where(
            user_groups.c.user_id == user_id,
            Group.is_active == True
        ).order_by(Group.name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения групп пользователя {user_id}: {e}")
        return []


async def add_user_to_group(session: AsyncSession, user_id: int, group_id: int) -> bool:
    """Добавление пользователя в группу"""
    try:
        # Проверяем, не состоит ли пользователь уже в группе
        check_stmt = select(func.count()).select_from(user_groups).where(
            user_groups.c.user_id == user_id,
            user_groups.c.group_id == group_id
        )
        check_result = await session.execute(check_stmt)
        
        is_member = check_result.scalar()
        if is_member > 0:
            logger.info(f"Пользователь {user_id} уже состоит в группе {group_id}")
            return True
        
        stmt = insert(user_groups).values(
            user_id=user_id,
            group_id=group_id
        )
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Пользователь {user_id} добавлен в группу {group_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления пользователя {user_id} в группу {group_id}: {e}")
        await session.rollback()
        return False


async def remove_user_from_group(session: AsyncSession, user_id: int, group_id: int) -> bool:
    """Удаление пользователя из группы"""
    try:
        stmt = delete(user_groups).where(
            user_groups.c.user_id == user_id,
            user_groups.c.group_id == group_id
        )
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Пользователь {user_id} удален из группы {group_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {user_id} из группы {group_id}: {e}")
        await session.rollback()
        return False


# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ОБЪЕКТАМИ
# =================================

async def create_object(session: AsyncSession, name: str, created_by_id: int) -> Optional[Object]:
    """Создание нового объекта"""
    try:
        # Проверяем, не существует ли уже объект с таким названием
        existing_object = await get_object_by_name(session, name)
        if existing_object:
            logger.warning(f"Объект с названием '{name}' уже существует")
            return None
        
        new_object = Object(
            name=name.strip(),
            created_by_id=created_by_id
        )
        
        session.add(new_object)
        await session.commit()
        await session.refresh(new_object)
        
        logger.info(f"Объект '{name}' создан пользователем {created_by_id}")
        return new_object
    except Exception as e:
        logger.error(f"Ошибка создания объекта '{name}': {e}")
        await session.rollback()
        return None

async def get_all_objects(session: AsyncSession) -> List[Object]:
    """Получение всех объектов"""
    try:
        result = await session.execute(
            select(Object)
            .options(
                selectinload(Object.users).selectinload(User.roles)
            )
            .where(Object.is_active == True)
            .order_by(Object.name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения объектов: {e}")
        return []

async def get_object_by_id(session: AsyncSession, object_id: int) -> Optional[Object]:
    """Получение объекта по ID"""
    try:
        result = await session.execute(
            select(Object).where(Object.id == object_id, Object.is_active == True)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения объекта {object_id}: {e}")
        return None

async def get_object_by_name(session: AsyncSession, name: str) -> Optional[Object]:
    """Получение объекта по названию"""
    try:
        result = await session.execute(
            select(Object).where(Object.name == name.strip(), Object.is_active == True)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения объекта по названию '{name}': {e}")
        return None

async def update_object_name(session: AsyncSession, object_id: int, new_name: str) -> bool:
    """Обновление названия объекта"""
    try:
        # Проверяем, не существует ли уже объект с новым названием
        existing_object = await get_object_by_name(session, new_name)
        if existing_object and existing_object.id != object_id:
            logger.warning(f"Объект с названием '{new_name}' уже существует")
            return False
        
        stmt = update(Object).where(Object.id == object_id).values(name=new_name.strip())
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Название объекта {object_id} изменено на '{new_name}'")
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления названия объекта {object_id}: {e}")
        await session.rollback()
        return False

async def get_object_users(session: AsyncSession, object_id: int) -> List[User]:
    """Получение всех пользователей объекта (включая объект стажировки и работы)"""
    try:
        # Получаем пользователей через таблицу user_objects
        result1 = await session.execute(
            select(User).join(user_objects).where(
                user_objects.c.object_id == object_id,
                User.is_activated == True
            ).options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            ).order_by(User.full_name)
        )
        users_by_objects = result1.scalars().all()
        
        # Получаем пользователей, у которых этот объект указан как объект стажировки или работы
        result2 = await session.execute(
            select(User).where(
                or_(
                    User.internship_object_id == object_id,
                    User.work_object_id == object_id
                ),
                User.is_activated == True
            ).options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            ).order_by(User.full_name)
        )
        users_by_direct = result2.scalars().all()
        
        # Объединяем и убираем дубликаты
        all_users = {}
        for user in users_by_objects + users_by_direct:
            all_users[user.id] = user
            
        # Сортируем по ФИО
        sorted_users = sorted(all_users.values(), key=lambda u: u.full_name)
        
        logger.info(f"Получено {len(sorted_users)} пользователей для объекта {object_id}")
        return sorted_users
        
    except Exception as e:
        logger.error(f"Ошибка получения пользователей объекта {object_id}: {e}")
        return []

async def add_user_to_object(session: AsyncSession, user_id: int, object_id: int) -> bool:
    """Добавление пользователя в объект"""
    try:
        # Проверяем, не состоит ли уже пользователь в этом объекте
        result = await session.execute(
            select(user_objects).where(
                user_objects.c.user_id == user_id,
                user_objects.c.object_id == object_id
            )
        )
        if result.scalar_one_or_none():
            logger.info(f"Пользователь {user_id} уже состоит в объекте {object_id}")
            return True
        
        stmt = insert(user_objects).values(user_id=user_id, object_id=object_id)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Пользователь {user_id} добавлен в объект {object_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления пользователя {user_id} в объект {object_id}: {e}")
        await session.rollback()
        return False

async def remove_user_from_object(session: AsyncSession, user_id: int, object_id: int) -> bool:
    """Удаление пользователя из объекта"""
    try:
        stmt = delete(user_objects).where(
            user_objects.c.user_id == user_id,
            user_objects.c.object_id == object_id
        )
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Пользователь {user_id} удален из объекта {object_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {user_id} из объекта {object_id}: {e}")
        await session.rollback()
        return False


async def delete_object(session: AsyncSession, object_id: int, deleted_by_id: int) -> bool:
    """Физическое удаление объекта"""
    try:
        # Проверяем существование объекта
        object_obj = await get_object_by_id(session, object_id)
        if not object_obj:
            logger.error(f"Объект {object_id} не найден")
            return False
        
        # Проверяем, есть ли пользователи в объекте (включая user_objects, internship_object_id, work_object_id)
        users_in_object = await get_object_users(session, object_id)
        if users_in_object:
            logger.warning(f"Нельзя удалить объект {object_id}: в нем есть пользователи ({len(users_in_object)} чел.)")
            return False
        
        # Удаляем связи пользователей с объектом
        await session.execute(
            delete(user_objects).where(user_objects.c.object_id == object_id)
        )
        
        # Физическое удаление объекта
        await session.execute(
            delete(Object).where(Object.id == object_id)
        )
        await session.commit()
        
        logger.info(f"Объект {object_id} '{object_obj.name}' физически удален пользователем {deleted_by_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка удаления объекта {object_id}: {e}")
        await session.rollback()
        return False


# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ТЕСТАМИ
# =================================

async def create_test(session: AsyncSession, test_data: dict) -> Optional[Test]:
    """Создание нового теста с валидацией"""
    try:
        # Валидация обязательных полей
        if not test_data.get('name') or len(test_data['name'].strip()) < 3:
            logger.error("Название теста должно содержать не менее 3 символов")
            return None
        
        if not test_data.get('creator_id'):
            logger.error("Не указан создатель теста")
            return None
        
        # Проверка существования создателя
        creator_exists = await session.execute(
            select(User).where(User.id == test_data['creator_id'])
        )
        if not creator_exists.scalar_one_or_none():
            logger.error(f"Создатель с ID {test_data['creator_id']} не найден")
            return None
        
        # Валидация материалов (если указана ссылка)
        material_link = test_data.get('material_link')
        if material_link and not (material_link.startswith('http://') or material_link.startswith('https://')):
            logger.warning(f"Ссылка на материалы не содержит протокол: {material_link}")
        
        test = Test(
            name=test_data['name'].strip(),
            description=test_data.get('description', '').strip() if test_data.get('description') else None,
            threshold_score=max(1, test_data.get('threshold_score', 1)),
            max_score=max(0, test_data.get('max_score', 0)),
            material_link=material_link,
            material_file_path=test_data.get('material_file_path'),
            material_type=test_data.get('material_type'),
            stage_id=test_data.get('stage_id'),
            creator_id=test_data['creator_id']
        )
        session.add(test)
        await session.flush()
        await session.commit()
        logger.info(f"Тест '{test.name}' создан успешно (ID: {test.id})")
        return test
    except Exception as e:
        logger.error(f"Ошибка создания теста: {e}")
        await session.rollback()
        return None

async def get_test_by_id(session: AsyncSession, test_id: int) -> Optional[Test]:
    """Получение теста по ID с загрузкой связанных вопросов"""
    try:
        result = await session.execute(
            select(Test)
            .options(selectinload(Test.questions))
            .where(Test.id == test_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения теста {test_id}: {e}")
        return None

async def get_tests_by_creator(session: AsyncSession, creator_id: int) -> List[Test]:
    """Получение всех тестов, созданных пользователем"""
    try:
        result = await session.execute(
            select(Test).where(Test.creator_id == creator_id, Test.is_active == True)
            .order_by(Test.created_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения тестов пользователя {creator_id}: {e}")
        return []

async def get_all_active_tests(session: AsyncSession) -> List[Test]:
    """Получение всех активных тестов"""
    try:
        result = await session.execute(
            select(Test).where(Test.is_active == True)
            .order_by(Test.created_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех тестов: {e}")
        return []

async def update_test(session: AsyncSession, test_id: int, update_data: dict) -> bool:
    """Обновление теста"""
    try:
        valid_fields = ['name', 'description', 'threshold_score', 'max_score', 
                       'material_link', 'material_file_path', 'material_type', 
                       'stage_id', 'shuffle_questions', 'max_attempts']
        update_values = {k: v for k, v in update_data.items() if k in valid_fields}
        
        if not update_values:
            return False
        
        stmt = update(Test).where(Test.id == test_id).values(**update_values)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления теста {test_id}: {e}")
        await session.rollback()
        return False

async def delete_test(session: AsyncSession, test_id: int) -> bool:
    """Удаление теста (мягкое удаление)"""
    try:
        stmt = update(Test).where(Test.id == test_id).values(is_active=False)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления теста {test_id}: {e}")
        await session.rollback()
        return False

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ВОПРОСАМИ
# =================================

async def add_question_to_test(session: AsyncSession, question_data: dict) -> Optional[TestQuestion]:
    """Добавление вопроса к тесту с проверкой на уникальность"""
    try:
        # Проверка на уникальность текста вопроса в рамках теста
        existing_question = await session.execute(
            select(TestQuestion).where(
                TestQuestion.test_id == question_data['test_id'],
                TestQuestion.question_text == question_data['question_text']
            )
        )
        if existing_question.scalar_one_or_none():
            logger.warning(f"Попытка добавить дублирующийся вопрос в тест {question_data['test_id']}")
            return None # или можно вернуть ошибку

        question = TestQuestion(
            test_id=question_data['test_id'],
            question_number=question_data['question_number'],
            question_type=question_data['question_type'],
            question_text=question_data['question_text'],
            options=question_data.get('options'),
            correct_answer=json.dumps(question_data['correct_answer']) if isinstance(question_data['correct_answer'], list) else question_data['correct_answer'],
            points=question_data.get('points', 1),
            penalty_points=question_data.get('penalty_points', 0)
        )
        session.add(question)
        await session.flush()
        
        # Обновляем максимальный балл теста
        await update_test_max_score(session, question_data['test_id'])
        
        await session.commit()
        return question
    except Exception as e:
        logger.error(f"Ошибка добавления вопроса: {e}")
        await session.rollback()
        return None

async def get_test_questions(session: AsyncSession, test_id: int) -> List[TestQuestion]:
    """Получение всех вопросов теста"""
    try:
        result = await session.execute(
            select(TestQuestion).where(TestQuestion.test_id == test_id)
            .order_by(TestQuestion.question_number)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения вопросов теста {test_id}: {e}")
        return []

async def update_question(session: AsyncSession, question_id: int, update_data: dict) -> bool:
    """Обновление вопроса"""
    try:
        valid_fields = ['question_text', 'correct_answer', 'points']
        update_values = {k: v for k, v in update_data.items() if k in valid_fields}
        
        if not update_values:
            return False
        
        # Получаем старую информацию о вопросе для обновления максимального балла
        old_question = await session.execute(
            select(TestQuestion).where(TestQuestion.id == question_id)
        )
        old_question = old_question.scalar_one_or_none()
        
        if not old_question:
            return False
        
        stmt = update(TestQuestion).where(TestQuestion.id == question_id).values(**update_values)
        await session.execute(stmt)
        
        # Обновляем максимальный балл теста
        await update_test_max_score(session, old_question.test_id)
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления вопроса {question_id}: {e}")
        await session.rollback()
        return False

async def delete_question(session: AsyncSession, question_id: int) -> bool:
    """Удаление вопроса"""
    try:
        # Получаем информацию о вопросе для обновления максимального балла
        question = await session.execute(
            select(TestQuestion).where(TestQuestion.id == question_id)
        )
        question = question.scalar_one_or_none()
        
        if not question:
            return False
        
        test_id = question.test_id
        
        await session.execute(delete(TestQuestion).where(TestQuestion.id == question_id))
        
        # Обновляем максимальный балл теста
        await update_test_max_score(session, test_id)
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления вопроса {question_id}: {e}")
        await session.rollback()
        return False

async def update_test_max_score(session: AsyncSession, test_id: int):
    """Обновление максимального балла теста на основе вопросов"""
    try:
        result = await session.execute(
            select(func.sum(TestQuestion.points)).where(TestQuestion.test_id == test_id)
        )
        max_score = result.scalar() or 0
        
        stmt = update(Test).where(Test.id == test_id).values(max_score=max_score)
        await session.execute(stmt)
    except Exception as e:
        logger.error(f"Ошибка обновления максимального балла теста {test_id}: {e}")

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ЭТАПАМИ СТАЖИРОВКИ
# =================================

async def get_all_stages(session: AsyncSession) -> List[InternshipStage]:
    """Получение всех этапов стажировки"""
    try:
        result = await session.execute(
            select(InternshipStage).where(InternshipStage.is_active == True)
            .order_by(InternshipStage.order_number)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения этапов стажировки: {e}")
        return []

async def get_stage_by_id(session: AsyncSession, stage_id: int) -> Optional[InternshipStage]:
    """Получение этапа по ID"""
    try:
        result = await session.execute(select(InternshipStage).where(InternshipStage.id == stage_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения этапа {stage_id}: {e}")
        return None

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С НАСТАВНИЧЕСТВОМ
# =================================

async def assign_mentor(session: AsyncSession, mentor_id: int, trainee_id: int, assigned_by_id: int, bot=None) -> Optional[Mentorship]:
    """Назначение наставника стажеру с полной валидацией"""
    try:
        # Валидация входных данных
        if not all([mentor_id, trainee_id, assigned_by_id]):
            logger.error("Все ID должны быть указаны для назначения наставника")
            return None
        
        if mentor_id == trainee_id:
            logger.error("Наставник не может быть наставником самому себе")
            return None
        
        # Проверяем существование пользователей
        mentor = await session.execute(select(User).where(User.id == mentor_id, User.is_active == True))
        mentor = mentor.scalar_one_or_none()
        if not mentor:
            logger.error(f"Наставник с ID {mentor_id} не найден или неактивен")
            return None
        
        trainee = await session.execute(select(User).where(User.id == trainee_id, User.is_active == True))
        trainee = trainee.scalar_one_or_none()
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден или неактивен")
            return None
        
        assigned_by = await session.execute(select(User).where(User.id == assigned_by_id, User.is_active == True))
        if not assigned_by.scalar_one_or_none():
            logger.error(f"Пользователь назначающий с ID {assigned_by_id} не найден")
            return None
        
        # Проверяем, что наставник имеет подходящую роль
        mentor_roles = await get_user_roles(session, mentor_id)
        role_names = [role.name for role in mentor_roles]
        if not any(role in ["Наставник", "Сотрудник", "Руководитель"] for role in role_names):
            logger.error(f"Пользователь {mentor_id} не может быть наставником (неподходящая роль)")
            return None
        
        # Проверяем, что стажер имеет роль стажера
        trainee_roles = await get_user_roles(session, trainee_id)
        trainee_role_names = [role.name for role in trainee_roles]
        if "Стажер" not in trainee_role_names:
            logger.error(f"Пользователь {trainee_id} не является стажером")
            return None
        
        # Проверяем, нет ли уже активного наставничества
        existing = await session.execute(
            select(Mentorship).where(
                Mentorship.trainee_id == trainee_id,
                Mentorship.is_active == True
            )
        )
        existing_mentorship = existing.scalar_one_or_none()
        
        if existing_mentorship:
            logger.warning(f"Стажер {trainee.full_name} уже имеет наставника. Переназначение...")
            # Деактивируем старое наставничество
            stmt = update(Mentorship).where(Mentorship.id == existing_mentorship.id).values(is_active=False)
            await session.execute(stmt)
        
        mentorship = Mentorship(
            mentor_id=mentor_id,
            trainee_id=trainee_id,
            assigned_by_id=assigned_by_id
        )
        session.add(mentorship)
        await session.commit()
        logger.info(f"Наставник {mentor.full_name} назначен стажеру {trainee.full_name}")
        
        # Отправляем уведомление стажёру о назначении наставника
        if bot:
            await send_notification_about_mentor_assignment(
                session, bot, trainee_id, mentor_id, assigned_by_id
            )
        
        # Отправляем уведомление наставнику о назначении стажёра
        if bot:
            await send_notification_about_new_trainee(
                session, bot, mentor_id, trainee_id, assigned_by_id
            )
        
        return mentorship
    except Exception as e:
        logger.error(f"Ошибка назначения наставника: {e}")
        await session.rollback()
        return None

async def get_mentor_trainees(session: AsyncSession, mentor_id: int) -> List[User]:
    """Получение списка стажеров у наставника (только с ролью Стажер)"""
    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы
                selectinload(User.internship_object),  # Загружаем объект стажировки
                selectinload(User.roles),  # Загружаем роли пользователя
                selectinload(User.groups)  # Загружаем группы пользователя
            )
            .join(Mentorship, User.id == Mentorship.trainee_id)
            .join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, user_roles.c.role_id == Role.id)
            .where(
                Mentorship.mentor_id == mentor_id,
                Mentorship.is_active == True,
                User.is_active == True,
                Role.name == "Стажер"
            ).order_by(User.full_name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения стажеров наставника {mentor_id}: {e}")
        return []

async def get_trainee_mentor(session: AsyncSession, trainee_id: int) -> Optional[User]:
    """Получение наставника стажера"""
    try:
        result = await session.execute(
            select(User).join(
                Mentorship, User.id == Mentorship.mentor_id
            ).where(
                Mentorship.trainee_id == trainee_id,
                Mentorship.is_active == True
            )
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения наставника стажера {trainee_id}: {e}")
        return None


async def get_user_mentor(session: AsyncSession, user_id: int) -> Optional[User]:
    """Алиас для get_trainee_mentor - получение наставника пользователя"""
    return await get_trainee_mentor(session, user_id)

async def get_unassigned_trainees(session: AsyncSession) -> List[User]:
    """Получение списка активированных стажеров без наставника"""
    try:
        result = await session.execute(
            select(User).join(
                user_roles, User.id == user_roles.c.user_id
            ).join(
                Role, user_roles.c.role_id == Role.id
            ).where(
                Role.name == "Стажер",
                User.is_activated == True,  # Только активированные пользователи
                ~User.id.in_(
                    select(Mentorship.trainee_id).where(Mentorship.is_active == True)
                )
            ).order_by(User.full_name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения стажеров без наставника: {e}")
        return []

async def get_available_mentors(session: AsyncSession) -> List[User]:
    """Получение списка пользователей, которые могут быть наставниками"""
    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы
                selectinload(User.internship_object)  # Загружаем объект стажировки
            )
            .join(
                user_roles, User.id == user_roles.c.user_id
            ).join(
                Role, user_roles.c.role_id == Role.id
            ).where(
                Role.name.in_(["Наставник", "Руководитель"])
            ).order_by(User.full_name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения доступных наставников: {e}")
        return []

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ДОСТУПОМ К ТЕСТАМ
# =================================

async def grant_test_access(session: AsyncSession, trainee_id: int, test_id: int, granted_by_id: int, bot=None) -> bool:
    """Предоставление доступа к тесту стажеру"""
    try:
        # Проверяем, нет ли уже доступа
        existing = await session.execute(
            select(TraineeTestAccess).where(
                TraineeTestAccess.trainee_id == trainee_id,
                TraineeTestAccess.test_id == test_id,
                TraineeTestAccess.is_active == True
            )
        )
        existing_access = existing.scalar_one_or_none()
        
        # Если доступа еще нет - создаем новый
        if not existing_access:
            access = TraineeTestAccess(
                trainee_id=trainee_id,
                test_id=test_id,
                granted_by_id=granted_by_id
            )
            session.add(access)
            await session.commit()
            logger.info(f"Создан новый доступ к тесту {test_id} для стажёра {trainee_id}")
        else:
            logger.info(f"Доступ к тесту {test_id} для стажёра {trainee_id} уже существует - отправляем повторное уведомление")
        
        # Отправляем уведомление стажеру ВСЕГДА (и при новом доступе, и при повторном назначении)
        if bot:
            await send_notification_about_new_test(session, bot, trainee_id, test_id, granted_by_id)
        
        return True
    except Exception as e:
        logger.error(f"Ошибка предоставления доступа к тесту: {e}")
        await session.rollback()
        return False

async def get_trainee_available_tests(session: AsyncSession, trainee_id: int) -> List[Test]:
    """
    Получение доступных тестов ТРАЕКТОРИИ для стажера
    
    ВАЖНО: Возвращает ТОЛЬКО тесты, которые входят в траекторию (через этапы/сессии).
    Тесты от наставника ВНЕ траектории идут в get_trainee_additional_tests_from_mentor()
    Тесты от рекрутера через рассылку - используй get_employee_tests_from_recruiter()
    """
    try:
        from database.models import LearningSession, TraineeSessionProgress, TraineeStageProgress, TraineeLearningPath
        
        # Получаем траекторию стажера
        trainee_path_result = await session.execute(
            select(TraineeLearningPath)
            .options(selectinload(TraineeLearningPath.learning_path))
            .where(
                TraineeLearningPath.trainee_id == trainee_id,
                TraineeLearningPath.is_active == True
            )
        )
        trainee_path = trainee_path_result.scalar_one_or_none()
        
        if not trainee_path:
            return []
        
        # Получаем все тесты из сессий траектории ТОЛЬКО из ОТКРЫТЫХ этапов
        result = await session.execute(
            select(Test).join(
                session_tests, Test.id == session_tests.c.test_id
            ).join(
                LearningSession, LearningSession.id == session_tests.c.session_id
            ).join(
                TraineeSessionProgress, TraineeSessionProgress.session_id == LearningSession.id
            ).join(
                TraineeStageProgress, TraineeSessionProgress.stage_progress_id == TraineeStageProgress.id
            ).where(
                TraineeStageProgress.trainee_path_id == trainee_path.id,
                TraineeStageProgress.is_opened == True,  # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: только открытые этапы
                Test.is_active == True
            ).order_by(Test.created_date)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения тестов траектории для стажера {trainee_id}: {e}")
        return []


async def get_user_available_tests(session: AsyncSession, user_id: int, exclude_completed: bool = True) -> List[Test]:
    """
    Универсальная функция получения доступных тестов для пользователя (стажер или сотрудник)
    
    Args:
        user_id: ID пользователя
        exclude_completed: Исключать ли пройденные тесты (по умолчанию True)
    
    Returns:
        List[Test]: Список доступных тестов
    """
    try:
        # Получаем все тесты, к которым у пользователя есть доступ
        result = await session.execute(
            select(Test).join(
                TraineeTestAccess, Test.id == TraineeTestAccess.test_id
            ).where(
                TraineeTestAccess.trainee_id == user_id,  # Используем существующую таблицу для всех пользователей
                TraineeTestAccess.is_active == True,
                Test.is_active == True
            ).order_by(Test.created_date)
        )
        available_tests = result.scalars().all()
        
        # Если нужно исключить пройденные тесты
        if exclude_completed:
            filtered_tests = []
            for test in available_tests:
                # Проверяем, есть ли успешный результат прохождения
                test_result = await get_user_test_result(session, user_id, test.id)
                if not (test_result and test_result.is_passed):
                    filtered_tests.append(test)
            return filtered_tests
        
        return available_tests
        
    except Exception as e:
        logger.error(f"Ошибка получения доступных тестов для пользователя {user_id}: {e}")
        return []


async def get_user_broadcast_tests(session: AsyncSession, user_id: int, exclude_completed: bool = False) -> List[Test]:
    """
    Универсальная функция получения тестов из рассылок для ЛЮБОГО пользователя
    (включая стажеров, сотрудников, наставников, рекрутеров и руководителей)
    
    Args:
        user_id: ID пользователя
        exclude_completed: Исключить пройденные тесты
    
    Returns:
        List[Test]: Список тестов доступных пользователю через рассылку (исключая тесты траектории)
    """
    try:
        from database.models import LearningSession, TraineeSessionProgress, TraineeStageProgress, TraineeLearningPath
        
        # Получаем все тесты, доступные пользователю через TraineeTestAccess
        all_tests_result = await session.execute(
            select(Test).join(
                TraineeTestAccess, Test.id == TraineeTestAccess.test_id
            ).where(
                TraineeTestAccess.trainee_id == user_id,
                TraineeTestAccess.is_active == True,
                Test.is_active == True
            ).order_by(Test.created_date)
        )
        all_tests = all_tests_result.scalars().all()
        
        # Получаем ID тестов из траектории (если пользователь - стажер с траекторией)
        trajectory_test_ids = set()
        trainee_path_result = await session.execute(
            select(TraineeLearningPath)
            .where(
                TraineeLearningPath.trainee_id == user_id,
                TraineeLearningPath.is_active == True
            )
        )
        trainee_path = trainee_path_result.scalar_one_or_none()
        
        if trainee_path:
            # Исключаем тесты траектории (только из открытых этапов)
            trajectory_tests_result = await session.execute(
                select(session_tests.c.test_id).join(
                    LearningSession, LearningSession.id == session_tests.c.session_id
                ).join(
                    TraineeSessionProgress, TraineeSessionProgress.session_id == LearningSession.id
                ).join(
                    TraineeStageProgress, TraineeSessionProgress.stage_progress_id == TraineeStageProgress.id
                ).where(
                    TraineeStageProgress.trainee_path_id == trainee_path.id,
                    TraineeStageProgress.is_opened == True
                )
            )
            trajectory_test_ids = set(row[0] for row in trajectory_tests_result.all())
        
        # Фильтруем: исключаем тесты траектории
        available_tests = [test for test in all_tests if test.id not in trajectory_test_ids]
        
        # Опционально исключаем пройденные тесты
        if exclude_completed:
            filtered_tests = []
            for test in available_tests:
                test_result = await get_user_test_result(session, user_id, test.id)
                if not (test_result and test_result.is_passed):
                    filtered_tests.append(test)
            return filtered_tests
        
        return available_tests
        
    except Exception as e:
        logger.error(f"Ошибка получения тестов рассылки для пользователя {user_id}: {e}")
        return []


async def get_employee_tests_from_recruiter(session: AsyncSession, user_id: int, exclude_completed: bool = True) -> List[Test]:
    """
    DEPRECATED: Использовать get_user_broadcast_tests()
    Оставлено для обратной совместимости
    
    Получение тестов для сотрудников/стажеров, назначенных рекрутером ИЛИ наставником ВНЕ траектории
    """
    return await get_user_broadcast_tests(session, user_id, exclude_completed)

async def revoke_test_access(session: AsyncSession, trainee_id: int, test_id: int) -> bool:
    """Отзыв доступа к тесту"""
    try:
        stmt = update(TraineeTestAccess).where(
            TraineeTestAccess.trainee_id == trainee_id,
            TraineeTestAccess.test_id == test_id
        ).values(is_active=False)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка отзыва доступа к тесту: {e}")
        await session.rollback()
        return False

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С РЕЗУЛЬТАТАМИ ТЕСТОВ
# =================================

async def save_test_result(session: AsyncSession, result_data: dict) -> Optional[TestResult]:
    """Сохранение результата прохождения теста"""
    try:
        test_result = TestResult(
            user_id=result_data['user_id'],
            test_id=result_data['test_id'],
            score=result_data['score'],
            max_possible_score=result_data['max_possible_score'],
            is_passed=result_data['is_passed'],
            start_time=result_data['start_time'],
            end_time=result_data['end_time'],
            answers=json.dumps(result_data.get('answers', {}), ensure_ascii=False),
            answers_details=result_data.get('answers_details', []),
            wrong_answers=result_data.get('wrong_answers', [])
        )
        session.add(test_result)
        await session.commit()
        logger.info(f"Результат теста сохранен для пользователя {result_data['user_id']}, тест {result_data['test_id']}")
        return test_result
    except Exception as e:
        logger.error(f"Ошибка сохранения результата теста: {e}")
        await session.rollback()
        return None

async def get_user_test_results(session: AsyncSession, user_id: int) -> List[TestResult]:
    """Получение результатов тестов пользователя"""
    try:
        result = await session.execute(
            select(TestResult).where(TestResult.user_id == user_id)
            .order_by(TestResult.created_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения результатов тестов пользователя {user_id}: {e}")
        return []

async def get_test_results_summary(session: AsyncSession, test_id: int) -> List[TestResult]:
    """Получение сводки результатов по тесту"""
    try:
        result = await session.execute(
            select(TestResult).where(TestResult.test_id == test_id)
            .order_by(TestResult.score.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения сводки результатов теста {test_id}: {e}")
        return []


async def delete_trajectory_test_results(session: AsyncSession, trainee_id: int, learning_path_id: int) -> bool:
    """Удаление результатов тестов при повторном назначении траектории"""
    try:
        from database.models import LearningPath, LearningStage, LearningSession, session_tests
        
        # Получаем все тесты из траектории
        tests_query = await session.execute(
            select(Test)
            .join(session_tests, Test.id == session_tests.c.test_id)
            .join(LearningSession, session_tests.c.session_id == LearningSession.id)
            .join(LearningStage, LearningSession.stage_id == LearningStage.id)
            .join(LearningPath, LearningStage.learning_path_id == LearningPath.id)
            .where(LearningPath.id == learning_path_id)
        )
        trajectory_tests = tests_query.scalars().all()
        
        if not trajectory_tests:
            logger.info(f"В траектории {learning_path_id} нет тестов для удаления результатов")
            return True
        
        # Получаем ID тестов
        test_ids = [test.id for test in trajectory_tests]
        
        # Удаляем результаты тестов стажера по этим тестам
        deleted_count = await session.execute(
            delete(TestResult).where(
                TestResult.user_id == trainee_id,
                TestResult.test_id.in_(test_ids)
            )
        )
        
        await session.commit()
        logger.info(f"Удалено {deleted_count.rowcount} результатов тестов для стажера {trainee_id} в траектории {learning_path_id}")
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка удаления результатов тестов для стажера {trainee_id} в траектории {learning_path_id}: {e}")
        return False

async def check_test_already_passed(session: AsyncSession, user_id: int, test_id: int) -> bool:
    """Проверка, проходил ли пользователь тест"""
    try:
        result = await session.execute(
            select(func.count()).select_from(TestResult).where(
                TestResult.user_id == user_id,
                TestResult.test_id == test_id
            )
        )
        count = result.scalar()
        return count > 0
    except Exception as e:
        logger.error(f"Ошибка проверки прохождения теста: {e}")
        return False

async def check_test_access(session: AsyncSession, user_id: int, test_id: int) -> bool:
    """Проверка доступа пользователя к тесту"""
    try:
        # Получаем роли пользователя
        user_roles = await get_user_roles(session, user_id)
        role_names = [role.name for role in user_roles]
        
        # Для стажеров - проверяем доступ через TraineeTestAccess И открытость этапов
        if "Стажер" in role_names:
            # Сначала проверяем базовый доступ через TraineeTestAccess
            result = await session.execute(
                select(TraineeTestAccess).where(
                    TraineeTestAccess.trainee_id == user_id,
                    TraineeTestAccess.test_id == test_id,
                    TraineeTestAccess.is_active == True
                )
            )
            access = result.scalar_one_or_none()
            if not access:
                return False
            
            # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Если тест из траектории, проверяем открытость этапа
            from database.models import LearningSession, TraineeSessionProgress, TraineeStageProgress, TraineeLearningPath, session_tests
            
            # Проверяем, входит ли тест в траекторию
            trainee_path_result = await session.execute(
                select(TraineeLearningPath)
                .where(
                    TraineeLearningPath.trainee_id == user_id,
                    TraineeLearningPath.is_active == True
                )
            )
            trainee_path = trainee_path_result.scalar_one_or_none()
            
            if trainee_path:
                # Проверяем, входит ли тест в сессии траектории И этап открыт
                trajectory_test_result = await session.execute(
                    select(session_tests.c.test_id).join(
                        LearningSession, LearningSession.id == session_tests.c.session_id
                    ).join(
                        TraineeSessionProgress, TraineeSessionProgress.session_id == LearningSession.id
                    ).join(
                        TraineeStageProgress, TraineeSessionProgress.stage_progress_id == TraineeStageProgress.id
                    ).where(
                        TraineeStageProgress.trainee_path_id == trainee_path.id,
                        TraineeStageProgress.is_opened == True,  # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: только открытые этапы
                        session_tests.c.test_id == test_id
                    )
                )
                trajectory_test = trajectory_test_result.first()
                
                # Если тест из траектории, но этап закрыт - проверяем источник доступа
                if trajectory_test is None:
                    # Проверяем, входит ли тест в траекторию вообще (для диагностики)
                    all_trajectory_test_result = await session.execute(
                        select(session_tests.c.test_id).join(
                            LearningSession, LearningSession.id == session_tests.c.session_id
                        ).join(
                            TraineeSessionProgress, TraineeSessionProgress.session_id == LearningSession.id
                        ).join(
                            TraineeStageProgress, TraineeSessionProgress.stage_progress_id == TraineeStageProgress.id
                        ).where(
                            TraineeStageProgress.trainee_path_id == trainee_path.id,
                            session_tests.c.test_id == test_id
                        )
                    )
                    all_trajectory_test = all_trajectory_test_result.first()
                    
                    if all_trajectory_test is not None:
                        # Тест из траектории, но этап закрыт
                        # Проверяем источник доступа: если доступ через рассылку - разрешаем
                        if access.granted_by_id:  # Доступ через рассылку от рекрутера
                            logger.info(f"Доступ к траекторному тесту {test_id} разрешен через рассылку для стажера {user_id}")
                            return True
                        else:
                            # Доступ через наставника, но этап закрыт - запрещаем
                            logger.warning(f"Доступ к тесту {test_id} запрещен: этап закрыт для стажера {user_id}")
                            return False
            
            return True
        
        # Для сотрудников - проверяем доступ через тесты от рекрутера
        elif "Сотрудник" in role_names:
            # Проверяем, что тест создан рекрутером
            test = await get_test_by_id(session, test_id)
            if not test:
                return False
                
            # Получаем создателя теста
            creator = await get_user_by_id(session, test.creator_id)
            if not creator:
                return False
                
            creator_roles = await get_user_roles(session, creator.id)
            creator_role_names = [role.name for role in creator_roles]
            
            # Доступ есть, если тест создан рекрутером
            return "Рекрутер" in creator_role_names
        
        # Для других ролей (наставники, рекрутеры) - полный доступ
        else:
            return True
            
    except Exception as e:
        logger.error(f"Ошибка проверки доступа к тесту: {e}")
        return False

async def get_user_test_result(session: AsyncSession, user_id: int, test_id: int) -> Optional[TestResult]:
    """Получение последнего результата конкретного теста пользователя"""
    try:
        result = await session.execute(
            select(TestResult).where(
                TestResult.user_id == user_id,
                TestResult.test_id == test_id
            ).order_by(TestResult.created_date.desc())
        )
        return result.scalars().first()  # Возвращаем первый (самый новый) результат
    except Exception as e:
        logger.error(f"Ошибка получения результата теста пользователя: {e}")
        return None

async def get_user_test_attempts_count(session: AsyncSession, user_id: int, test_id: int) -> int:
    """Подсчет количества попыток прохождения теста пользователем"""
    try:
        result = await session.execute(
            select(func.count()).select_from(TestResult).where(
                TestResult.user_id == user_id,
                TestResult.test_id == test_id
            )
        )
        return result.scalar() or 0
    except Exception as e:
        logger.error(f"Ошибка подсчета попыток теста: {e}")
        return 0

async def can_user_take_test(session: AsyncSession, user_id: int, test_id: int) -> tuple[bool, str]:
    """
    Проверяет, может ли пользователь пройти тест с учетом лимитов и пройденных тестов
    Возвращает: (можно_ли_проходить, сообщение_об_ошибке)
    """
    try:
        # Получаем тест
        test = await get_test_by_id(session, test_id)
        if not test:
            return False, "Тест не найден"
        
        # Проверяем лимит попыток, если он установлен (max_attempts > 0)
        # По умолчанию max_attempts = 0 (бесконечные попытки)
        if test.max_attempts > 0:
            attempts_count = await get_user_test_attempts_count(session, user_id, test_id)
            if attempts_count >= test.max_attempts:
                return False, f"Превышен лимит попыток ({attempts_count}/{test.max_attempts})"
        
        # Для бесконечных попыток (max_attempts = 0) всегда разрешаем прохождение
        # Пользователь может пересдавать тест для улучшения результата
        return True, ""
    except Exception as e:
        logger.error(f"Ошибка проверки возможности прохождения теста: {e}")
        return False, "Ошибка проверки доступа"

async def get_question_analytics(session: AsyncSession, question_id: int) -> dict:
    """Собирает и возвращает реальную аналитику по конкретному вопросу."""
    
    # Находим все результаты, где есть информация по данному вопросу
    all_results_query = await session.execute(
        select(TestResult).where(TestResult.answers_details.isnot(None))
    )
    all_results = all_results_query.scalars().all()
    
    relevant_answers = []
    for result in all_results:
        # answers_details - это список словарей
        for answer_detail in result.answers_details:
            if answer_detail.get('question_id') == question_id:
                relevant_answers.append(answer_detail)

    if not relevant_answers:
        return {"total_answers": 0, "correct_answers": 0, "avg_time_seconds": 0}

    total_answers = len(relevant_answers)
    correct_answers = sum(1 for ans in relevant_answers if ans.get('is_correct'))
    total_time = sum(ans.get('time_spent', 0) for ans in relevant_answers)
    
    return {
        "total_answers": total_answers,
        "correct_answers": correct_answers,
        "avg_time_seconds": total_time / total_answers if total_answers > 0 else 0
    }

async def validate_admin_token(session: AsyncSession, init_token: str) -> bool:
    """Проверка токена администратора без создания пользователя"""
    import os

    # Поддержка множественных токенов через запятую
    admin_tokens_str = os.getenv("ADMIN_INIT_TOKENS", os.getenv("ADMIN_INIT_TOKEN", ""))

    if not admin_tokens_str:
        logger.error("Не настроены токены инициализации администратора")
        return False

    # Разбираем токены
    valid_tokens = [token.strip() for token in admin_tokens_str.split(",") if token.strip()]

    if init_token not in valid_tokens:
        logger.error(f"Неверный токен инициализации администратора. Ожидался один из: {valid_tokens}")
        return False

    # Проверяем лимит администраторов (по умолчанию максимум 5)
    max_admins = int(os.getenv("MAX_ADMINS", "5"))
    existing_managers = await get_users_by_role(session, "Руководитель")
    existing_recruiters = await get_users_by_role(session, "Рекрутер")

    total_admins = len(existing_managers) + len(existing_recruiters)

    if total_admins >= max_admins:
        logger.error(f"Достигнут лимит администраторов ({max_admins})")
        return False

    return True


async def create_admin_with_role(session: AsyncSession, admin_data: dict, role_name: str) -> bool:
    """Создание администратора с выбранной ролью"""
    try:
        user = User(
            tg_id=admin_data['tg_id'],
            username=admin_data.get('username'),
            full_name=admin_data['full_name'],
            phone_number=admin_data['phone_number'],
            is_active=True,  # Администраторы автоматически активны
            is_activated=True  # Администраторы автоматически активированы
        )
        session.add(user)
        await session.flush()

        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one()

        stmt = insert(user_roles).values(
            user_id=user.id,
            role_id=role.id
        )
        await session.execute(stmt)

        await session.commit()

        logger.info(f"Администратор {user.id} создан с ролью {role_name} и автоматически активирован")
        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка создания администратора: {e}")
        return False


async def create_initial_admin_with_token(session: AsyncSession, admin_data: dict, init_token: str) -> bool:
    """УСТАРЕВШАЯ ФУНКЦИЯ - оставлена для обратной совместимости"""
    # Сначала проверяем токен
    if not await validate_admin_token(session, init_token):
        return False

    # Создаем администратора с ролью Руководитель (по умолчанию для обратной совместимости)
    return await create_admin_with_role(session, admin_data, "Руководитель")

# =================================
# ФУНКЦИИ ДЛЯ УВЕДОМЛЕНИЙ
# =================================

async def send_notification_about_new_test(session: AsyncSession, bot, trainee_id: int, test_id: int, granted_by_id: int):
    """Отправка уведомления стажеру о назначении нового теста"""
    try:
        # Получаем данные о стажере
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден")
            return False
            
        # Получаем данные о тесте
        test = await get_test_by_id(session, test_id)
        if not test:
            logger.error(f"Тест с ID {test_id} не найден")
            return False
            
        # Получаем данные о наставнике
        mentor = await get_user_by_id(session, granted_by_id)
        if not mentor:
            logger.error(f"Наставник с ID {granted_by_id} не найден")
            return False
            
        # Получаем название этапа, если есть
        stage_name = None
        if test.stage_id:
            stage = await get_stage_by_id(session, test.stage_id)
            if stage:
                stage_name = stage.name
        
        await send_test_notification(
            bot=bot,
            trainee_tg_id=trainee.tg_id,
            test_name=test.name,
            mentor_name=mentor.full_name,
            test_description=test.description,
            stage_name=stage_name,
            test_id=test_id
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о новом тесте: {e}")
        return False

async def send_notification_about_mentor_assignment(session: AsyncSession, bot, trainee_id: int, mentor_id: int, assigned_by_id: int):
    """Отправка уведомления стажеру о назначении наставника"""
    try:
        # Получаем данные о стажере
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден")
            return False
            
        # Получаем данные о наставнике
        mentor = await get_user_by_id(session, mentor_id)
        if not mentor:
            logger.error(f"Наставник с ID {mentor_id} не найден")
            return False
            
        # Получаем данные о том, кто назначил
        assigned_by = await get_user_by_id(session, assigned_by_id)
        if not assigned_by:
            logger.error(f"Пользователь назначивший с ID {assigned_by_id} не найден")
            return False
        
        await send_mentor_assignment_notification(
            bot=bot,
            trainee_tg_id=trainee.tg_id,
            mentor_tg_id=mentor.tg_id,
            mentor_name=mentor.full_name,
            mentor_phone=mentor.phone_number,
            mentor_username=mentor.username,
            assigned_by_name=assigned_by.full_name,
            trainee_internship_object=trainee.internship_object.name if trainee.internship_object else None,
            trainee_work_object=trainee.work_object.name if trainee.work_object else None,
            mentor_work_object=mentor.work_object.name if mentor.work_object else None
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о назначении наставника: {e}")
        return False

async def send_test_notification(bot, trainee_tg_id: int, test_name: str, mentor_name: str, test_description: str = None, stage_name: str = None, test_id: int = None):
    """Отправка уведомления стажеру о назначении нового теста"""
    try:
        notification_text = """🚨Появился новый тест для прохождения!
Можно открыть его из раздела «Мои тесты» и начать, когда тебе будет удобно."""

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Перейти к тесту", callback_data=f"take_test:{test_id}")],
            [InlineKeyboardButton(text="📋 Мои тесты", callback_data="my_broadcast_tests_shortcut")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]) if test_id else None
        
        await bot.send_message(
            chat_id=trainee_tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logger.info(f"Уведомление о тесте '{test_name}' отправлено стажеру {trainee_tg_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления стажеру {trainee_tg_id}: {e}")
        return False


async def send_broadcast_notification(bot, user_tg_id: int, broadcast_script: str, 
                                     broadcast_photos: list, broadcast_material_id: int = None, 
                                     test_id: int = None, broadcast_docs: list | None = None) -> bool:
    """
    Отправка расширенного уведомления о рассылке
    
    Args:
        bot: Экземпляр бота
        user_tg_id: Telegram ID получателя
        broadcast_script: Текст рассылки
        broadcast_photos: Список file_id фотографий
        broadcast_material_id: ID материала из базы знаний
        test_id: ID теста (опционально)
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaDocument
        
        # 1. Если есть фото/документы-превью - отправляем медиагруппы
        photos = []
        docs = []
        # Фото приходят отдельным списком; документы могут прийти в broadcast_docs
        for item in (broadcast_photos or []):
            photos.append(item)
        for item in (broadcast_docs or []):
            docs.append(item)

        if photos:
            if len(photos) == 1:
                await bot.send_photo(chat_id=user_tg_id, photo=photos[0])
            else:
                media_group = [InputMediaPhoto(media=pid) for pid in photos]
                await bot.send_media_group(chat_id=user_tg_id, media=media_group)
        if docs:
            if len(docs) == 1:
                await bot.send_document(chat_id=user_tg_id, document=docs[0])
            else:
                docs_group = [InputMediaDocument(media=did) for did in docs]
                await bot.send_media_group(chat_id=user_tg_id, media=docs_group)
        
        # 2. Формируем клавиатуру
        keyboard = []
        
        if test_id:
            keyboard.append([InlineKeyboardButton(text="🚀 Перейти к тесту", callback_data=f"take_test:{test_id}")])
        
        if broadcast_material_id:
            keyboard.append([InlineKeyboardButton(text="📚 Материалы", callback_data=f"broadcast_material:{broadcast_material_id}")])
        
        keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
        
        # 3. Отправляем текст с кнопками
        await bot.send_message(
            chat_id=user_tg_id,
            text=broadcast_script,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        logger.info(f"Расширенное уведомление отправлено пользователю {user_tg_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки расширенного уведомления пользователю {user_tg_id}: {e}")
        return False


async def send_mentor_assignment_notification(bot, trainee_tg_id: int, mentor_tg_id: int, mentor_name: str, mentor_phone: str, mentor_username: str = None, assigned_by_name: str = None, trainee_internship_object: str = None, trainee_work_object: str = None, mentor_work_object: str = None):
    """Отправка уведомления стажеру о назначении наставника"""
    try:
        # Формируем контактную информацию наставника
        contact_info = f"📞 <b>Телефон:</b> {mentor_phone}"
        if mentor_username:
            contact_info += f"\n📧 <b>Telegram:</b> @{mentor_username}"
        else:
            contact_info += f"\n📧 <b>Telegram:</b> не указан"

        assigned_info = f"\n👤 <b>Назначил:</b> {assigned_by_name}" if assigned_by_name else ""

        # Формируем информацию об объектах
        objects_info = ""
        if trainee_internship_object or trainee_work_object:
            objects_info = "\n🏢 <b>Информация об объектах:</b>\n"
            if trainee_internship_object:
                objects_info += f"📍<b>1️⃣Объект стажировки:</b> {trainee_internship_object}\n"
            if trainee_work_object:
                objects_info += f"📍<b>2️⃣Объект работы:</b> {trainee_work_object}\n"
            if mentor_work_object:
                objects_info += f"📍<b>Объект работы наставника:</b> {mentor_work_object}"

        notification_text = f"""🎯 <b>Тебе назначен наставник!</b>

👨‍🏫 <b>Твой наставник:</b> {mentor_name}

📋 <b>Контактная информация:</b>
{contact_info}{assigned_info}{objects_info}

💡 <b>Что дальше?</b>
• Свяжитесь с наставником для знакомства
• Обсудите план обучения и цели стажировки
• Задавайте вопросы и просите помощь при необходимости
• Наставник поможет тебе с тестами и заданиями

🎯 <b>Удачи в обучении!</b>"""

        # Создаем клавиатуру с полезными кнопками
        keyboard_buttons = []
        
        # Кнопка для связи с наставником (всегда показываем)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="💬 Написать наставнику", 
                url=f"tg://user?id={mentor_tg_id}"  # Используем tg://user для прямого сообщения
            )
        ])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="🗺️ Тесты траектории", callback_data="trajectory_tests_shortcut")],
            [InlineKeyboardButton(text="👨‍🏫 Информация о наставнике", callback_data="my_mentor_info")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await bot.send_message(
            chat_id=trainee_tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logger.info(f"Уведомление о назначении наставника '{mentor_name}' отправлено стажеру {trainee_tg_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о наставнике стажеру {trainee_tg_id}: {e}")
        return False 

async def send_notification_about_new_trainee(session: AsyncSession, bot, mentor_id: int, trainee_id: int, assigned_by_id: int):
    """Отправка уведомления наставнику о назначении ему нового стажёра"""
    try:
        # Получаем данные о наставнике
        mentor = await get_user_by_id(session, mentor_id)
        if not mentor:
            logger.error(f"Наставник с ID {mentor_id} не найден")
            return False
            
        # Получаем данные о стажере
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден")
            return False
            
        # Получаем данные о том, кто назначил
        assigned_by = await get_user_by_id(session, assigned_by_id)
        if not assigned_by:
            logger.error(f"Пользователь назначивший с ID {assigned_by_id} не найден")
            return False
        
        # Получаем дополнительные данные о стажере
        trainee_roles = await get_user_roles(session, trainee_id)
        trainee_groups = await get_user_groups(session, trainee_id)
        
        # Получаем номер стажера (порядковый номер среди стажеров)
        all_trainees = await get_all_trainees(session)
        trainee_number = None
        for i, t in enumerate(all_trainees, 1):
            if t.id == trainee_id:
                trainee_number = i
                break
        
        await send_trainee_assignment_notification(
            bot=bot,
            mentor_tg_id=mentor.tg_id,
            trainee_name=trainee.full_name,
            trainee_phone=trainee.phone_number,
            trainee_tg_id=trainee.tg_id,
            trainee_username=trainee.username,
            trainee_registration_date=trainee.registration_date.strftime('%d.%m.%Y %H:%M'),
            assigned_by_name=assigned_by.full_name,
            trainee_roles=trainee_roles,
            trainee_groups=trainee_groups,
            trainee_number=trainee_number,
            trainee_internship_object=trainee.internship_object.name if trainee.internship_object else None,
            trainee_work_object=trainee.work_object.name if trainee.work_object else None
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о назначении стажёра: {e}")
        return False

async def send_trainee_assignment_notification(bot, mentor_tg_id: int, trainee_name: str, trainee_phone: str, trainee_tg_id: int = None, trainee_username: str = None, trainee_registration_date: str = None, assigned_by_name: str = None, trainee_roles: list = None, trainee_groups: list = None, trainee_number: int = None, trainee_internship_object: str = None, trainee_work_object: str = None):
    """Отправка уведомления наставнику о назначении ему нового стажёра"""
    try:
        # Формируем основную информацию
        role_name = trainee_roles[0].name if trainee_roles else "Стажёр"
        group_name = trainee_groups[0].name if trainee_groups else "Не назначена"
        
        # Формируем username с экранированием
        username_text = f"@{trainee_username}" if trainee_username else "не указан"
        if trainee_username and "_" in trainee_username:
            username_text = f"@{trainee_username.replace('_', '_')}"
        
        # Формируем информацию об объектах
        objects_info = ""
        if trainee_internship_object:
            objects_info += f"<b>Стажировки:</b> {trainee_internship_object}\n"
        if trainee_work_object:
            objects_info += f"<b>Работы:</b> {trainee_work_object}"
        
        notification_text = f"""‼️<b>Тебе назначен новый стажёр!</b>


<b>{trainee_name}</b>


<b>Телефон:</b> {trainee_phone}
<b>Username:</b> {username_text}
<b>Номер:</b> #{trainee_number or 'N/A'}
<b>Дата регистрации:</b> {trainee_registration_date or 'Не указана'}


━━━━━━━━━━━━


🗂️ <b>Статус:</b>
<b>Группа:</b> {group_name}
<b>Роль:</b> {role_name}


━━━━━━━━━━━━


📍 <b>Объект:</b>
{objects_info}


Теперь свяжись со стажером, согласуй план обучение, выдай доступ к тестам, помогай и отслеживай прогресс. Успехов в наставничестве!"""

        # Создаем клавиатуру с полезными кнопками
        keyboard_buttons = []
        
        # Кнопка для связи со стажёром (всегда показываем)
        if trainee_tg_id:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💬 Написать стажёру", 
                    url=f"tg://user?id={trainee_tg_id}"
                )
            ])
        elif trainee_username:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💬 Написать стажёру", 
                    url=f"https://t.me/{trainee_username}"
                )
            ])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="👥 Мои стажёры", callback_data="my_trainees")],
            [InlineKeyboardButton(text="🗺️ Назначить траекторию", callback_data="assign_trajectory")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await bot.send_message(
            chat_id=mentor_tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logger.info(f"Уведомление о назначении стажёра '{trainee_name}' отправлено наставнику {mentor_tg_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о стажёре наставнику {mentor_tg_id}: {e}")
        return False 

async def send_notification_about_new_trainee_registration(session: AsyncSession, bot, trainee_id: int):
    """Отправка уведомления всем рекрутерам о регистрации нового стажёра"""
    try:
        # Получаем данные о стажере
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден")
            return False
            
        # Получаем всех рекрутеров
        recruiters = await get_users_by_role(session, "Рекрутер")
        
        if not recruiters:
            logger.info("Нет рекрутеров в системе для отправки уведомлений")
            return True
        
        # Отправляем уведомления каждому рекрутеру
        success_count = 0
        for recruiter in recruiters:
            try:
                await send_new_trainee_registration_notification(
                    bot=bot,
                    recruiter_tg_id=recruiter.tg_id,
                    trainee_name=trainee.full_name,
                    trainee_phone=trainee.phone_number,
                    trainee_username=trainee.username,
                    trainee_registration_date=trainee.registration_date.strftime('%d.%m.%Y %H:%M')
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления рекрутеру {recruiter.tg_id}: {e}")
        
        logger.info(f"Уведомления о новом стажёре отправлены {success_count}/{len(recruiters)} рекрутерам")
        return success_count > 0
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о новом стажёре: {e}")
        return False

async def send_new_trainee_registration_notification(bot, recruiter_tg_id: int, trainee_name: str, trainee_phone: str, trainee_username: str = None, trainee_registration_date: str = None):
    """Отправка уведомления рекрутеру о регистрации нового стажёра"""
    try:
        # Формируем контактную информацию стажёра
        contact_info = f"📞 <b>Телефон:</b> {trainee_phone}"
        if trainee_username:
            contact_info += f"\n📧 <b>Telegram:</b> @{trainee_username}"
        else:
            contact_info += f"\n📧 <b>Telegram:</b> не указан"
        
        if trainee_registration_date:
            contact_info += f"\n📅 <b>Дата регистрации:</b> {trainee_registration_date}"
        
        notification_text = f"""🎉 <b>Новый стажёр зарегистрировался!</b>

👤 <b>Стажёр:</b> {trainee_name}

📋 <b>Контактная информация:</b>
{contact_info}

💡 <b>Рекомендуемые действия:</b>
• Свяжитесь со стажёром для знакомства
• Назначьте подходящего наставника
• Предоставьте доступ к начальным тестам
• Проведите вводный инструктаж

⚡ <b>Быстрые действия:</b>"""

        # Создаем клавиатуру с полезными кнопками
        keyboard_buttons = []
        
        # Кнопка для связи со стажёром (если есть username)
        if trainee_username:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💬 Написать стажёру", 
                    url=f"https://t.me/{trainee_username}"
                )
            ])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="👨‍🏫 Назначить наставника", callback_data="assign_mentor")],
            [InlineKeyboardButton(text="👥 Список новых стажёров", callback_data="new_trainees_list")],
            [InlineKeyboardButton(text="📊 Предоставить доступ к тестам", callback_data="grant_test_access")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await bot.send_message(
            chat_id=recruiter_tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logger.info(f"Уведомление о новом стажёре '{trainee_name}' отправлено рекрутеру {recruiter_tg_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о новом стажёре рекрутеру {recruiter_tg_id}: {e}")
        return False


async def get_unactivated_users(session: AsyncSession) -> List[User]:
    """Получение списка неактивированных пользователей (исключая администраторов)"""
    try:
        # Исключаем пользователей с ролями Руководитель и Рекрутер,
        # так как они автоматически активируются
        result = await session.execute(
            select(User)
            .where(User.is_activated == False)
            .where(~User.roles.any(Role.name.in_(["Руководитель", "Рекрутер"])))
            .order_by(User.registration_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения неактивированных пользователей: {e}")
        return []


async def create_user_without_role(session: AsyncSession, user_data: dict, bot=None) -> User:
    """Создание пользователя без роли (для последующей активации рекрутером)"""
    try:
        user = User(
            tg_id=user_data['tg_id'],
            username=user_data.get('username'),
            full_name=user_data['full_name'],
            phone_number=user_data['phone_number'],
            is_activated=False  # Пользователь неактивирован до обработки рекрутером
        )
        session.add(user)
        await session.flush()
        await session.commit()
        
        # Отправляем уведомления рекрутерам о новом пользователе
        if bot:
            await send_notification_about_new_user_registration(session, bot, user.id)
        
        logger.info(f"Пользователь {user.id} создан без роли для последующей активации")
        return user
    except Exception as e:
        logger.error(f"Ошибка создания пользователя без роли: {e}")
        await session.rollback()
        raise


async def send_notification_about_activation(session: AsyncSession, bot, user_id: int, 
                                           role_name: str, group_id: int, 
                                           internship_object_id: int, work_object_id: int):
    """Отправка уведомления пользователю об активации"""
    try:
        # Получаем данные пользователя
        user = await get_user_with_details(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
            
        # Получаем данные группы
        group = await get_group_by_id(session, group_id)
        group_name = group.name if group else "Не назначена"
        
        # Получаем данные объектов
        internship_object = await get_object_by_id(session, internship_object_id)
        work_object = await get_object_by_id(session, work_object_id)
        
        internship_object_name = internship_object.name if internship_object else "Не назначен"
        work_object_name = work_object.name if work_object else "Не назначен"
        
        # Формируем уведомление в зависимости от роли
        if role_name == "Стажер":
            notification_text = f"""✔️Доступ активирован
Добро пожаловать в команду!

👑Твоя Роль: {role_name}
🗂️Твоя Группа: {group_name}
📍1️⃣Твой Объект стажировки: {internship_object_name}
📍2️⃣Твой Объект работы: {work_object_name}

Совсем скоро тебе назначат наставника"""
        else:
            # Для Сотрудника, Рекрутера, Управляющего
            notification_text = f"""✔️Доступ активирован
Добро пожаловать в команду!

👑Твоя Роль: {role_name}
🗂️Твоя Группа: {group_name}
📍2️⃣Твой Объект работы: {work_object_name}"""

        # Создаем клавиатуру с кнопкой "Главное меню"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])

        await bot.send_message(chat_id=user.tg_id, text=notification_text, parse_mode="HTML", reply_markup=keyboard)
        logger.info(f"Уведомление об активации отправлено пользователю {user.tg_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об активации пользователю {user_id}: {e}")
        return False


async def send_notification_about_new_user_registration(session: AsyncSession, bot, user_id: int):
    """Отправка уведомления всем рекрутерам о регистрации нового пользователя"""
    try:
        # Получаем данные о пользователе
        user = await get_user_by_id(session, user_id)
        if not user:
            logger.error(f"Пользователь с ID {user_id} не найден")
            return False
            
        # Получаем всех рекрутеров
        recruiters = await get_users_by_role(session, "Рекрутер")
        
        if not recruiters:
            logger.info("Нет рекрутеров в системе для отправки уведомлений")
            return True
            
        # Формируем текст уведомления
        registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Не указана"
        
        notification_text = f"""‼️<b>Новый пользователь</b>

<b>Пользователь:</b> {user.full_name}
<b>Телефон:</b> {user.phone_number}
<b>Дата регистрации:</b> {registration_date}

⚠️<b>Требует активации!</b> Используй список "Новые пользователи" для назначения роли, группы и объектов"""

        # Создаем инлайн клавиатуру с кнопкой "Новые пользователи"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Новые пользователи", callback_data="show_new_users")]
        ])

        # Отправляем уведомления всем рекрутерам
        for recruiter in recruiters:
            try:
                await bot.send_message(
                    chat_id=recruiter.tg_id,
                    text=notification_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                logger.info(f"Уведомление о новом пользователе отправлено рекрутеру {recruiter.tg_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления рекрутеру {recruiter.tg_id}: {e}")
                continue
                
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о новом пользователе: {e}")
        return False


async def get_all_activated_users(session: AsyncSession) -> List[User]:
    """Получение всех активированных пользователей с их ролями, группами и объектами"""
    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            )
            .where(User.is_activated == True)
            .order_by(User.id)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех активированных пользователей: {e}")
        return []


async def get_users_by_group(session: AsyncSession, group_id: int) -> List[User]:
    """Получение пользователей по группе с их полной информацией"""
    try:
        result = await session.execute(
            select(User)
            .join(user_groups, User.id == user_groups.c.user_id)
            .options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            )
            .where(
                user_groups.c.group_id == group_id,
                User.is_activated == True
            )
            .order_by(User.full_name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения пользователей по группе {group_id}: {e}")
        return []


async def get_users_by_object(session: AsyncSession, object_id: int) -> List[User]:
    """Получение пользователей по объекту (стажировки или работы) с их полной информацией"""
    try:
        result = await session.execute(
            select(User)
            .join(user_objects, User.id == user_objects.c.user_id)
            .options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            )
            .where(
                user_objects.c.object_id == object_id,
                User.is_activated == True
            )
            .order_by(User.full_name)
        )
        users_by_objects = result.scalars().all()
        
        # Также ищем пользователей, где этот объект назначен как internship_object или work_object
        result2 = await session.execute(
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            )
            .where(
                or_(
                    User.internship_object_id == object_id,
                    User.work_object_id == object_id
                ),
                User.is_activated == True
            )
            .order_by(User.full_name)
        )
        users_by_direct = result2.scalars().all()
        
        # Объединяем и убираем дубликаты
        all_users = {}
        for user in users_by_objects + users_by_direct:
            all_users[user.id] = user
            
        return list(all_users.values())
        
    except Exception as e:
        logger.error(f"Ошибка получения пользователей по объекту {object_id}: {e}")
        return []


async def search_activated_users_by_name(session: AsyncSession, query: str) -> List[User]:
    """
    Поиск активированных пользователей по ФИО (частичное совпадение, case-insensitive)
    
    Args:
        session: Сессия БД
        query: Поисковый запрос
    
    Returns:
        Список найденных пользователей с полной информацией
    """
    try:
        search_pattern = f"%{query}%"
        
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.groups),
                selectinload(User.internship_object),
                selectinload(User.work_object)
            )
            .where(
                User.is_activated == True,
                User.full_name.ilike(search_pattern)
            )
            .order_by(User.full_name)
        )
        users = result.scalars().all()
        
        logger.info(f"Поиск активированных пользователей по запросу '{query}': найдено {len(users)}")
        return list(users)
        
    except Exception as e:
        logger.error(f"Ошибка поиска активированных пользователей по запросу '{query}': {e}")
        return []


async def search_unactivated_users_by_name(session: AsyncSession, query: str) -> List[User]:
    """
    Поиск неактивированных пользователей по ФИО (частичное совпадение, case-insensitive)
    
    Args:
        session: Сессия БД
        query: Поисковый запрос
    
    Returns:
        Список найденных неактивированных пользователей
    """
    try:
        search_pattern = f"%{query}%"
        
        result = await session.execute(
            select(User)
            .where(
                User.is_activated == False,
                User.full_name.ilike(search_pattern)
            )
            .order_by(User.registration_date.desc())
        )
        users = result.scalars().all()
        
        logger.info(f"Поиск неактивированных пользователей по запросу '{query}': найдено {len(users)}")
        return list(users)
        
    except Exception as e:
        logger.error(f"Ошибка поиска неактивированных пользователей по запросу '{query}': {e}")
        return []


async def update_user_full_name(session: AsyncSession, user_id: int, new_full_name: str, 
                               recruiter_id: int, bot=None) -> bool:
    """Обновление ФИО пользователя"""
    try:
        user = await get_user_by_id(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
            
        old_full_name = user.full_name
        
        # Обновляем ФИО
        update_stmt = update(User).where(User.id == user_id).values(full_name=new_full_name)
        await session.execute(update_stmt)
        await session.commit()
        
        # Отправляем уведомление пользователю
        if bot:
            await send_notification_about_data_change(
                session, bot, user_id, recruiter_id, 
                "ФИО", old_full_name, new_full_name
            )
        
        logger.info(f"ФИО пользователя {user_id} изменено с '{old_full_name}' на '{new_full_name}'")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления ФИО пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def update_user_phone_number(session: AsyncSession, user_id: int, new_phone_number: str, 
                                  recruiter_id: int, bot=None) -> bool:
    """Обновление телефона пользователя"""
    try:
        user = await get_user_by_id(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
            
        # Проверяем уникальность телефона
        existing_user = await get_user_by_phone(session, new_phone_number)
        if existing_user and existing_user.id != user_id:
            logger.error(f"Телефон {new_phone_number} уже используется другим пользователем")
            return False
            
        old_phone = user.phone_number
        
        # Обновляем телефон
        update_stmt = update(User).where(User.id == user_id).values(phone_number=new_phone_number)
        await session.execute(update_stmt)
        await session.commit()
        
        # Отправляем уведомление пользователю
        if bot:
            await send_notification_about_data_change(
                session, bot, user_id, recruiter_id,
                "ТЕЛЕФОН", old_phone, new_phone_number
            )
        
        logger.info(f"Телефон пользователя {user_id} изменен с '{old_phone}' на '{new_phone_number}'")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления телефона пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def update_user_role(session: AsyncSession, user_id: int, new_role_name: str, 
                          recruiter_id: int, bot=None) -> bool:
    """Безопасное обновление роли пользователя с очисткой связанных данных"""
    try:
        from database.models import Mentorship, TraineeLearningPath, TraineeTestAccess, TraineeAttestation
        
        user = await get_user_with_details(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
            
        # Получаем старую роль
        old_role_name = user.roles[0].name if user.roles else "Нет роли"
        
        # Если роль не изменяется, ничего не делаем
        if old_role_name == new_role_name:
            logger.info(f"Роль пользователя {user_id} уже {new_role_name}, изменения не требуются")
            return True
        
        # Получаем новую роль
        role_result = await session.execute(
            select(Role).where(Role.name == new_role_name)
        )
        new_role = role_result.scalar_one_or_none()
        if not new_role:
            logger.error(f"Роль {new_role_name} не найдена")
            return False
        
        # Очистка данных при смене роли
        active_mentorships = []  # Инициализируем переменную
        
        # 1. Если меняем роль С "Стажер" - деактивируем траектории и наставничество
        if old_role_name == "Стажер":
            logger.info(f"Очистка данных стажера для пользователя {user_id}")
            
            # Деактивируем траектории стажера
            await session.execute(
                update(TraineeLearningPath).where(
                    TraineeLearningPath.trainee_id == user_id,
                    TraineeLearningPath.is_active == True
                ).values(is_active=False)
            )
            
            # Деактивируем наставничество (стажер больше не стажер)
            await session.execute(
                update(Mentorship).where(
                    Mentorship.trainee_id == user_id,
                    Mentorship.is_active == True
                ).values(is_active=False)
            )
            
            # Деактивируем доступ к тестам стажера (ТОЛЬКО при смене роли рекрутером)
            # ВАЖНО: При переходе через аттестацию (change_trainee_to_employee) тесты НЕ деактивируются
            await session.execute(
                update(TraineeTestAccess).where(
                    TraineeTestAccess.trainee_id == user_id,
                    TraineeTestAccess.is_active == True
                ).values(is_active=False)
            )
            
            # КРИТИЧЕСКОЕ ДОБАВЛЕНИЕ: Деактивируем все аттестации стажера
            await session.execute(
                update(TraineeAttestation).where(
                    TraineeAttestation.trainee_id == user_id,
                    TraineeAttestation.is_active == True
                ).values(is_active=False)
            )
            
            logger.info(f"Очищены данные стажера: траектории, наставничество, доступ к тестам, аттестации")
        
        # 2. Если меняем роль С "Наставник" - деактивируем все наставничество
        if old_role_name == "Наставник":
            logger.info(f"Очистка данных наставника для пользователя {user_id}")
            
            # Получаем всех стажеров этого наставника
            mentorship_result = await session.execute(
                select(Mentorship).where(
                    Mentorship.mentor_id == user_id,
                    Mentorship.is_active == True
                )
            )
            active_mentorships = mentorship_result.scalars().all()
            
            if active_mentorships:
                logger.warning(f"ВНИМАНИЕ: Наставник {user_id} имеет {len(active_mentorships)} активных стажеров!")
                
                # Деактивируем наставничество
                await session.execute(
                    update(Mentorship).where(
                        Mentorship.mentor_id == user_id,
                        Mentorship.is_active == True
                    ).values(is_active=False)
                )
                
                logger.info(f"Деактивированы связи наставничества для {len(active_mentorships)} стажеров")
        
        # 3. Если меняем роль НА "Стажер" - очищаем старые аттестации и подготавливаем к новому назначению
        if new_role_name == "Стажер":
            logger.info(f"Пользователь {user_id} становится стажером - очистка старых данных и подготовка к назначению наставника")
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Очищаем все старые аттестации при становлении стажером
            duplicates_cleaned = await cleanup_duplicate_attestations(session, user_id)
            if duplicates_cleaned > 0:
                logger.info(f"Очищено {duplicates_cleaned} старых аттестаций при смене роли на Стажер")
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Очищаем все результаты тестов при становлении стажером
            # Это необходимо, чтобы при назначении траектории индикация была правильной
            deleted_results = await session.execute(
                delete(TestResult).where(TestResult.user_id == user_id)
            )
            if deleted_results.rowcount > 0:
                logger.info(f"Очищено {deleted_results.rowcount} результатов тестов при смене роли на Стажер")
            
        # Удаляем старую роль
        if user.roles:
            delete_stmt = delete(user_roles).where(user_roles.c.user_id == user_id)
            await session.execute(delete_stmt)
            
        # Добавляем новую роль
        insert_stmt = insert(user_roles).values(user_id=user_id, role_id=new_role.id)
        await session.execute(insert_stmt)
        
        # Обновляем дату назначения роли
        from datetime import datetime
        update_role_date_stmt = update(User).where(User.id == user_id).values(role_assigned_date=datetime.now())
        await session.execute(update_role_date_stmt)
        
        # Управление объектом стажировки
        if new_role_name != "Стажер":
            # Убираем объект стажировки для не-стажеров
            update_stmt = update(User).where(User.id == user_id).values(internship_object_id=None)
            await session.execute(update_stmt)
        
        await session.commit()
        
        # Отправляем уведомление пользователю с дополнительной информацией
        if bot:
            notification_text = f"РОЛЬ изменена с '{old_role_name}' на '{new_role_name}'"
            
            # Добавляем специальные инструкции в зависимости от смены роли
            if old_role_name == "Наставник" and len(active_mentorships) > 0:
                notification_text += f"\n\n⚠️ ВНИМАНИЕ: Твои {len(active_mentorships)} стажеров остались без наставника. Обратитесь к рекрутеру для назначения нового наставника."
            elif new_role_name == "Стажер":
                notification_text += "\n\n📋 ТРЕБУЕТСЯ: Обратитесь к рекрутеру для назначения наставника и траектории обучения."
            elif old_role_name == "Стажер":
                notification_text += "\n\n✅ Твои данные стажера (траектории, наставник) деактивированы."
            
            await send_notification_about_data_change(
                session, bot, user_id, recruiter_id,
                "РОЛЬ", old_role_name, notification_text
            )
        
        logger.info(f"Роль пользователя {user_id} безопасно изменена с '{old_role_name}' на '{new_role_name}'")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления роли пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def get_role_change_warnings(session: AsyncSession, user_id: int, old_role: str, new_role: str) -> str:
    """Получение предупреждений о последствиях смены роли"""
    try:
        from database.models import Mentorship, TraineeLearningPath, TraineeTestAccess
        
        warnings = []
        
        # Если роль не изменяется
        if old_role == new_role:
            return "✅ <b>Роль не изменится</b>"
        
        # Предупреждения при смене роли С "Стажер"
        if old_role == "Стажер":
            # Проверяем траектории
            trainee_path_result = await session.execute(
                select(TraineeLearningPath).where(
                    TraineeLearningPath.trainee_id == user_id,
                    TraineeLearningPath.is_active == True
                )
            )
            active_paths = trainee_path_result.scalars().all()
            
            if active_paths:
                warnings.append("❌<b>ПОТЕРЯ ДАННЫХ:</b> Активные траектории обучения будут деактивированы")
            
            # Проверяем наставничество
            mentorship_result = await session.execute(
                select(Mentorship).where(
                    Mentorship.trainee_id == user_id,
                    Mentorship.is_active == True
                )
            )
            active_mentorship = mentorship_result.scalar_one_or_none()
            
            if active_mentorship:
                mentor = await get_user_by_id(session, active_mentorship.mentor_id)
                warnings.append(f"❌<b>ПОТЕРЯ НАСТАВНИКА:</b> Связь с наставником {mentor.full_name} будет деактивирована")
            
            # Проверяем доступ к тестам
            test_access_result = await session.execute(
                select(TraineeTestAccess).where(
                    TraineeTestAccess.trainee_id == user_id,
                    TraineeTestAccess.is_active == True
                )
            )
            active_test_access = test_access_result.scalars().all()
            
            if active_test_access:
                warnings.append(f"❌<b>ПОТЕРЯ ДОСТУПА:</b> Доступ к {len(active_test_access)} тестам стажера будет отозван")
            
            # Проверяем аттестации
            attestations_result = await session.execute(
                select(TraineeAttestation).where(
                    TraineeAttestation.trainee_id == user_id,
                    TraineeAttestation.is_active == True
                )
            )
            active_attestations = attestations_result.scalars().all()
            
            if active_attestations:
                warnings.append(f"❌<b>ПОТЕРЯ АТТЕСТАЦИЙ:</b> {len(active_attestations)} назначенных аттестаций будут деактивированы")
        
        # Предупреждения при смене роли С "Наставник"
        if old_role == "Наставник":
            # Проверяем стажеров
            mentorship_result = await session.execute(
                select(Mentorship).where(
                    Mentorship.mentor_id == user_id,
                    Mentorship.is_active == True
                )
            )
            active_mentorships = mentorship_result.scalars().all()
            
            if active_mentorships:
                trainee_names = []
                for mentorship in active_mentorships:
                    trainee = await get_user_by_id(session, mentorship.trainee_id)
                    trainee_names.append(trainee.full_name)
                
                warnings.append(f"❌<b>КРИТИЧНО:</b> {len(active_mentorships)} стажеров останутся без наставника:")
                warnings.append(f"   • {', '.join(trainee_names)}")
                warnings.append("   • Потребуется назначение нового наставника!")
        
        # Предупреждения при смене роли НА "Стажер"
        if new_role == "Стажер":
            warnings.append("⚠️<b>ТРЕБУЕТСЯ:</b> После смены роли назначьте наставника и траекторию")
        
        # Предупреждения о потере прав доступа
        role_permissions_info = {
            "Стажер": ["прохождение тестов через траектории", "взаимодействие с наставником"],
            "Сотрудник": ["прохождение тестов от рекрутера"],
            "Наставник": ["управление стажерами", "предоставление доступа к тестам"],
            "Рекрутер": ["создание тестов", "управление пользователями", "рассылка"],
            "Руководитель": ["проведение аттестаций"]
        }
        
        old_permissions = role_permissions_info.get(old_role, [])
        new_permissions = role_permissions_info.get(new_role, [])
        
        if old_permissions:
            warnings.append(f"❌<b>ПОТЕРЯ ФУНКЦИЙ:</b> {', '.join(old_permissions)}")
        if new_permissions:
            warnings.append(f"✅<b>НОВЫЕ ФУНКЦИИ:</b> {', '.join(new_permissions)}")
        
        if warnings:
            return "<b>ПОСЛЕДСТВИЯ СМЕНЫ РОЛИ:</b>\n\n" + "\n".join(warnings) + "\n\n<b>Подтвердите изменение:</b>"
        else:
            return "✅ <b>Безопасная смена роли</b>\n\n<b>Подтвердите изменение:</b>"
            
    except Exception as e:
        logger.error(f"Ошибка получения предупреждений о смене роли: {e}")
        return "⚠️ <b>Ошибка анализа последствий</b>\n\n<b>Подтвердите изменение:</b>"


async def cleanup_duplicate_attestations(session: AsyncSession, user_id: int) -> int:
    """Очистка дублирующих аттестаций для пользователя"""
    try:
        from database.models import TraineeAttestation
        
        # Находим все активные аттестации пользователя
        attestations_result = await session.execute(
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
                    logger.info(f"Деактивировано дублирующее назначение аттестации {attestation_id} для стажера {user_id} (ID: {old_assignment.id})")
        
        if duplicates_removed > 0:
            await session.flush()
            logger.info(f"Очищено {duplicates_removed} дублирующих назначений аттестации для пользователя {user_id}")
        
        return duplicates_removed
        
    except Exception as e:
        logger.error(f"Ошибка очистки дублирующих аттестаций для пользователя {user_id}: {e}")
        return 0


async def cleanup_all_duplicate_attestations(session: AsyncSession) -> dict:
    """Глобальная очистка всех дублирующих аттестаций в системе"""
    try:
        from database.models import TraineeAttestation
        
        cleanup_report = {
            "users_processed": 0,
            "duplicates_found": 0,
            "duplicates_removed": 0,
            "affected_users": []
        }
        
        # Находим всех пользователей с активными аттестациями
        users_with_attestations_result = await session.execute(
            select(TraineeAttestation.trainee_id)
            .where(TraineeAttestation.is_active == True)
            .distinct()
        )
        user_ids = [row[0] for row in users_with_attestations_result.all()]
        
        cleanup_report["users_processed"] = len(user_ids)
        
        # Очищаем дубликаты для каждого пользователя
        for user_id in user_ids:
            duplicates_removed = await cleanup_duplicate_attestations(session, user_id)
            if duplicates_removed > 0:
                cleanup_report["duplicates_removed"] += duplicates_removed
                cleanup_report["affected_users"].append(user_id)
                
                # Получаем имя пользователя для отчета
                user = await get_user_by_id(session, user_id)
                if user:
                    logger.info(f"Очищены дубликаты аттестаций для пользователя {user.full_name} (ID: {user_id})")
        
        if cleanup_report["duplicates_removed"] > 0:
            await session.commit()
            logger.info(f"Глобальная очистка завершена: обработано {cleanup_report['users_processed']} пользователей, удалено {cleanup_report['duplicates_removed']} дубликатов")
        else:
            logger.info("Дублирующие аттестации не найдены")
        
        return cleanup_report
        
    except Exception as e:
        logger.error(f"Ошибка глобальной очистки дублирующих аттестаций: {e}")
        await session.rollback()
        return {"error": str(e)}


async def cleanup_all_duplicate_attestations_on_startup():
    """БЕЗОПАСНАЯ проверка дублирующих аттестаций при запуске системы (только диагностика)"""
    try:
        logger.info("Проверка целостности данных аттестаций...")
        async with async_session() as session:
            # БЕЗОПАСНАЯ ПРОВЕРКА: только подсчитываем дубликаты, НЕ удаляем их автоматически
            from database.models import TraineeAttestation
            
            # Находим потенциальные дубликаты
            duplicates_query = await session.execute(
                select(TraineeAttestation.trainee_id, TraineeAttestation.attestation_id, func.count())
                .where(TraineeAttestation.is_active == True)
                .group_by(TraineeAttestation.trainee_id, TraineeAttestation.attestation_id)
                .having(func.count() > 1)
            )
            duplicates = duplicates_query.all()
            
            if duplicates:
                logger.warning(f"⚠️ ОБНАРУЖЕНЫ ДУБЛИКАТЫ: {len(duplicates)} групп дублирующих аттестаций")
                for trainee_id, attestation_id, count in duplicates:
                    user = await get_user_by_id(session, trainee_id)
                    user_name = user.full_name if user else f"ID:{trainee_id}"
                    logger.warning(f"   • Стажер {user_name}: {count} назначений аттестации {attestation_id}")
                logger.info("💡 Для очистки используй команду администратора или редактор пользователя")
            # else:
            #     logger.info("✅ Дублирующие аттестации не найдены - целостность данных в порядке")  # Проверка пройдена
                
    except Exception as e:
        logger.error(f"Ошибка при проверке целостности аттестаций: {e}")


async def verify_role_system_integrity(session: AsyncSession) -> dict:
    """Проверка целостности системы ролей и связанных данных"""
    try:
        integrity_report = {
            "roles_count": 0,
            "users_count": 0,
            "mentorships_count": 0,
            "trajectories_count": 0,
            "orphaned_trainees": [],
            "mentors_without_trainees": [],
            "trainees_without_mentors": [],
            "role_distribution": {}
        }
        
        # Подсчет ролей
        roles_result = await session.execute(select(Role))
        all_roles = roles_result.scalars().all()
        integrity_report["roles_count"] = len(all_roles)
        
        # Подсчет пользователей по ролям
        for role in all_roles:
            users_with_role_result = await session.execute(
                select(func.count()).select_from(User)
                .join(user_roles, User.id == user_roles.c.user_id)
                .where(user_roles.c.role_id == role.id)
            )
            count = users_with_role_result.scalar()
            integrity_report["role_distribution"][role.name] = count
        
        integrity_report["users_count"] = sum(integrity_report["role_distribution"].values())
        
        # Проверка наставничества
        active_mentorships_result = await session.execute(
            select(Mentorship).where(Mentorship.is_active == True)
        )
        active_mentorships = active_mentorships_result.scalars().all()
        integrity_report["mentorships_count"] = len(active_mentorships)
        
        # Проверка траекторий
        active_paths_result = await session.execute(
            select(TraineeLearningPath).where(TraineeLearningPath.is_active == True)
        )
        active_paths = active_paths_result.scalars().all()
        integrity_report["trajectories_count"] = len(active_paths)
        
        # Поиск проблем
        
        # 1. Стажеры без наставника
        trainees_result = await session.execute(
            select(User).join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, user_roles.c.role_id == Role.id)
            .where(Role.name == "Стажер")
        )
        all_trainees = trainees_result.scalars().all()
        
        for trainee in all_trainees:
            mentorship_check = await session.execute(
                select(Mentorship).where(
                    Mentorship.trainee_id == trainee.id,
                    Mentorship.is_active == True
                )
            )
            if not mentorship_check.scalar_one_or_none():
                integrity_report["trainees_without_mentors"].append({
                    "id": trainee.id,
                    "name": trainee.full_name,
                    "tg_id": trainee.tg_id
                })
        
        # 2. Наставники без стажеров
        mentors_result = await session.execute(
            select(User).join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, user_roles.c.role_id == Role.id)
            .where(Role.name == "Наставник")
        )
        all_mentors = mentors_result.scalars().all()
        
        for mentor in all_mentors:
            mentorship_check = await session.execute(
                select(Mentorship).where(
                    Mentorship.mentor_id == mentor.id,
                    Mentorship.is_active == True
                )
            )
            if not mentorship_check.scalars().all():
                integrity_report["mentors_without_trainees"].append({
                    "id": mentor.id,
                    "name": mentor.full_name,
                    "tg_id": mentor.tg_id
                })
        
        return integrity_report
        
    except Exception as e:
        logger.error(f"Ошибка проверки целостности системы ролей: {e}")
        return {"error": str(e)}


async def update_user_group(session: AsyncSession, user_id: int, new_group_id: int, 
                           recruiter_id: int, bot=None) -> bool:
    """Обновление группы пользователя"""
    try:
        user = await get_user_with_details(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
            
        # Получаем старую группу
        old_group_name = user.groups[0].name if user.groups else "Нет группы"
        
        # Получаем новую группу
        new_group = await get_group_by_id(session, new_group_id)
        if not new_group:
            logger.error(f"Группа {new_group_id} не найдена")
            return False
            
        # Удаляем старую группу
        if user.groups:
            delete_stmt = delete(user_groups).where(user_groups.c.user_id == user_id)
            await session.execute(delete_stmt)
            
        # Добавляем новую группу
        insert_stmt = insert(user_groups).values(user_id=user_id, group_id=new_group_id)
        await session.execute(insert_stmt)
        await session.commit()
        
        # Отправляем уведомление пользователю
        if bot:
            await send_notification_about_data_change(
                session, bot, user_id, recruiter_id,
                "ГРУППА", old_group_name, new_group.name
            )
        
        logger.info(f"Группа пользователя {user_id} изменена с '{old_group_name}' на '{new_group.name}'")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления группы пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def update_user_internship_object(session: AsyncSession, user_id: int, 
                                       new_object_id: int, recruiter_id: int, bot=None) -> bool:
    """Обновление объекта стажировки пользователя"""
    try:
        user = await get_user_with_details(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
            
        # Получаем старый объект
        old_object_name = user.internship_object.name if user.internship_object else "Не назначен"
        
        # Получаем новый объект
        new_object = await get_object_by_id(session, new_object_id)
        if not new_object:
            logger.error(f"Объект {new_object_id} не найден")
            return False
            
        # Обновляем объект стажировки
        update_stmt = update(User).where(User.id == user_id).values(internship_object_id=new_object_id)
        await session.execute(update_stmt)
        await session.commit()
        
        # Отправляем уведомление пользователю
        if bot:
            await send_notification_about_data_change(
                session, bot, user_id, recruiter_id,
                "ОБЪЕКТ СТАЖИРОВКИ", old_object_name, new_object.name
            )
        
        logger.info(f"Объект стажировки пользователя {user_id} изменен с '{old_object_name}' на '{new_object.name}'")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления объекта стажировки пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def update_user_work_object(session: AsyncSession, user_id: int, 
                                 new_object_id: int, recruiter_id: int, bot=None) -> bool:
    """Обновление объекта работы пользователя"""
    try:
        user = await get_user_with_details(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
            
        # Получаем старый объект
        old_object_name = user.work_object.name if user.work_object else "Не назначен"
        
        # Получаем новый объект
        new_object = await get_object_by_id(session, new_object_id)
        if not new_object:
            logger.error(f"Объект {new_object_id} не найден")
            return False
            
        # Обновляем объект работы
        update_stmt = update(User).where(User.id == user_id).values(work_object_id=new_object_id)
        await session.execute(update_stmt)
        await session.commit()
        
        # Отправляем уведомление пользователю
        if bot:
            await send_notification_about_data_change(
                session, bot, user_id, recruiter_id,
                "ОБЪЕКТ РАБОТЫ", old_object_name, new_object.name
            )
        
        logger.info(f"Объект работы пользователя {user_id} изменен с '{old_object_name}' на '{new_object.name}'")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления объекта работы пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def send_notification_about_data_change(session: AsyncSession, bot, user_id: int,
                                             recruiter_id: int, field_name: str, 
                                             old_value: str, new_value: str):
    """Отправка уведомления пользователю об изменении его данных"""
    try:
        # Получаем данные пользователя
        user = await get_user_by_id(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
            
        # Получаем данные рекрутера
        recruiter = await get_user_by_id(session, recruiter_id)
        if not recruiter:
            logger.error(f"Рекрутер {recruiter_id} не найден")
            return False
        
        # Специальная обработка для ролевых уведомлений (роль, группа, объекты)
        if field_name in ["РОЛЬ", "ГРУППА", "ОБЪЕКТ СТАЖИРОВКИ", "ОБЪЕКТ РАБОТЫ"]:
            if field_name == "РОЛЬ":
                # new_value уже содержит полный текст с предупреждениями
                notification_text = f"""‼️Твои данные изменены:


{new_value}


Изменение внес: Рекрутер - {recruiter.full_name}"""
            else:
                # Для группы и объектов используем новый формат
                notification_text = f"""‼️Твои данные изменены:


{field_name} изменена с '{old_value}' на '{new_value}'


Изменение внес: Рекрутер - {recruiter.full_name}"""
        else:
            # Старый формат для ФИО и телефона
                notification_text = f"""❗️Твои данные изменены:
Рекрутер - {recruiter.full_name}
⚠️НОВЫЙ {field_name}:
⚠️{new_value}"""

        # Создаем клавиатуру с кнопкой "Перезагрузка" для ролевых уведомлений
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        if field_name in ["РОЛЬ", "ГРУППА", "ОБЪЕКТ СТАЖИРОВКИ", "ОБЪЕКТ РАБОТЫ"]:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Перезагрузка", callback_data="reload_menu")]
            ])
            await bot.send_message(chat_id=user.tg_id, text=notification_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=user.tg_id, text=notification_text, parse_mode="HTML")
            
        logger.info(f"Уведомление об изменении {field_name} отправлено пользователю {user.tg_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об изменении данных пользователю {user_id}: {e}")
        return False


async def migrate_new_tables():
    """Миграция новых таблиц для траекторий обучения"""
    try:
        logger.info("Начинаем миграцию новых таблиц для траекторий...")
        async with engine.begin() as conn:
            # Создаем новые таблицы если их нет
            await conn.run_sync(Base.metadata.create_all)
            
            # Добавляем столбец role_assigned_date если его нет
            try:
                await conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS role_assigned_date TIMESTAMP DEFAULT NOW()
                """))
                # logger.info("✅ Столбец role_assigned_date добавлен в таблицу users")  # Миграция применена
            except Exception as e:
                logger.info(f"Столбец role_assigned_date уже существует или ошибка: {e}")
            
            # Миграция: делаем поля создателя nullable для корректного удаления пользователей
            try:
                await conn.execute(text("ALTER TABLE groups ALTER COLUMN created_by_id DROP NOT NULL"))
                # logger.info("✅ groups.created_by_id теперь nullable")  # Миграция применена
            except Exception as e:
                logger.info(f"groups.created_by_id уже nullable или ошибка: {e}")
                
            try:
                await conn.execute(text("ALTER TABLE objects ALTER COLUMN created_by_id DROP NOT NULL"))
                # logger.info("✅ objects.created_by_id теперь nullable")  # Миграция применена
            except Exception as e:
                logger.info(f"objects.created_by_id уже nullable или ошибка: {e}")
                
            try:
                await conn.execute(text("ALTER TABLE tests ALTER COLUMN creator_id DROP NOT NULL"))
                # logger.info("✅ tests.creator_id теперь nullable")  # Миграция применена
            except Exception as e:
                logger.info(f"tests.creator_id уже nullable или ошибка: {e}")
                
            try:
                await conn.execute(text("ALTER TABLE learning_paths ALTER COLUMN created_by_id DROP NOT NULL"))
                # logger.info("✅ learning_paths.created_by_id теперь nullable")  # Миграция применена
            except Exception as e:
                logger.info(f"learning_paths.created_by_id уже nullable или ошибка: {e}")
                
            try:
                await conn.execute(text("ALTER TABLE attestations ALTER COLUMN created_by_id DROP NOT NULL"))
                # logger.info("✅ attestations.created_by_id теперь nullable")  # Миграция применена
            except Exception as e:
                logger.info(f"attestations.created_by_id уже nullable или ошибка: {e}")
                
            try:
                await conn.execute(text("ALTER TABLE knowledge_folders ALTER COLUMN created_by_id DROP NOT NULL"))
                # logger.info("✅ knowledge_folders.created_by_id теперь nullable")  # Миграция применена
            except Exception as e:
                logger.info(f"knowledge_folders.created_by_id уже nullable или ошибка: {e}")
                
            try:
                await conn.execute(text("ALTER TABLE knowledge_materials ALTER COLUMN created_by_id DROP NOT NULL"))
                # logger.info("✅ knowledge_materials.created_by_id теперь nullable")  # Миграция применена
            except Exception as e:
                logger.info(f"knowledge_materials.created_by_id уже nullable или ошибка: {e}")
            
            # Миграция: добавляем поле material_type для тестов
            try:
                await conn.execute(text("ALTER TABLE tests ADD COLUMN IF NOT EXISTS material_type VARCHAR(20)"))
                # logger.info("✅ tests.material_type добавлен")  # Миграция применена
            except Exception as e:
                logger.info(f"tests.material_type уже существует или ошибка: {e}")
                
        # logger.info("✅ Миграция новых таблиц для траекторий ЗАВЕРШЕНА УСПЕШНО")  # Миграции выполнены
    except Exception as e:
        logger.error(f"❌ ОШИБКА МИГРАЦИИ новых таблиц: {type(e).__name__}: {e}")


# ====================== ТРАЕКТОРИИ ОБУЧЕНИЯ ======================

async def create_attestation(session: AsyncSession, name: str, passing_score: float, 
                           creator_id: int) -> Optional[Attestation]:
    """Создание новой аттестации"""
    try:
        attestation = Attestation(
            name=name,
            passing_score=passing_score,
            max_score=0,  # Будет обновлено при добавлении вопросов
            created_by_id=creator_id
        )
        
        session.add(attestation)
        await session.flush()
        await session.commit()
        
        logger.info(f"Аттестация '{name}' создана с ID: {attestation.id}")
        return attestation
        
    except Exception as e:
        logger.error(f"Ошибка создания аттестации: {e}")
        await session.rollback()
        
        return None


async def add_attestation_question(session: AsyncSession, attestation_id: int, 
                                 question_text: str, max_points: float,
                                 question_number: int) -> Optional[AttestationQuestion]:
    """Добавление вопроса к аттестации"""
    try:
        question = AttestationQuestion(
            attestation_id=attestation_id,
            question_number=question_number,
            question_text=question_text,
            max_points=max_points
        )
        
        session.add(question)
        await session.flush()
        
        # Обновляем максимальный балл аттестации
        attestation = await session.get(Attestation, attestation_id)
        if attestation:
            attestation.max_score += max_points
            
        await session.commit()
        
        logger.info(f"Вопрос добавлен к аттестации {attestation_id}")
        return question
        
    except Exception as e:
        logger.error(f"Ошибка добавления вопроса к аттестации: {e}")
        await session.rollback()
        return None


async def get_all_attestations(session: AsyncSession) -> List[Attestation]:
    """Получение всех аттестаций"""
    try:
        # Временно создаем пустой список пока таблица не создана
        try:
            result = await session.execute(
                select(Attestation)
                .options(selectinload(Attestation.questions))
                .where(Attestation.is_active == True)
                .order_by(Attestation.created_date.desc())
            )
            attestations = result.scalars().all()
            return list(attestations)
        except Exception as table_error:
            logger.error(f"Ошибка получения аттестаций (таблица не существует?): {table_error}")
            return []
        
    except Exception as e:
        logger.error(f"Ошибка получения аттестаций: {e}")
        return []


async def save_trajectory_to_database(session: AsyncSession, trajectory_data: dict) -> Optional[LearningPath]:
    """Сохранение траектории в базу данных"""
    try:
        # Валидация обязательных полей
        if not trajectory_data.get('name'):
            logger.error("Отсутствует название траектории")
            return None
        if not trajectory_data.get('group_id'):
            logger.error("Отсутствует group_id для траектории")
            return None
        if not trajectory_data.get('created_by_id'):
            logger.error("Отсутствует created_by_id для траектории")
            return None
            
        logger.info(f"Сохранение траектории: name={trajectory_data['name']}, group_id={trajectory_data['group_id']}, created_by_id={trajectory_data['created_by_id']}")
        
        try:
            # Создаем траекторию
            learning_path = LearningPath(
                name=trajectory_data['name'],
                description=trajectory_data.get('description', ''),
                group_id=trajectory_data['group_id'],  # Обязательное поле
                created_by_id=trajectory_data['created_by_id']  # Обязательное поле
            )
            
            session.add(learning_path)
            await session.flush()
            logger.info(f"LearningPath создан с ID: {learning_path.id}")
            
            # Создаем этапы
            for stage_data in trajectory_data.get('stages', []):
                logger.info(f"Создание этапа: {stage_data['name']}, order: {stage_data['order']}")
                stage = LearningStage(
                    name=stage_data['name'],
                    learning_path_id=learning_path.id,
                    order_number=stage_data['order']
                )
                session.add(stage)
                await session.flush()
                logger.info(f"Этап создан с ID: {stage.id}")
                
                # Создаем сессии для этапа
                for session_data in stage_data.get('sessions', []):
                    logger.info(f"Создание сессии: {session_data['name']}, order: {session_data['order']}")
                    learning_session = LearningSession(
                        name=session_data['name'],
                        stage_id=stage.id,
                        order_number=session_data['order']
                    )
                    session.add(learning_session)
                    await session.flush()
                    logger.info(f"Сессия создана с ID: {learning_session.id}")
                    
                    # Привязываем тесты к сессии
                    for test_data in session_data.get('tests', []):
                        logger.info(f"Привязка теста ID:{test_data['id']} к сессии ID:{learning_session.id}")
                        stmt = insert(session_tests).values(
                            session_id=learning_session.id,
                            test_id=test_data['id'],
                            order_number=test_data['order']
                        )
                        await session.execute(stmt)
            
            await session.commit()
            logger.info(f"Траектория '{trajectory_data['name']}' УСПЕШНО СОХРАНЕНА с ID: {learning_path.id}")
            return learning_path
            
        except Exception as table_error:
            # Логируем детальную ошибку для диагностики
            logger.error(f"ОШИБКА СОХРАНЕНИЯ ТРАЕКТОРИИ: {type(table_error).__name__}: {table_error}")
            logger.error(f"Данные траектории: {trajectory_data}")
            
            # Если таблицы не созданы, создаем mock объект
            if "relation" in str(table_error) and "does not exist" in str(table_error):
                logger.warning("Таблицы траекторий еще не созданы в БД")
            else:
                logger.error("Неизвестная ошибка при сохранении траектории")
            
            return None
        
    except Exception as e:
        logger.error(f"Ошибка сохранения траектории: {e}")
        await session.rollback()
        return None


async def save_trajectory_with_attestation_and_group(session: AsyncSession, trajectory_data: dict,
                                                   attestation_id: int, group_id: int) -> bool:
    """Сохранение траектории с аттестацией и привязкой к группе"""
    try:
        # Добавляем недостающие данные
        trajectory_data['group_id'] = group_id
        trajectory_data['attestation_id'] = attestation_id
        
        # Создаем траекторию
        learning_path = await save_trajectory_to_database(session, trajectory_data)
        if not learning_path:
            return False
            
            
        # Обновляем аттестацию, привязывая её к траектории
        if attestation_id:
            update_stmt = update(LearningPath).where(
                LearningPath.id == learning_path.id
            ).values(attestation_id=attestation_id)
            await session.execute(update_stmt)
            await session.commit()
        
        logger.info(f"Траектория {learning_path.id} привязана к группе {group_id} и аттестации {attestation_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка привязки траектории к группе и аттестации: {e}")
        await session.rollback()
        return False


async def get_all_learning_paths(session: AsyncSession) -> List[LearningPath]:
    """Получение всех траекторий обучения"""
    try:
        # Временно возвращаем пустой список пока таблицы не созданы
        try:
            result = await session.execute(
                select(LearningPath)
                .options(
                    selectinload(LearningPath.stages)
                    .selectinload(LearningStage.sessions)
                    .selectinload(LearningSession.tests),
                    selectinload(LearningPath.group),
                    selectinload(LearningPath.attestation)
                )
                .where(LearningPath.is_active == True)
                .order_by(LearningPath.created_date.desc())
            )
            paths = result.scalars().all()
            return list(paths)
        except Exception as table_error:
            # Если таблицы не существуют, возвращаем пустой список
            logger.warning(f"Таблицы траекторий еще не созданы: {table_error}")
            return []
        
    except Exception as e:
        logger.error(f"Ошибка получения траекторий: {e}")
        return []


async def get_learning_path_by_id(session: AsyncSession, path_id: int) -> Optional[LearningPath]:
    """Получение траектории по ID с полными данными"""
    try:
        result = await session.execute(
            select(LearningPath)
            .options(
                selectinload(LearningPath.stages)
                .selectinload(LearningStage.sessions)
                .selectinload(LearningSession.tests),
                selectinload(LearningPath.group),
                selectinload(LearningPath.attestation)
                .selectinload(Attestation.questions)
            )
            .where(LearningPath.id == path_id)
        )
        return result.scalar_one_or_none()
        
    except Exception as e:
        logger.error(f"Ошибка получения траектории {path_id}: {e}")
        return None


async def get_learning_paths_by_group(session: AsyncSession, group_id: int) -> List[LearningPath]:
    """Получение траекторий по группе"""
    try:
        result = await session.execute(
            select(LearningPath)
            .options(
                selectinload(LearningPath.stages)
                .selectinload(LearningStage.sessions)
                .selectinload(LearningSession.tests)
            )
            .where(LearningPath.group_id == group_id)
            .where(LearningPath.is_active == True)
            .order_by(LearningPath.created_date.desc())
        )
        paths = result.scalars().all()
        return list(paths)
        
    except Exception as e:
        logger.error(f"Ошибка получения траекторий для группы {group_id}: {e}")
        return []


async def deactivate_learning_path(session: AsyncSession, path_id: int) -> bool:
    """Деактивация траектории обучения (мягкое удаление)"""
    try:
        update_stmt = update(LearningPath).where(
            LearningPath.id == path_id
        ).values(is_active=False)
        
        await session.execute(update_stmt)
        await session.commit()
        
        logger.info(f"Траектория {path_id} деактивирована")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка удаления траектории {path_id}: {e}")
        await session.rollback()
        return False


async def get_attestation_by_id(session: AsyncSession, attestation_id: int) -> Optional[Attestation]:
    """Получение аттестации по ID с вопросами"""
    try:
        result = await session.execute(
            select(Attestation)
            .options(selectinload(Attestation.questions))
            .where(Attestation.id == attestation_id)
        )
        return result.scalar_one_or_none()

    except Exception as e:
        logger.error(f"Ошибка получения аттестации {attestation_id}: {e}")
        return None


async def check_attestation_in_use(session: AsyncSession, attestation_id: int) -> bool:
    """Проверка, используется ли аттестация в траекториях"""
    try:
        from sqlalchemy import select
        from database.models import LearningPath
        
        # Проверяем, есть ли траектории с данной аттестацией
        result = await session.execute(
            select(LearningPath).where(LearningPath.attestation_id == attestation_id)
        )
        learning_paths = result.scalars().all()
        
        logger.info(f"Проверка использования аттестации {attestation_id}: найдено {len(learning_paths)} траекторий")
        return len(learning_paths) > 0
        
    except Exception as e:
        logger.error(f"Ошибка проверки использования аттестации {attestation_id}: {e}")
        return True  # В случае ошибки считаем, что аттестация используется (безопасно)


async def delete_attestation(session: AsyncSession, attestation_id: int) -> bool:
    """Удаление аттестации"""
    try:
        from sqlalchemy import select, delete
        from database.models import Attestation, AttestationQuestion
        
        # Сначала проверяем, не используется ли аттестация
        if await check_attestation_in_use(session, attestation_id):
            logger.warning(f"Попытка удалить используемую аттестацию {attestation_id}")
            return False
        
        # Получаем аттестацию для логирования
        result = await session.execute(
            select(Attestation).where(Attestation.id == attestation_id)
        )
        attestation = result.scalar_one_or_none()
        
        if not attestation:
            logger.warning(f"Аттестация {attestation_id} не найдена для удаления")
            return False
        
        # Удаляем все вопросы аттестации
        await session.execute(
            delete(AttestationQuestion).where(AttestationQuestion.attestation_id == attestation_id)
        )
        
        # Удаляем саму аттестацию
        await session.execute(
            delete(Attestation).where(Attestation.id == attestation_id)
        )
        
        await session.commit()
        
        logger.info(f"Аттестация '{attestation.name}' (ID: {attestation_id}) успешно удалена")
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка удаления аттестации {attestation_id}: {e}")
        return False 

async def get_trajectories_using_attestation(session: AsyncSession, attestation_id: int) -> List[str]:
    """Получение названий траекторий, использующих данную аттестацию"""
    try:
        from sqlalchemy import select
        from database.models import LearningPath
        
        # Получаем траектории с данной аттестацией
        result = await session.execute(
            select(LearningPath).where(LearningPath.attestation_id == attestation_id)
        )
        learning_paths = result.scalars().all()
        
        # Извлекаем названия траекторий
        trajectory_names = []
        for path in learning_paths:
            if hasattr(path, 'name') and path.name:
                trajectory_names.append(path.name)
            else:
                # Fallback для mock объектов
                trajectory_names.append(f"Траектория {path.id}")
        
        logger.info(f"Получены названия траекторий для аттестации {attestation_id}: {trajectory_names}")
        return trajectory_names
        
    except Exception as e:
        logger.error(f"Ошибка получения названий траекторий для аттестации {attestation_id}: {e}")
        return ["Неизвестные траектории"]  # Fallback в случае ошибки

async def get_user_objects(session: AsyncSession, user_id: int) -> List[Object]:
    """Получение всех объектов пользователя"""
    try:
        result = await session.execute(
            select(Object).join(user_objects).where(
                user_objects.c.user_id == user_id,
                Object.is_active == True
            ).order_by(Object.name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения объектов пользователя {user_id}: {e}")
        return []


# ===== ФУНКЦИИ ДЛЯ ПРОХОЖДЕНИЯ ТРАЕКТОРИЙ СТАЖЕРАМИ =====

async def get_trainees_without_mentor(session: AsyncSession) -> List[User]:
    """Получение списка стажеров без наставника"""
    try:
        from database.models import User, Role, Mentorship

        # Получаем роль стажера
        trainee_role_result = await session.execute(
            select(Role).where(Role.name == "Стажер")
        )
        trainee_role = trainee_role_result.scalar_one_or_none()

        if not trainee_role:
            return []

        # Получаем стажеров без активного наставника
        result = await session.execute(
            select(User).where(
                User.is_active == True,
                User.is_activated == True
            ).join(user_roles).where(
                user_roles.c.role_id == trainee_role.id
            ).outerjoin(
                Mentorship,
                (Mentorship.trainee_id == User.id) & (Mentorship.is_active == True)
            ).where(
                Mentorship.id.is_(None)  # Нет активного наставника
            ).order_by(User.full_name)
        )

        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения стажеров без наставника: {e}")
        return []


async def get_available_mentors_for_trainee(session: AsyncSession, trainee_id: int) -> List[User]:
    """Получение доступных наставников для стажера"""
    try:
        from database.models import User, Role, Mentorship

        # Получаем стажера для определения его объекта работы
        trainee_result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы стажера
                selectinload(User.internship_object)  # Загружаем объект стажировки стажера
            )
            .where(User.id == trainee_id)
        )
        trainee = trainee_result.scalar_one_or_none()

        if not trainee or not trainee.work_object:
            return []

        # Получаем роли наставника и руководителя
        mentor_roles_result = await session.execute(
            select(Role).where(Role.name.in_(["Наставник", "Руководитель"]))
        )
        mentor_roles = mentor_roles_result.scalars().all()
        mentor_role_ids = [role.id for role in mentor_roles]

        # Получаем наставников, которые работают на том же объекте
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы наставника
                selectinload(User.internship_object)  # Загружаем объект стажировки наставника
            )
            .where(
                User.is_active == True,
                User.work_object_id == trainee.work_object_id
            ).join(user_roles).where(
                user_roles.c.role_id.in_(mentor_role_ids)
            ).order_by(User.full_name)
        )

        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения доступных наставников для стажера {trainee_id}: {e}")
        return []


async def assign_mentor_to_trainee(session: AsyncSession, trainee_id: int, mentor_id: int, recruiter_id: int, bot=None) -> bool:
    """Назначение наставника стажеру"""
    try:
        from database.models import Mentorship, User

        # Проверяем, что стажер существует и активен
        trainee_result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы
                selectinload(User.internship_object)  # Загружаем объект стажировки
            )
            .where(
                User.id == trainee_id,
                User.is_active == True,
                User.is_activated == True
            )
        )
        trainee = trainee_result.scalar_one_or_none()

        if not trainee:
            logger.error(f"Стажер {trainee_id} не найден или неактивен")
            return False

        # Проверяем, что наставник существует и активен
        mentor_result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),  # Загружаем объект работы
                selectinload(User.internship_object)  # Загружаем объект стажировки
            )
            .where(
                User.id == mentor_id,
                User.is_active == True
            )
        )
        mentor = mentor_result.scalar_one_or_none()

        if not mentor:
            logger.error(f"Наставник {mentor_id} не найден или неактивен")
            return False

        # Деактивируем существующие наставничества стажера
        await session.execute(
            update(Mentorship).where(
                Mentorship.trainee_id == trainee_id,
                Mentorship.is_active == True
            ).values(is_active=False)
        )

        # Создаем новое наставничество
        mentorship = Mentorship(
            mentor_id=mentor_id,
            trainee_id=trainee_id,
            assigned_by_id=recruiter_id,
            is_active=True
        )

        session.add(mentorship)
        await session.commit()

        # Отправляем уведомления
        await send_mentor_assigned_notification(session, trainee_id, mentor_id, recruiter_id, bot)

        logger.info(f"Наставник {mentor_id} назначен стажеру {trainee_id} рекрутером {recruiter_id}")
        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка назначения наставника {mentor_id} стажеру {trainee_id}: {e}")
        return False


async def send_mentor_assigned_notification(session: AsyncSession, trainee_id: int, mentor_id: int, recruiter_id: int, bot=None) -> None:
    """Отправка уведомлений о назначении наставника"""
    if not bot:
        logger.warning("Bot instance not provided to send_mentor_assigned_notification")
        return
        
    try:
        from database.models import User

        # Получаем данные пользователей с загрузкой связанных объектов
        trainee_result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),
                selectinload(User.internship_object)
            )
            .where(User.id == trainee_id)
        )
        mentor_result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),
                selectinload(User.internship_object)
            )
            .where(User.id == mentor_id)
        )
        recruiter_result = await session.execute(
            select(User)
            .options(
                selectinload(User.work_object),
                selectinload(User.internship_object)
            )
            .where(User.id == recruiter_id)
        )

        trainee = trainee_result.scalar_one_or_none()
        mentor = mentor_result.scalar_one_or_none()
        recruiter = recruiter_result.scalar_one_or_none()

        if not trainee or not mentor or not recruiter:
            return

        # Уведомление стажеру
        trainee_message = (
            "👨‍🏫 <b>Тебе назначен наставник!</b>\n\n"
            f"👤 <b>Наставник:</b> {mentor.full_name}\n"
            f"📞 <b>Телефон:</b> {mentor.phone_number}\n"
            f"📧 <b>Telegram:</b> @{mentor.username if mentor.username else 'не указан'}\n"
            f"📍<b>2️⃣Объект работы наставника:</b> {mentor.work_object.name if mentor.work_object else 'Не указан'}\n\n"
            f"🏢 <b>Информация об объектах:</b>\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
            f"📅 <b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y')}\n"
            f"👤 <b>Назначил:</b> {recruiter.full_name} - Рекрутер\n\n"
            "💡 <b>Что делать дальше?</b>\n"
            "• Свяжитесь со своим наставником для знакомства\n"
            "• Обсудите план обучения и цели стажировки\n"
            "• Получите доступ к необходимым тестам\n"
            "• Задавайте вопросы и обращайтесь за помощью\n\n"
            "🎯 <b>Успехов в обучении!</b>"
        )

        # Уведомление наставнику
        mentor_message = (
            "👨‍🏫 <b>Тебе назначен новый стажёр!</b>\n\n"
            f"👤 <b>Стажёр:</b> {trainee.full_name}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
            "📋 <b>Контактная информация:</b>\n"
            f"📞 Телефон: {trainee.phone_number}\n"
            f"📧 Telegram: @{trainee.username if trainee.username else 'не указан'}\n"
            f"📅 Дата регистрации: {trainee.registration_date.strftime('%d.%m.%Y')}\n"
            f"👤 Назначил: {recruiter.full_name} - Рекрутер\n\n"
            "💡 <b>Что делать дальше?</b>\n"
            "• Свяжитесь со стажёром для знакомства\n"
            "• Обсудите план обучения и цели стажировки\n"
            "• Предоставьте доступ к необходимым тестам\n"
            "• Отслеживайте прогресс обучения\n"
            "• Помогайте с вопросами и заданиями\n\n"
            "🎯 <b>Успехов в наставничестве!</b>"
        )

        # Отправляем уведомления
        try:
            await bot.send_message(
                trainee.tg_id,
                trainee_message,
                parse_mode="HTML"
            )
            await bot.send_message(
                mentor.tg_id,
                mentor_message,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="💬 Написать стажёру", url=f"tg://user?id={trainee.tg_id}"),
                        InlineKeyboardButton(text="👥 Мои стажёры", callback_data="my_trainees")
                    ],
                    [
                        InlineKeyboardButton(text="🗺️ Назначить траекторию", callback_data="assign_trajectory")
                    ]
                ])
            )
            logger.info(f"Отправлены уведомления о назначении наставника {mentor_id} стажеру {trainee_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомления: {e}")

        logger.info(f"Отправлены уведомления о назначении наставника {mentor_id} стажеру {trainee_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомлений о назначении наставника: {e}")




async def assign_learning_path_to_trainee(session: AsyncSession, trainee_id: int, learning_path_id: int, mentor_id: int, bot=None) -> bool:
    """Назначение траектории обучения стажеру"""
    try:
        from database.models import TraineeLearningPath, LearningPath, LearningStage, TraineeStageProgress, TraineeSessionProgress

        # Проверяем существование стажера и траектории
        trainee_result = await session.execute(select(User).where(User.id == trainee_id))
        learning_path_result = await session.execute(select(LearningPath).where(LearningPath.id == learning_path_id))

        trainee = trainee_result.scalar_one_or_none()
        learning_path = learning_path_result.scalar_one_or_none()

        if not trainee or not learning_path:
            logger.error(f"Стажер {trainee_id} или траектория {learning_path_id} не найдены")
            return False

        # Деактивируем существующие назначения траекторий стажеру
        await session.execute(
            update(TraineeLearningPath).where(
                TraineeLearningPath.trainee_id == trainee_id,
                TraineeLearningPath.is_active == True
            ).values(is_active=False)
        )
        
        # Удаляем результаты тестов из старой траектории (если есть)
        await delete_trajectory_test_results(session, trainee_id, learning_path_id)

        # Создаем новое назначение траектории
        trainee_path = TraineeLearningPath(
            trainee_id=trainee_id,
            learning_path_id=learning_path_id,
            assigned_by_id=mentor_id,
            is_active=True
        )

        session.add(trainee_path)
        await session.commit()

        # Создаем прогресс по этапам и сессиям
        await _create_trainee_progress(session, trainee_path.id, learning_path_id)

        # Отправляем уведомление стажеру
        await send_learning_path_assigned_notification(session, trainee_id, learning_path_id, bot)

        logger.info(f"Траектория {learning_path_id} назначена стажеру {trainee_id} наставником {mentor_id}")
        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка назначения траектории {learning_path_id} стажеру {trainee_id}: {e}")
        return False


async def _create_trainee_progress(session: AsyncSession, trainee_path_id: int, learning_path_id: int) -> None:
    """Создание структуры прогресса для стажера"""
    try:
        from database.models import LearningStage, LearningSession, TraineeStageProgress, TraineeSessionProgress

        # Получаем этапы траектории
        stages_result = await session.execute(
            select(LearningStage).where(LearningStage.learning_path_id == learning_path_id).order_by(LearningStage.order_number)
        )
        stages = stages_result.scalars().all()

        for stage in stages:
            # Создаем прогресс по этапу
            stage_progress = TraineeStageProgress(
                trainee_path_id=trainee_path_id,
                stage_id=stage.id,
                is_opened=False,  # По умолчанию этапы закрыты
                is_completed=False
            )
            session.add(stage_progress)
            await session.commit()

            # Получаем сессии этапа
            sessions_result = await session.execute(
                select(LearningSession).where(LearningSession.stage_id == stage.id).order_by(LearningSession.order_number)
            )
            sessions = sessions_result.scalars().all()

            for session_obj in sessions:
                # Создаем прогресс по сессии
                session_progress = TraineeSessionProgress(
                    stage_progress_id=stage_progress.id,
                    session_id=session_obj.id,
                    is_opened=False,  # По умолчанию сессии закрыты
                    is_completed=False
                )
                session.add(session_progress)

        await session.commit()
        logger.info(f"Создана структура прогресса для траектории {learning_path_id}")

    except Exception as e:
        logger.error(f"Ошибка создания структуры прогресса: {e}")


async def send_learning_path_assigned_notification(session: AsyncSession, trainee_id: int, learning_path_id: int, bot=None) -> None:
    """Отправка уведомления стажеру о назначении траектории"""
    try:
        from database.models import User, LearningPath

        # Получаем данные
        trainee_result = await session.execute(select(User).where(User.id == trainee_id))
        learning_path_result = await session.execute(select(LearningPath).where(LearningPath.id == learning_path_id))

        trainee = trainee_result.scalar_one_or_none()
        learning_path = learning_path_result.scalar_one_or_none()

        if not trainee or not learning_path:
            return

        # Уведомление стажеру согласно ТЗ шаг 6
        message = (
            "🗺️<b>Тебе доступна траектория обучения!</b>\n"
            "Чтобы ознакомиться с ней нажми кнопку \"Траектория\" в меню или используй команду /trajectory"
        )

        # Отправляем уведомление стажеру
        if not bot:
            logger.warning("Bot instance not provided to send_learning_path_assigned_notification")
            return
        try:
            await bot.send_message(
                trainee.tg_id,
                message,
                parse_mode="HTML"
            )
            logger.info(f"Отправлено уведомление стажеру {trainee_id} о назначении траектории {learning_path_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление стажеру {trainee.tg_id}: {e}")

        logger.info(f"Отправлено уведомление стажеру {trainee_id} о назначении траектории {learning_path_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о назначении траектории: {e}")


async def open_stage_for_trainee(session: AsyncSession, trainee_id: int, stage_id: int, bot=None) -> bool:
    """Открытие этапа для стажера с предоставлением доступа к тестам"""
    try:
        from database.models import TraineeLearningPath, TraineeStageProgress, TraineeSessionProgress

        logger.info(f"ДЕБАГ: Начинаем открытие этапа {stage_id} для стажера {trainee_id}")

        # Находим активную траекторию стажера
        trainee_path_result = await session.execute(
            select(TraineeLearningPath).where(
                TraineeLearningPath.trainee_id == trainee_id,
                TraineeLearningPath.is_active == True
            )
        )
        trainee_path = trainee_path_result.scalar_one_or_none()

        if not trainee_path:
            logger.error(f"Активная траектория для стажера {trainee_id} не найдена")
            return False
        
        logger.info(f"ДЕБАГ: Найдена траектория {trainee_path.id} для стажера {trainee_id}")

        # Открываем этап
        await session.execute(
            update(TraineeStageProgress).where(
                TraineeStageProgress.trainee_path_id == trainee_path.id,
                TraineeStageProgress.stage_id == stage_id
            ).values(
                is_opened=True,
                opened_date=datetime.now()
            )
        )

        # Открываем все сессии этого этапа
        stage_progress_result = await session.execute(
            select(TraineeStageProgress).where(
                TraineeStageProgress.trainee_path_id == trainee_path.id,
                TraineeStageProgress.stage_id == stage_id
            )
        )
        stage_progress = stage_progress_result.scalar_one_or_none()

        if stage_progress:
            await session.execute(
                update(TraineeSessionProgress).where(
                    TraineeSessionProgress.stage_progress_id == stage_progress.id
                ).values(
                    is_opened=True,
                    opened_date=datetime.now()
                )
            )

            # Предоставляем доступ к тестам в открываемом этапе
            # Получаем все сессии этого этапа с тестами
            from database.models import LearningSession
            logger.info(f"ДЕБАГ: Получаем сессии для этапа {stage_id}, stage_progress.id = {stage_progress.id}")
            
            sessions_result = await session.execute(
                select(LearningSession)
                .options(selectinload(LearningSession.tests))
                .join(TraineeSessionProgress)
                .where(TraineeSessionProgress.stage_progress_id == stage_progress.id)
            )
            sessions = sessions_result.scalars().all()
            logger.info(f"ДЕБАГ: Найдено {len(sessions)} сессий для этапа {stage_id}")

            # Получаем наставника для записи в TraineeTestAccess
            mentor_id = trainee_path.assigned_by_id
            logger.info(f"ДЕБАГ: Наставник ID = {mentor_id}")

            # Для каждого теста в каждой сессии создаем доступ
            tests_granted = 0
            for session_obj in sessions:
                logger.info(f"ДЕБАГ: Обрабатываем сессию {session_obj.id} с {len(session_obj.tests)} тестами")
                for test in session_obj.tests:
                    # Проверяем, нет ли уже доступа
                    existing_access = await session.execute(
                        select(TraineeTestAccess).where(
                            TraineeTestAccess.trainee_id == trainee_id,
                            TraineeTestAccess.test_id == test.id,
                            TraineeTestAccess.is_active == True
                        )
                    )
                    if not existing_access.scalar_one_or_none():
                        # Создаем новый доступ к тесту
                        access = TraineeTestAccess(
                            trainee_id=trainee_id,
                            test_id=test.id,
                            granted_by_id=mentor_id
                        )
                        session.add(access)
                        tests_granted += 1
                        logger.info(f"ДЕБАГ: Создан доступ к тесту {test.id} для стажера {trainee_id} при открытии этапа {stage_id}")
                    else:
                        logger.info(f"ДЕБАГ: Доступ к тесту {test.id} уже существует для стажера {trainee_id}")
            
            logger.info(f"ДЕБАГ: Предоставлен доступ к {tests_granted} тестам")

        await session.commit()

        # Отправляем уведомление стажеру
        await send_stage_opened_notification(session, trainee_id, stage_id, bot)

        logger.info(f"Этап {stage_id} открыт для стажера {trainee_id}")
        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка открытия этапа {stage_id} для стажера {trainee_id}: {e}")
        return False


async def send_stage_opened_notification(session: AsyncSession, trainee_id: int, stage_id: int, bot=None) -> None:
    """Отправка уведомления стажеру об открытии этапа"""
    try:
        from database.models import User, LearningStage

        # Получаем данные
        trainee_result = await session.execute(select(User).where(User.id == trainee_id))
        stage_result = await session.execute(select(LearningStage).where(LearningStage.id == stage_id))

        trainee = trainee_result.scalar_one_or_none()
        stage = stage_result.scalar_one_or_none()

        if not trainee or not stage:
            return

        # Уведомление стажеру согласно ТЗ
        message = (
            "🚨<b>Тебе открыли новый этап обучения!</b>\n"
            "Нажми кнопку ниже, чтобы открыть траекторию"
        )

        # Создаем клавиатуру с кнопкой траектории
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Траектория обучения ⬜", callback_data="trajectory_command")]
        ])

        # Отправляем уведомление стажеру
        if not bot:
            logger.warning("Bot instance not provided to send_stage_opened_notification")
            return
        try:
            await bot.send_message(
                trainee.tg_id,
                message,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            logger.info(f"Отправлено уведомление стажеру {trainee_id} об открытии этапа {stage_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление стажеру {trainee.tg_id}: {e}")

        logger.info(f"Отправлено уведомление стажеру {trainee_id} об открытии этапа {stage_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об открытии этапа: {e}")


async def send_stage_completion_notification_to_trainee(session: AsyncSession, trainee_id: int, stage_id: int, bot=None) -> None:
    """Отправка уведомления стажеру о завершении этапа"""
    if not bot:
        logger.warning("Bot instance not provided to send_stage_completion_notification_to_trainee")
        return
        
    try:
        from database.models import User, LearningStage

        # Получаем данные
        trainee_result = await session.execute(select(User).where(User.id == trainee_id))
        stage_result = await session.execute(select(LearningStage).where(LearningStage.id == stage_id))

        trainee = trainee_result.scalar_one_or_none()
        stage = stage_result.scalar_one_or_none()

        if not trainee or not stage:
            return

        # Получаем траекторию стажера для отображения прогресса согласно ТЗ
        trainee_path = await get_trainee_learning_path(session, trainee_id)
        if not trainee_path:
            return
            
        # Получаем результаты тестов стажера
        test_results = await get_user_test_results(session, trainee_id)
        
        # Получаем этапы траектории
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)
        
        # Формируем прогресс траектории согласно ТЗ (используем функцию из mentorship.py)
        from handlers.mentorship import generate_trajectory_progress_for_mentor
        trajectory_progress = generate_trajectory_progress_for_mentor(trainee_path, stages_progress, test_results)
        
        # Уведомление стажеру согласно ТЗ
        message = f"""🏆<b>Твой прогресс</b>
{trajectory_progress}
✅ <b>Ты завершил {stage.name}!</b>
Обратитесь к твоему наставнику, чтобы получить доступ к следующему этапу"""

        # Отправляем уведомление стажеру
        if not bot:
            logger.warning("Bot instance not provided to send_stage_completion_notification_to_trainee")
            return
        try:
            await bot.send_message(
                trainee.tg_id,
                message,
                parse_mode="HTML"
            )
            logger.info(f"Отправлено уведомление стажеру {trainee_id} о завершении этапа {stage_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление стажеру {trainee.tg_id}: {e}")

        logger.info(f"Отправлено уведомление стажеру {trainee_id} о завершении этапа {stage_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления стажеру о завершении этапа: {e}")


async def get_trainee_learning_path(session: AsyncSession, trainee_id: int) -> Optional[TraineeLearningPath]:
    """Получение активной траектории стажера с загрузкой связанных объектов"""
    try:
        from database.models import TraineeLearningPath

        result = await session.execute(
            select(TraineeLearningPath)
            .options(
                selectinload(TraineeLearningPath.learning_path),  # Загружаем траекторию обучения
                selectinload(TraineeLearningPath.learning_path).selectinload(LearningPath.attestation),  # Загружаем аттестацию
                selectinload(TraineeLearningPath.assigned_by)  # Загружаем наставника, который назначил траекторию
            )
            .where(
                TraineeLearningPath.trainee_id == trainee_id,
                TraineeLearningPath.is_active == True
            )
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения траектории стажера {trainee_id}: {e}")
        return None


async def get_trainee_stage_progress(session: AsyncSession, trainee_path_id: int) -> List[TraineeStageProgress]:
    """Получение прогресса стажера по этапам с загрузкой связанных объектов"""
    try:
        from database.models import TraineeStageProgress, LearningStage

        result = await session.execute(
            select(TraineeStageProgress)
            .options(
                selectinload(TraineeStageProgress.stage),  # Загружаем этап
                selectinload(TraineeStageProgress.session_progress),  # Загружаем прогресс сессий
                selectinload(TraineeStageProgress.session_progress).selectinload(TraineeSessionProgress.session),  # Загружаем сессии
                selectinload(TraineeStageProgress.session_progress).selectinload(TraineeSessionProgress.session).selectinload(LearningSession.tests),  # Загружаем тесты сессий
                selectinload(TraineeStageProgress.trainee_path).selectinload(TraineeLearningPath.learning_path).selectinload(LearningPath.attestation)  # Загружаем аттестацию
            )
            .join(LearningStage).where(
                TraineeStageProgress.trainee_path_id == trainee_path_id
            ).order_by(LearningStage.order_number)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения прогресса по этапам для траектории {trainee_path_id}: {e}")
        return []


async def get_stage_session_progress(session: AsyncSession, stage_progress_id: int) -> List[TraineeSessionProgress]:
    """Получение прогресса по сессиям этапа с загрузкой связанных объектов"""
    try:
        from database.models import TraineeSessionProgress, LearningSession

        result = await session.execute(
            select(TraineeSessionProgress)
            .options(
                selectinload(TraineeSessionProgress.session)
                .selectinload(LearningSession.tests)  # Загружаем тесты сессии
            )
            .join(LearningSession).where(
                TraineeSessionProgress.stage_progress_id == stage_progress_id
            ).order_by(LearningSession.order_number)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения прогресса по сессиям для этапа {stage_progress_id}: {e}")
        return []


async def get_all_stage_sessions_progress(session: AsyncSession, stage_progress_id: int) -> List[TraineeSessionProgress]:
    """Получение ВСЕГО прогресса по сессиям этапа (включая завершенные) с загрузкой связанных объектов"""
    try:
        from database.models import TraineeSessionProgress, LearningSession

        result = await session.execute(
            select(TraineeSessionProgress)
            .options(
                selectinload(TraineeSessionProgress.session)
                .selectinload(LearningSession.tests)  # Загружаем тесты сессии
            )
            .join(LearningSession).where(
                TraineeSessionProgress.stage_progress_id == stage_progress_id
            ).order_by(LearningSession.order_number)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всего прогресса по сессиям для этапа {stage_progress_id}: {e}")
        return []


async def complete_stage_for_trainee(session: AsyncSession, trainee_id: int, stage_id: int) -> bool:
    """Отметка этапа как пройденного"""
    try:
        from database.models import TraineeLearningPath, TraineeStageProgress

        # Находим траекторию стажера
        trainee_path_result = await session.execute(
            select(TraineeLearningPath).where(
                TraineeLearningPath.trainee_id == trainee_id,
                TraineeLearningPath.is_active == True
            )
        )
        trainee_path = trainee_path_result.scalar_one_or_none()

        if not trainee_path:
            return False

        # Отмечаем этап как пройденный
        await session.execute(
            update(TraineeStageProgress).where(
                TraineeStageProgress.trainee_path_id == trainee_path.id,
                TraineeStageProgress.stage_id == stage_id
            ).values(
                is_completed=True,
                completed_date=datetime.now()
            )
        )

        await session.commit()

        # Уведомление стажеру теперь показывается в результате теста
        # Уведомление наставнику отправляется из check_and_notify_stage_completion

        logger.info(f"Этап {stage_id} отмечен как пройденный для стажера {trainee_id}")
        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка отметки этапа {stage_id} как пройденного для стажера {trainee_id}: {e}")
        return False


async def complete_session_for_trainee(session: AsyncSession, trainee_id: int, session_id: int) -> bool:
    """Отметка сессии как пройденной"""
    try:
        from database.models import TraineeLearningPath, TraineeStageProgress, TraineeSessionProgress

        # Находим траекторию стажера
        trainee_path_result = await session.execute(
            select(TraineeLearningPath).where(
                TraineeLearningPath.trainee_id == trainee_id,
                TraineeLearningPath.is_active == True
            )
        )
        trainee_path = trainee_path_result.scalar_one_or_none()

        if not trainee_path:
            return False

        # Отмечаем сессию как пройденную
        await session.execute(
            update(TraineeSessionProgress).where(
                TraineeSessionProgress.stage_progress_id.in_(
                    select(TraineeStageProgress.id).where(
                        TraineeStageProgress.trainee_path_id == trainee_path.id
                    )
                ),
                TraineeSessionProgress.session_id == session_id
            ).values(
                is_completed=True,
                completed_date=datetime.now()
            )
        )

        await session.commit()
        logger.info(f"Сессия {session_id} отмечена как пройденная для стажера {trainee_id}")
        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка отметки сессии {session_id} как пройденной для стажера {trainee_id}: {e}")
        return False


async def get_available_learning_paths_for_mentor(session: AsyncSession, mentor_id: int) -> List[LearningPath]:
    """Получение доступных траекторий для наставника"""
    try:
        from database.models import LearningPath, User

        # Получаем наставника для определения его группы
        mentor_result = await session.execute(select(User).where(User.id == mentor_id))
        mentor = mentor_result.scalar_one_or_none()

        if not mentor or not mentor.groups:
            return []

        # Получаем группы наставника
        mentor_group_ids = [group.id for group in mentor.groups]

        # Получаем траектории для этих групп
        result = await session.execute(
            select(LearningPath)
            .options(
                selectinload(LearningPath.attestation)  # Загружаем аттестацию
            )
            .where(
                LearningPath.group_id.in_(mentor_group_ids),
                LearningPath.is_active == True
            ).order_by(LearningPath.name)
        )

        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения доступных траекторий для наставника {mentor_id}: {e}")
        return []


async def get_learning_path_stages(session: AsyncSession, learning_path_id: int) -> List[LearningStage]:
    """Получение этапов траектории"""
    try:
        from database.models import LearningStage

        result = await session.execute(
            select(LearningStage).where(
                LearningStage.learning_path_id == learning_path_id
            ).order_by(LearningStage.order_number)
        )

        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения этапов траектории {learning_path_id}: {e}")
        return []


async def get_session_with_tests(session: AsyncSession, session_id: int) -> Optional['LearningSession']:
    """Получение сессии с загруженными тестами"""
    try:
        from database.models import LearningSession

        result = await session.execute(
            select(LearningSession)
            .options(
                selectinload(LearningSession.tests)  # Загружаем тесты сессии
            )
            .where(LearningSession.id == session_id)
        )

        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения сессии {session_id}: {e}")
        return None


async def get_stage_sessions(session: AsyncSession, stage_id: int) -> List['LearningSession']:
    """Получение сессий этапа"""
    try:
        from database.models import LearningSession

        result = await session.execute(
            select(LearningSession).where(
                LearningSession.stage_id == stage_id
            ).order_by(LearningSession.order_number)
        )

        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения сессий этапа {stage_id}: {e}")
        return []


async def get_session_tests(session: AsyncSession, session_id: int) -> List[Test]:
    """Получение тестов сессии"""
    try:
        from database.models import LearningSession, session_tests

        result = await session.execute(
            select(Test).join(
                session_tests, Test.id == session_tests.c.test_id
            ).where(
                session_tests.c.session_id == session_id
            ).order_by(session_tests.c.order_number)
        )

        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения тестов сессии {session_id}: {e}")
        return []


# ===== ФУНКЦИИ ДЛЯ РЕДАКТИРОВАНИЯ ТРАЕКТОРИЙ =====

async def update_learning_path_name(session: AsyncSession, path_id: int, new_name: str) -> bool:
    """Изменение названия траектории обучения"""
    try:
        # Валидация и очистка входных данных
        new_name = new_name.strip() if new_name else ""
        if not new_name:
            logger.error(f"Название траектории не может быть пустым")
            return False
        
        # Проверяем существование траектории
        learning_path = await get_learning_path_by_id(session, path_id)
        if not learning_path:
            logger.error(f"Траектория с ID {path_id} не найдена")
            return False
        
        # Проверяем уникальность нового названия (в рамках активных траекторий)
        existing_result = await session.execute(
            select(LearningPath).where(
                func.lower(LearningPath.name) == func.lower(new_name),
                LearningPath.id != path_id,
                LearningPath.is_active == True
            )
        )
        if existing_result.scalar_one_or_none():
            logger.error(f"Траектория с названием '{new_name}' уже существует")
            return False
        
        old_name = learning_path.name
        stmt = update(LearningPath).where(LearningPath.id == path_id).values(name=new_name)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Название траектории {path_id} изменено: '{old_name}' -> '{new_name}'")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения названия траектории {path_id}: {e}")
        await session.rollback()
        return False


async def update_learning_stage_name(session: AsyncSession, stage_id: int, new_name: str) -> bool:
    """Изменение названия этапа траектории"""
    try:
        # Валидация и очистка входных данных
        new_name = new_name.strip() if new_name else ""
        if not new_name:
            logger.error(f"Название этапа не может быть пустым")
            return False
        
        # Проверяем существование этапа
        result = await session.execute(
            select(LearningStage).where(LearningStage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        if not stage:
            logger.error(f"Этап с ID {stage_id} не найден")
            return False
        
        old_name = stage.name
        stmt = update(LearningStage).where(LearningStage.id == stage_id).values(name=new_name)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Название этапа {stage_id} изменено: '{old_name}' -> '{new_name}'")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения названия этапа {stage_id}: {e}")
        await session.rollback()
        return False


async def update_learning_stage_description(session: AsyncSession, stage_id: int, new_description: Optional[str]) -> bool:
    """Изменение описания этапа траектории"""
    try:
        # Проверяем существование этапа
        result = await session.execute(
            select(LearningStage).where(LearningStage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        if not stage:
            logger.error(f"Этап с ID {stage_id} не найден")
            return False
        
        # Описание может быть пустым
        description_value = new_description.strip() if new_description else None
        
        stmt = update(LearningStage).where(LearningStage.id == stage_id).values(description=description_value)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Описание этапа {stage_id} обновлено")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения описания этапа {stage_id}: {e}")
        await session.rollback()
        return False


async def update_learning_session_name(session: AsyncSession, session_id: int, new_name: str) -> bool:
    """Изменение названия сессии траектории"""
    try:
        # Валидация и очистка входных данных
        new_name = new_name.strip() if new_name else ""
        if not new_name:
            logger.error(f"Название сессии не может быть пустым")
            return False
        
        # Проверяем существование сессии
        result = await session.execute(
            select(LearningSession).where(LearningSession.id == session_id)
        )
        learning_session = result.scalar_one_or_none()
        if not learning_session:
            logger.error(f"Сессия с ID {session_id} не найдена")
            return False
        
        old_name = learning_session.name
        stmt = update(LearningSession).where(LearningSession.id == session_id).values(name=new_name)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Название сессии {session_id} изменено: '{old_name}' -> '{new_name}'")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения названия сессии {session_id}: {e}")
        await session.rollback()
        return False


async def update_learning_session_description(session: AsyncSession, session_id: int, new_description: Optional[str]) -> bool:
    """Изменение описания сессии траектории"""
    try:
        # Проверяем существование сессии
        result = await session.execute(
            select(LearningSession).where(LearningSession.id == session_id)
        )
        learning_session = result.scalar_one_or_none()
        if not learning_session:
            logger.error(f"Сессия с ID {session_id} не найдена")
            return False
        
        # Описание может быть пустым
        description_value = new_description.strip() if new_description else None
        
        stmt = update(LearningSession).where(LearningSession.id == session_id).values(description=description_value)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Описание сессии {session_id} обновлено")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения описания сессии {session_id}: {e}")
        await session.rollback()
        return False


async def update_learning_path_group(session: AsyncSession, path_id: int, new_group_id: int) -> bool:
    """Изменение группы траектории обучения"""
    try:
        # Проверяем существование траектории
        learning_path = await get_learning_path_by_id(session, path_id)
        if not learning_path:
            logger.error(f"Траектория с ID {path_id} не найдена")
            return False
        
        # Проверяем существование новой группы
        group = await get_group_by_id(session, new_group_id)
        if not group:
            logger.error(f"Группа с ID {new_group_id} не найдена")
            return False
        
        old_group_id = learning_path.group_id
        stmt = update(LearningPath).where(LearningPath.id == path_id).values(group_id=new_group_id)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Группа траектории {path_id} изменена: {old_group_id} -> {new_group_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения группы траектории {path_id}: {e}")
        await session.rollback()
        return False


async def update_learning_path_attestation(session: AsyncSession, path_id: int, new_attestation_id: Optional[int]) -> bool:
    """Изменение аттестации траектории обучения (может быть None для удаления)"""
    try:
        # Проверяем существование траектории
        learning_path = await get_learning_path_by_id(session, path_id)
        if not learning_path:
            logger.error(f"Траектория с ID {path_id} не найдена")
            return False
        
        # Если указана новая аттестация, проверяем её существование
        if new_attestation_id is not None:
            attestation = await get_attestation_by_id(session, new_attestation_id)
            if not attestation:
                logger.error(f"Аттестация с ID {new_attestation_id} не найдена")
                return False
        
        old_attestation_id = learning_path.attestation_id
        stmt = update(LearningPath).where(LearningPath.id == path_id).values(attestation_id=new_attestation_id)
        await session.execute(stmt)
        await session.commit()
        
        action = "удалена" if new_attestation_id is None else f"изменена на {new_attestation_id}"
        logger.info(f"Аттестация траектории {path_id} {action} (была: {old_attestation_id})")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения аттестации траектории {path_id}: {e}")
        await session.rollback()
        return False


async def reorder_learning_stages(session: AsyncSession, path_id: int, stage_orders: dict) -> bool:
    """Изменение порядка этапов в траектории
    
    Args:
        session: Сессия БД
        path_id: ID траектории
        stage_orders: Словарь {stage_id: new_order_number}
    """
    try:
        # Валидация входных данных
        if not stage_orders:
            logger.warning(f"Словарь порядков этапов пуст для траектории {path_id}")
            return False
        
        # Проверяем существование траектории
        learning_path = await get_learning_path_by_id(session, path_id)
        if not learning_path:
            logger.error(f"Траектория с ID {path_id} не найдена")
            return False
        
        # Валидация: проверяем, что все этапы принадлежат этой траектории
        stage_ids = list(stage_orders.keys())
        existing_stages_result = await session.execute(
            select(LearningStage.id).where(
                LearningStage.id.in_(stage_ids),
                LearningStage.learning_path_id == path_id
            )
        )
        existing_stage_ids = {row[0] for row in existing_stages_result.all()}
        
        if len(existing_stage_ids) != len(stage_ids):
            missing_ids = set(stage_ids) - existing_stage_ids
            logger.error(f"Некоторые этапы не найдены или не принадлежат траектории {path_id}: {missing_ids}")
            return False
        
        # Обновляем порядок для каждого этапа
        for stage_id, new_order in stage_orders.items():
            if not isinstance(new_order, int) or new_order < 1:
                logger.error(f"Некорректный порядок {new_order} для этапа {stage_id}")
                return False
            
            stmt = update(LearningStage).where(
                LearningStage.id == stage_id,
                LearningStage.learning_path_id == path_id
            ).values(order_number=new_order)
            await session.execute(stmt)
        
        await session.commit()
        logger.info(f"Порядок этапов траектории {path_id} обновлен")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения порядка этапов траектории {path_id}: {e}")
        await session.rollback()
        return False


async def reorder_learning_sessions(session: AsyncSession, stage_id: int, session_orders: dict) -> bool:
    """Изменение порядка сессий в этапе
    
    Args:
        session: Сессия БД
        stage_id: ID этапа
        session_orders: Словарь {session_id: new_order_number}
    """
    try:
        # Валидация входных данных
        if not session_orders:
            logger.warning(f"Словарь порядков сессий пуст для этапа {stage_id}")
            return False
        
        # Проверяем существование этапа
        result = await session.execute(
            select(LearningStage).where(LearningStage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        if not stage:
            logger.error(f"Этап с ID {stage_id} не найден")
            return False
        
        # Валидация: проверяем, что все сессии принадлежат этому этапу
        session_ids = list(session_orders.keys())
        existing_sessions_result = await session.execute(
            select(LearningSession.id).where(
                LearningSession.id.in_(session_ids),
                LearningSession.stage_id == stage_id
            )
        )
        existing_session_ids = {row[0] for row in existing_sessions_result.all()}
        
        if len(existing_session_ids) != len(session_ids):
            missing_ids = set(session_ids) - existing_session_ids
            logger.error(f"Некоторые сессии не найдены или не принадлежат этапу {stage_id}: {missing_ids}")
            return False
        
        # Обновляем порядок для каждой сессии
        for session_id, new_order in session_orders.items():
            if not isinstance(new_order, int) or new_order < 1:
                logger.error(f"Некорректный порядок {new_order} для сессии {session_id}")
                return False
            
            stmt = update(LearningSession).where(
                LearningSession.id == session_id,
                LearningSession.stage_id == stage_id
            ).values(order_number=new_order)
            await session.execute(stmt)
        
        await session.commit()
        logger.info(f"Порядок сессий этапа {stage_id} обновлен")
        return True
    except Exception as e:
        logger.error(f"Ошибка изменения порядка сессий этапа {stage_id}: {e}")
        await session.rollback()
        return False


async def check_stage_has_trainees(session: AsyncSession, stage_id: int) -> bool:
    """Проверка, есть ли стажеры с назначенной траекторией, содержащей этот этап"""
    try:
        # Получаем этап и его траекторию
        result = await session.execute(
            select(LearningStage).where(LearningStage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        if not stage:
            return False
        
        # Проверяем, есть ли активные назначения траектории стажерам
        trainees_result = await session.execute(
            select(func.count(TraineeLearningPath.id)).where(
                TraineeLearningPath.learning_path_id == stage.learning_path_id,
                TraineeLearningPath.is_active == True
            )
        )
        trainees_count = trainees_result.scalar() or 0
        
        return trainees_count > 0
    except Exception as e:
        logger.error(f"Ошибка проверки стажеров для этапа {stage_id}: {e}")
        return True  # В случае ошибки блокируем удаление для безопасности


async def check_session_has_trainees(session: AsyncSession, session_id: int) -> bool:
    """Проверка, есть ли стажеры с назначенной траекторией, содержащей эту сессию"""
    try:
        # Оптимизированный запрос: получаем learning_path_id через JOIN и сразу проверяем стажеров
        result = await session.execute(
            select(func.count(TraineeLearningPath.id))
            .select_from(LearningSession)
            .join(LearningStage, LearningSession.stage_id == LearningStage.id)
            .join(TraineeLearningPath, LearningStage.learning_path_id == TraineeLearningPath.learning_path_id)
            .where(
                LearningSession.id == session_id,
                TraineeLearningPath.is_active == True
            )
        )
        trainees_count = result.scalar() or 0
        
        return trainees_count > 0
    except Exception as e:
        logger.error(f"Ошибка проверки стажеров для сессии {session_id}: {e}")
        return True  # В случае ошибки блокируем удаление для безопасности


async def delete_learning_stage(session: AsyncSession, stage_id: int) -> bool:
    """Удаление этапа траектории с проверкой использования стажерами"""
    try:
        # Получаем этап с сессиями для каскадного удаления через ORM
        result = await session.execute(
            select(LearningStage)
            .where(LearningStage.id == stage_id)
            .options(selectinload(LearningStage.sessions))
        )
        stage = result.scalar_one_or_none()
        
        if not stage:
            logger.error(f"Этап с ID {stage_id} не найден")
            return False
        
        # Проверяем, есть ли стажеры с этой траекторией
        has_trainees = await check_stage_has_trainees(session, stage_id)
        if has_trainees:
            logger.warning(f"Нельзя удалить этап {stage_id}: есть стажеры с назначенной траекторией")
            return False
        
        # Получаем все сессии этапа для удаления связей с тестами
        # Используем подзапрос для оптимизации
        if stage.sessions:
            session_ids = [s.id for s in stage.sessions]
            await session.execute(
                delete(session_tests).where(session_tests.c.session_id.in_(session_ids))
            )
            # Явно удаляем все сессии этапа
            await session.execute(
                delete(LearningSession).where(LearningSession.stage_id == stage_id)
            )
        
        # Удаляем этап
        await session.execute(
            delete(LearningStage).where(LearningStage.id == stage_id)
        )
        await session.commit()
        
        logger.info(f"Этап {stage_id} '{stage.name}' удален")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления этапа {stage_id}: {e}")
        await session.rollback()
        return False


async def delete_learning_session(session: AsyncSession, session_id: int) -> bool:
    """Удаление сессии траектории с проверкой использования стажерами"""
    try:
        # Проверяем существование сессии
        result = await session.execute(
            select(LearningSession).where(LearningSession.id == session_id)
        )
        learning_session = result.scalar_one_or_none()
        if not learning_session:
            logger.error(f"Сессия с ID {session_id} не найдена")
            return False
        
        # Проверяем, есть ли стажеры с этой траекторией
        has_trainees = await check_session_has_trainees(session, session_id)
        if has_trainees:
            logger.warning(f"Нельзя удалить сессию {session_id}: есть стажеры с назначенной траекторией")
            return False
        
        # Удаляем прогресс стажеров по сессии (если остались)
        await session.execute(
            delete(TraineeSessionProgress).where(TraineeSessionProgress.session_id == session_id)
        )
        
        # Удаляем связи тестов с сессией
        await session.execute(
            delete(session_tests).where(session_tests.c.session_id == session_id)
        )
        
        # Удаляем саму сессию
        await session.execute(
            delete(LearningSession).where(LearningSession.id == session_id)
        )
        await session.commit()
        
        logger.info(f"Сессия {session_id} '{learning_session.name}' удалена")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления сессии {session_id}: {e}")
        await session.rollback()
        return False


async def add_test_to_session_from_editor(session: AsyncSession, session_id: int, test_id: int) -> bool:
    """Добавление теста в сессию через редактор"""
    try:
        # Проверяем существование сессии
        result = await session.execute(
            select(LearningSession).where(LearningSession.id == session_id)
        )
        learning_session = result.scalar_one_or_none()
        if not learning_session:
            logger.error(f"Сессия с ID {session_id} не найдена")
            return False
        
        # Проверяем существование теста
        test = await session.get(Test, test_id)
        if not test:
            logger.error(f"Тест с ID {test_id} не найден")
            return False
        
        # Проверяем, не добавлен ли уже тест в эту сессию
        existing_result = await session.execute(
            select(session_tests).where(
                session_tests.c.session_id == session_id,
                session_tests.c.test_id == test_id
            )
        )
        if existing_result.first():
            logger.warning(f"Тест {test_id} уже добавлен в сессию {session_id}")
            return False
        
        # Получаем максимальный order_number для тестов в этой сессии
        max_order_result = await session.execute(
            select(func.max(session_tests.c.order_number)).where(
                session_tests.c.session_id == session_id
            )
        )
        max_order = max_order_result.scalar() or 0
        
        # Добавляем тест в сессию
        stmt = insert(session_tests).values(
            session_id=session_id,
            test_id=test_id,
            order_number=max_order + 1
        )
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Тест {test_id} добавлен в сессию {session_id} с порядком {max_order + 1}")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления теста {test_id} в сессию {session_id}: {e}")
        await session.rollback()
        return False


async def remove_test_from_session(session: AsyncSession, session_id: int, test_id: int) -> bool:
    """Удаление теста из сессии"""
    try:
        # Проверяем существование связи
        existing_result = await session.execute(
            select(session_tests).where(
                session_tests.c.session_id == session_id,
                session_tests.c.test_id == test_id
            )
        )
        if not existing_result.first():
            logger.warning(f"Тест {test_id} не найден в сессии {session_id}")
            return False
        
        # Удаляем связь теста с сессией (тест остается в системе)
        await session.execute(
            delete(session_tests).where(
                session_tests.c.session_id == session_id,
                session_tests.c.test_id == test_id
            )
        )
        await session.commit()
        
        logger.info(f"Тест {test_id} удален из сессии {session_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления теста {test_id} из сессии {session_id}: {e}")
        await session.rollback()
        return False


async def save_stage_to_trajectory_from_editor(session: AsyncSession, path_id: int, stage_data: dict) -> Optional[LearningStage]:
    """
    Сохранение нового этапа в существующую траекторию из редактора
    
    Args:
        session: Сессия БД
        path_id: ID траектории
        stage_data: Словарь с данными этапа:
            - name: название этапа
            - description: описание этапа (опционально)
            - order: порядковый номер этапа
            - sessions: список сессий с их тестами
    
    Returns:
        LearningStage или None при ошибке
    """
    try:
        # Валидация обязательных полей
        if not stage_data.get('name'):
            logger.error("Отсутствует название этапа")
            return None
        if not stage_data.get('order'):
            logger.error("Отсутствует порядковый номер этапа")
            return None
        
        # Проверяем существование траектории
        learning_path = await get_learning_path_by_id(session, path_id)
        if not learning_path:
            logger.error(f"Траектория с ID {path_id} не найдена")
            return None
        
        logger.info(f"Сохранение этапа '{stage_data['name']}' в траекторию {path_id}")
        
        # Создаем этап
        stage = LearningStage(
            name=stage_data['name'],
            description=stage_data.get('description', ''),
            learning_path_id=path_id,
            order_number=stage_data['order']
        )
        session.add(stage)
        await session.flush()
        logger.info(f"Этап создан с ID: {stage.id}")
        
        # Создаем сессии для этапа
        for session_data in stage_data.get('sessions', []):
            logger.info(f"Создание сессии: {session_data['name']}, order: {session_data['order']}")
            learning_session = LearningSession(
                name=session_data['name'],
                description=session_data.get('description', ''),
                stage_id=stage.id,
                order_number=session_data['order']
            )
            session.add(learning_session)
            await session.flush()
            logger.info(f"Сессия создана с ID: {learning_session.id}")
            
            # Привязываем тесты к сессии
            for test_data in session_data.get('tests', []):
                test_id = test_data.get('id') if isinstance(test_data, dict) else test_data
                test_order = test_data.get('order', 1) if isinstance(test_data, dict) else 1
                
                logger.info(f"Привязка теста ID:{test_id} к сессии ID:{learning_session.id}")
                stmt = insert(session_tests).values(
                    session_id=learning_session.id,
                    test_id=test_id,
                    order_number=test_order
                )
                await session.execute(stmt)
        
        await session.commit()
        logger.info(f"Этап '{stage_data['name']}' успешно сохранен в траекторию {path_id}")
        return stage
        
    except Exception as e:
        logger.error(f"Ошибка сохранения этапа в траекторию {path_id}: {e}")
        await session.rollback()
        return None


# ===== ФУНКЦИИ ДЛЯ АТТЕСТАЦИОННОЙ СИСТЕМЫ =====

async def get_available_managers_for_trainee(session: AsyncSession, trainee_id: int) -> List[User]:
    """
    Получение доступных руководителей для назначения стажеру
    Руководители должны иметь роль "Руководитель"
    """
    try:
        # Получаем стажера для определения его объекта работы
        trainee_result = await session.execute(
            select(User).where(User.id == trainee_id)
        )
        trainee = trainee_result.scalar_one_or_none()

        if not trainee or not trainee.work_object:
            return []

        # Получаем роль руководителя
        manager_role_result = await session.execute(
            select(Role).where(Role.name == "Руководитель")
        )
        manager_role = manager_role_result.scalar_one_or_none()

        if not manager_role:
            return []

        # Получаем руководителей, которые работают на том же объекте
        result = await session.execute(
            select(User).join(
                user_roles, User.id == user_roles.c.user_id
            ).where(
                user_roles.c.role_id == manager_role.id,
                User.work_object_id == trainee.work_object_id,
                User.is_active == True
            ).order_by(User.full_name)
        )

        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения доступных руководителей для стажера {trainee_id}: {e}")
        return []


async def assign_manager_to_trainee(session: AsyncSession, trainee_id: int, manager_id: int, assigned_by_id: int) -> Optional[TraineeManager]:
    """
    Назначение руководителя стажеру
    """
    try:
        # Проверяем, что стажер существует
        trainee_result = await session.execute(
            select(User).where(User.id == trainee_id)
        )
        trainee = trainee_result.scalar_one_or_none()

        if not trainee:
            logger.error(f"Стажер {trainee_id} не найден")
            return None

        # Проверяем, что руководитель существует
        manager_result = await session.execute(
            select(User).where(User.id == manager_id)
        )
        manager = manager_result.scalar_one_or_none()

        if not manager:
            logger.error(f"Руководитель {manager_id} не найден")
            return None

        # Проверяем, что назначитель существует
        assigner_result = await session.execute(
            select(User).where(User.id == assigned_by_id)
        )
        assigner = assigner_result.scalar_one_or_none()

        if not assigner:
            logger.error(f"Назначитель {assigned_by_id} не найден")
            return None

        # Проверяем, что руководитель имеет подходящую роль
        manager_roles = await get_user_roles(session, manager_id)
        role_names = [role.name for role in manager_roles]
        if "Руководитель" not in role_names:
            logger.error(f"Пользователь {manager_id} не может быть руководителем (неподходящая роль)")
            return None

        # Проверяем, что стажер имеет роль стажера
        trainee_roles = await get_user_roles(session, trainee_id)
        trainee_role_names = [role.name for role in trainee_roles]
        if "Стажер" not in trainee_role_names:
            logger.error(f"Пользователь {trainee_id} не может быть стажером (неподходящая роль)")
            return None

        # Создаем связь стажер-руководитель
        trainee_manager = TraineeManager(
            trainee_id=trainee_id,
            manager_id=manager_id,
            assigned_by_id=assigned_by_id
        )

        session.add(trainee_manager)
        await session.flush()

        logger.info(f"Руководитель {manager.full_name} назначен стажеру {trainee.full_name}")
        return trainee_manager

    except Exception as e:
        logger.error(f"Ошибка назначения руководителя стажеру: {e}")
        return None


async def get_trainee_manager(session: AsyncSession, trainee_id: int) -> Optional[TraineeManager]:
    """
    Получение руководителя стажера
    """
    try:
        result = await session.execute(
            select(TraineeManager).where(
                TraineeManager.trainee_id == trainee_id,
                TraineeManager.is_active == True
            )
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения руководителя стажера {trainee_id}: {e}")
        return None


async def get_manager_trainees(session: AsyncSession, manager_id: int) -> List[TraineeManager]:
    """
    Получение всех стажеров руководителя
    """
    try:
        result = await session.execute(
            select(TraineeManager).where(
                TraineeManager.manager_id == manager_id,
                TraineeManager.is_active == True
            ).order_by(TraineeManager.assigned_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения стажеров руководителя {manager_id}: {e}")
        return []


async def conduct_attestation(session: AsyncSession, trainee_id: int, attestation_id: int, manager_id: int, scores: dict) -> Optional[AttestationResult]:
    """
    Проведение аттестации руководителем
    scores - словарь {question_id: score}
    """
    try:
        # Получаем аттестацию
        attestation_result = await session.execute(
            select(Attestation).where(Attestation.id == attestation_id)
        )
        attestation = attestation_result.scalar_one_or_none()

        if not attestation:
            logger.error(f"Аттестация {attestation_id} не найдена")
            return None

        # Рассчитываем общий балл
        total_score = sum(scores.values())
        is_passed = total_score >= attestation.passing_score

        # Создаем результат аттестации
        attestation_result = AttestationResult(
            trainee_id=trainee_id,
            attestation_id=attestation_id,
            manager_id=manager_id,
            total_score=total_score,
            max_score=attestation.max_score,
            is_passed=is_passed
        )

        session.add(attestation_result)
        await session.flush()

        logger.info(f"Аттестация проведена для стажера {trainee_id}, результат: {total_score}/{attestation.max_score}, пройдена: {is_passed}")

        # НЕ автоматически переводим в сотрудники - решение принимает руководитель
        # await change_trainee_to_employee(session, trainee_id, attestation_result.id)

        return attestation_result

    except Exception as e:
        logger.error(f"Ошибка проведения аттестации: {e}")
        return None


async def get_attestation_results(session: AsyncSession, trainee_id: int) -> List[AttestationResult]:
    """
    Получение результатов аттестаций стажера
    """
    try:
        result = await session.execute(
            select(AttestationResult).where(
                AttestationResult.trainee_id == trainee_id,
                AttestationResult.is_active == True
            ).order_by(AttestationResult.completed_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения результатов аттестаций стажера {trainee_id}: {e}")
        return []


async def get_user_attestation_result(session: AsyncSession, trainee_id: int, attestation_id: int) -> Optional[AttestationResult]:
    """
    Получение результата конкретной аттестации для стажера
    """
    try:
        result = await session.execute(
            select(AttestationResult).where(
                AttestationResult.trainee_id == trainee_id,
                AttestationResult.attestation_id == attestation_id,
                AttestationResult.is_active == True
            ).order_by(AttestationResult.completed_date.desc())
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения результата аттестации {attestation_id} для стажера {trainee_id}: {e}")
        return None


async def change_trainee_to_employee(session: AsyncSession, trainee_id: int, attestation_result_id: int) -> bool:
    """
    Изменение роли стажера на сотрудника после успешной аттестации
    
    ВАЖНО: При переходе через аттестацию TraineeTestAccess НЕ деактивируется,
    чтобы стажер мог продолжать видеть свои тесты из рассылки в "Мои тесты 📋"
    после перехода в сотрудника.
    """
    try:
        from database.models import Mentorship
        
        # Получаем стажера
        trainee_result = await session.execute(
            select(User).where(User.id == trainee_id)
        )
        trainee = trainee_result.scalar_one_or_none()

        if not trainee:
            logger.error(f"Стажер {trainee_id} не найден")
            return False

        # Получаем роли
        trainee_role_result = await session.execute(
            select(Role).where(Role.name == "Стажер")
        )
        trainee_role = trainee_role_result.scalar_one_or_none()

        employee_role_result = await session.execute(
            select(Role).where(Role.name == "Сотрудник")
        )
        employee_role = employee_role_result.scalar_one_or_none()

        if not trainee_role or not employee_role:
            logger.error("Не найдены роли 'Стажер' или 'Сотрудник'")
            return False

        # Удаляем стажерскую роль
        await session.execute(
            user_roles.delete().where(
                user_roles.c.user_id == trainee_id,
                user_roles.c.role_id == trainee_role.id
            )
        )

        # Добавляем роль сотрудника
        stmt = insert(user_roles).values(
            user_id=trainee_id,
            role_id=employee_role.id
        )
        await session.execute(stmt)

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Деактивируем траекторию и все связанное с ней
        trainee_path_result = await session.execute(
            select(TraineeLearningPath).where(
                TraineeLearningPath.trainee_id == trainee_id,
                TraineeLearningPath.is_active == True
            )
        )
        trainee_path = trainee_path_result.scalar_one_or_none()

        if trainee_path:
            # Завершаем траекторию - сотрудники не должны получать уведомления о траекториях
            trainee_path.attestation_completed = True
            trainee_path.is_active = False  # ДЕАКТИВИРУЕМ траекторию
            await session.flush()
            logger.info(f"Траектория деактивирована для нового сотрудника {trainee_id}")

        # Деактивируем наставничество - сотрудники не должны иметь наставников
        await session.execute(
            update(Mentorship).where(
                Mentorship.trainee_id == trainee_id,
                Mentorship.is_active == True
            ).values(is_active=False)
        )
        logger.info(f"Наставничество деактивировано для нового сотрудника {trainee_id}")

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Очищаем все результаты тестов при переходе в сотрудники
        # Это необходимо, чтобы при возможном возврате в стажеры индикация была правильной
        deleted_results = await session.execute(
            delete(TestResult).where(TestResult.user_id == trainee_id)
        )
        if deleted_results.rowcount > 0:
            logger.info(f"Очищено {deleted_results.rowcount} результатов тестов при переходе в сотрудники")

        await session.commit()
        logger.info(f"Роль стажера изменена на сотрудника для пользователя {trainee.full_name}. Траектории, наставничество и результаты тестов деактивированы.")
        return True

    except Exception as e:
        logger.error(f"Ошибка изменения роли стажера на сотрудника: {e}")
        return False


async def make_manager_decision(session: AsyncSession, attestation_result_id: int, decision: bool, comment: str = None) -> bool:
    """
    Принятие решения руководителем о переводе стажера в сотрудники
    """
    try:
        # Получаем результат аттестации
        result = await session.execute(
            select(AttestationResult).where(AttestationResult.id == attestation_result_id)
        )
        attestation_result = result.scalar_one_or_none()

        if not attestation_result:
            logger.error(f"Результат аттестации {attestation_result_id} не найден")
            return False

        # Обновляем решение руководителя
        attestation_result.manager_decision = decision
        attestation_result.manager_comment = comment
        await session.flush()

        # Если руководитель решил перевести в сотрудники
        if decision:
            success = await change_trainee_to_employee(session, attestation_result.trainee_id, attestation_result_id)
            if success:
                logger.info(f"Стажер {attestation_result.trainee_id} переведен в сотрудники по решению руководителя")
            else:
                logger.error(f"Ошибка перевода стажера {attestation_result.trainee_id} в сотрудники")
                return False

        logger.info(f"Руководитель принял решение по аттестации {attestation_result_id}: {'перевести в сотрудники' if decision else 'оставить стажером'}")
        return True

    except Exception as e:
        logger.error(f"Ошибка принятия решения руководителем: {e}")
        return False


async def get_pending_attestation_decisions(session: AsyncSession, manager_id: int) -> List[AttestationResult]:
    """
    Получение ожидающих решения аттестаций для руководителя
    """
    try:
        result = await session.execute(
            select(AttestationResult).where(
                AttestationResult.manager_id == manager_id,
                AttestationResult.manager_decision.is_(None),  # Решение еще не принято
                AttestationResult.is_active == True
            ).order_by(AttestationResult.completed_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения ожидающих решений для руководителя {manager_id}: {e}")
        return []


async def send_attestation_completed_notification(session: AsyncSession, trainee_id: int, attestation_result: AttestationResult) -> None:
    """
    Отправка уведомления о завершении аттестации
    """
    try:
        # Получаем стажера
        trainee_result = await session.execute(
            select(User).where(User.id == trainee_id)
        )
        trainee = trainee_result.scalar_one_or_none()

        if not trainee:
            return

        # Получаем наставника стажера
        mentorship_result = await session.execute(
            select(Mentorship).where(
                Mentorship.trainee_id == trainee_id,
                Mentorship.is_active == True
            )
        )
        mentorship = mentorship_result.scalar_one_or_none()

        if not mentorship:
            return

        mentor = await get_user_by_id(session, mentorship.mentor_id)
        if not mentor:
            return

        # Формируем уведомление
        notification_message = (
            "🎓 <b>Аттестация завершена!</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"📊 <b>Результат:</b> {attestation_result.total_score:.1f}/{attestation_result.max_score:.1f}\n"
            f"📅 <b>Дата:</b> {attestation_result.completed_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"🎯 <b>Статус по баллам:</b> {'✅ Пройдена' if attestation_result.is_passed else '❌ Не пройдена'}\n\n"
            "⚖️ <b>Ожидает решения руководителя</b>\n"
            "Руководитель примет решение о переводе стажера в сотрудники."
        )

        logger.info(f"Отправлено уведомление о завершении аттестации для стажера {trainee.full_name}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о завершении аттестации: {e}")


# ===============================
# Функции для Task 7: Переход от Стажера к Сотруднику
# ===============================

async def assign_attestation_to_trainee(session: AsyncSession, trainee_id: int, manager_id: int, 
                                       attestation_id: int, assigned_by_id: int) -> Optional[TraineeAttestation]:
    """Назначение аттестации стажеру наставником"""
    try:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем дубликаты по всем параметрам включая manager_id
        existing = await session.execute(
            select(TraineeAttestation)
            .where(TraineeAttestation.trainee_id == trainee_id)
            .where(TraineeAttestation.manager_id == manager_id)
            .where(TraineeAttestation.attestation_id == attestation_id)
            .where(TraineeAttestation.is_active == True)
        )
        
        existing_assignment = existing.scalar_one_or_none()
        if existing_assignment:
            logger.warning(f"Аттестация {attestation_id} уже назначена стажеру {trainee_id} с руководителем {manager_id}")
            return existing_assignment  # Возвращаем существующее назначение вместо None
        
        # Дополнительная проверка: деактивируем все старые назначения этой же аттестации для этого стажера
        await session.execute(
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
            status='assigned'
        )
        
        session.add(trainee_attestation)
        await session.flush()
        
        logger.info(f"Аттестация {attestation_id} назначена стажеру {trainee_id} с руководителем {manager_id}")
        return trainee_attestation
        
    except Exception as e:
        logger.error(f"Ошибка назначения аттестации: {e}")
        return None


async def get_manager_assigned_attestations(session: AsyncSession, manager_id: int) -> List[TraineeAttestation]:
    """Получение всех назначенных аттестаций для руководителя"""
    try:
        result = await session.execute(
            select(TraineeAttestation)
            .options(
                selectinload(TraineeAttestation.trainee).selectinload(User.work_object),
                selectinload(TraineeAttestation.attestation),
                selectinload(TraineeAttestation.assigned_by)
            )
            .where(TraineeAttestation.manager_id == manager_id)
            .where(TraineeAttestation.is_active == True)
            .order_by(TraineeAttestation.assigned_date.desc())
        )
        return result.scalars().all()
        
    except Exception as e:
        logger.error(f"Ошибка получения назначенных аттестаций для руководителя {manager_id}: {e}")
        return []


async def update_attestation_schedule(session: AsyncSession, attestation_id: int, 
                                    scheduled_date: str, scheduled_time: str) -> bool:
    """Обновление даты и времени аттестации"""
    try:
        result = await session.execute(
            update(TraineeAttestation)
            .where(TraineeAttestation.id == attestation_id)
            .values(
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time
            )
        )
        
        if result.rowcount > 0:
            logger.info(f"Обновлены дата и время для аттестации {attestation_id}: {scheduled_date} {scheduled_time}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Ошибка обновления расписания аттестации {attestation_id}: {e}")
        return False


async def start_attestation_session(session: AsyncSession, attestation_id: int) -> bool:
    """Начало сессии прохождения аттестации"""
    try:
        result = await session.execute(
            update(TraineeAttestation)
            .where(TraineeAttestation.id == attestation_id)
            .values(status='in_progress')
        )
        
        if result.rowcount > 0:
            logger.info(f"Начата сессия аттестации {attestation_id}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Ошибка начала сессии аттестации {attestation_id}: {e}")
        return False


async def save_attestation_question_result(session: AsyncSession, attestation_result_id: int,
                                         question_id: int, points_awarded: float, max_points: float) -> bool:
    """Сохранение результата ответа на вопрос аттестации"""
    try:
        question_result = AttestationQuestionResult(
            attestation_result_id=attestation_result_id,
            question_id=question_id,
            points_awarded=points_awarded,
            max_points=max_points
        )
        
        session.add(question_result)
        await session.flush()
        
        logger.info(f"Сохранен результат вопроса {question_id}: {points_awarded}/{max_points}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка сохранения результата вопроса: {e}")
        return False


async def complete_attestation_session(session: AsyncSession, attestation_id: int, 
                                     total_score: float, max_score: float, is_passed: bool) -> bool:
    """Завершение сессии аттестации с результатами"""
    try:
        # Обновляем статус назначения аттестации
        status = 'completed' if is_passed else 'failed'
        result = await session.execute(
            update(TraineeAttestation)
            .where(TraineeAttestation.id == attestation_id)
            .values(status=status)
        )
        
        if result.rowcount > 0:
            logger.info(f"Завершена аттестация {attestation_id} со статусом {status}, результат: {total_score}/{max_score}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Ошибка завершения аттестации {attestation_id}: {e}")
        return False


async def get_trainee_attestation_by_id(session: AsyncSession, attestation_id: int) -> Optional[TraineeAttestation]:
    """Получение назначенной аттестации по ID"""
    try:
        result = await session.execute(
            select(TraineeAttestation)
            .options(
                selectinload(TraineeAttestation.trainee).selectinload(User.work_object),
                selectinload(TraineeAttestation.manager),
                selectinload(TraineeAttestation.attestation).selectinload(Attestation.questions),
                selectinload(TraineeAttestation.assigned_by)
            )
            .where(TraineeAttestation.id == attestation_id)
            .where(TraineeAttestation.is_active == True)
        )
        return result.scalar_one_or_none()
        
    except Exception as e:
        logger.error(f"Ошибка получения аттестации {attestation_id}: {e}")
        return None


async def get_managers_for_attestation(session: AsyncSession, group_id: int) -> List[User]:
    """Получение списка руководителей для назначения аттестации (по группе стажера)"""
    try:
        result = await session.execute(
            select(User)
            .join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, user_roles.c.role_id == Role.id)
            .where(Role.name == "Руководитель")
            .where(User.is_active == True)
            .where(User.is_activated == True)
        )
        return result.scalars().all()
        
    except Exception as e:
        logger.error(f"Ошибка получения руководителей для аттестации: {e}")
        return []


async def create_attestation_result(session: AsyncSession, trainee_id: int, attestation_id: int,
                                  manager_id: int, total_score: float, max_score: float, is_passed: bool) -> Optional[AttestationResult]:
    """Создание результата аттестации"""
    try:
        result = AttestationResult(
            trainee_id=trainee_id,
            attestation_id=attestation_id,
            manager_id=manager_id,
            total_score=total_score,
            max_score=max_score,
            is_passed=is_passed
        )
        
        session.add(result)
        await session.flush()
        
        logger.info(f"Создан результат аттестации для стажера {trainee_id}: {total_score}/{max_score}, пройдена: {is_passed}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка создания результата аттестации: {e}")
        return None


async def check_all_stages_completed(session: AsyncSession, trainee_id: int) -> bool:
    """Проверка что стажер прошел ВСЕ этапы траектории перед аттестацией"""
    try:
        # Получаем траекторию стажера
        trainee_path = await get_trainee_learning_path(session, trainee_id)
        if not trainee_path:
            logger.warning(f"У стажера {trainee_id} нет назначенной траектории")
            return False
            
        # Получаем все этапы траектории
        stages_result = await session.execute(
            select(LearningStage)
            .where(LearningStage.learning_path_id == trainee_path.learning_path_id)
            .order_by(LearningStage.order_number)
        )
        all_stages = stages_result.scalars().all()
        
        if not all_stages:
            logger.warning(f"В траектории стажера {trainee_id} нет этапов")
            return False
            
        # Получаем прогресс стажера по этапам
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)
        
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


async def get_trainee_attestation_status(session: AsyncSession, trainee_id: int, attestation_id: int) -> str:
    """Получение статуса аттестации стажера: ⛔️ - не назначена, 🟡 - назначена, ✅ - пройдена"""
    try:
        # Проверяем назначена ли аттестация
        assignment_result = await session.execute(
            select(TraineeAttestation)
            .where(TraineeAttestation.trainee_id == trainee_id)
            .where(TraineeAttestation.attestation_id == attestation_id)
            .where(TraineeAttestation.is_active == True)
        )
        assignment = assignment_result.scalar_one_or_none()
        
        if not assignment:
            return "⛔️"  # Не назначена
            
        if assignment.status == "completed":
            return "✅"  # Пройдена
        elif assignment.status in ["assigned", "in_progress"]:
            return "🟡"  # Назначена
        else:
            return "⛔️"  # Провалена или отменена
            
    except Exception as e:
        logger.error(f"Ошибка получения статуса аттестации: {e}")
        return "⛔️"


# ===============================
# ФУНКЦИИ ДЛЯ МАССОВОЙ РАССЫЛКИ ТЕСТОВ (TASK 8)
# ===============================

async def broadcast_test_to_groups(session: AsyncSession, test_id: int, group_ids: list, 
                                  sent_by_id: int, bot=None, broadcast_script: str = None,
                                  broadcast_photos: list = None, broadcast_material_id: int = None,
                                  broadcast_docs: list | None = None, target_roles: list = None) -> dict:
    """
    Массовая рассылка пользователям по группам (Task 8 + расширенная версия)
    
    Args:
        session: Сессия БД
        test_id: ID теста (опционально)
        group_ids: Список ID групп
        sent_by_id: ID отправителя
        bot: Экземпляр бота
        broadcast_script: Текст рассылки (обязательно для новой версии)
        broadcast_photos: Список file_id фотографий
        broadcast_material_id: ID материала из базы знаний
        broadcast_docs: Список file_id документов
        target_roles: Список названий ролей для фильтрации получателей (опционально)
    
    Returns:
        dict: Статистика рассылки
    """
    try:
        # Получаем тест (опционально)
        test = None
        if test_id:
            test = await get_test_by_id(session, test_id)
            if not test:
                logger.error(f"Тест {test_id} не найден для рассылки")
                return {"success": False, "error": "Тест не найден"}
        
        # Получаем отправителя
        sender = await get_user_by_id(session, sent_by_id)
        if not sender:
            logger.error(f"Отправитель {sent_by_id} не найден")
            return {"success": False, "error": "Отправитель не найден"}
        
        # Собираем ВСЕХ пользователей из выбранных групп (включая рекрутеров и руководителей)
        all_users = []
        group_names = []
        
        for group_id in group_ids:
            group = await get_group_by_id(session, group_id)
            if group:
                group_names.append(group.name)
                # Получаем ВСЕХ пользователей из группы (все роли)
                users_in_group = await get_all_users_in_group(session, group_id)
                all_users.extend(users_in_group)
        
        # Убираем дубликаты пользователей (если они в нескольких группах)
        unique_users = {}
        for user in all_users:
            unique_users[user.id] = user
        final_users = list(unique_users.values())
        
        # КРИТИЧЕСКИ ВАЖНО: Исключаем отправителя из списка получателей
        final_users = [user for user in final_users if user.id != sent_by_id]
        
        # Фильтрация по выбранным ролям (если указаны)
        if target_roles:
            filtered_users = []
            for user in final_users:
                # Получаем названия ролей пользователя
                user_role_names = [role.name for role in user.roles]
                # Проверяем, есть ли хотя бы одна из целевых ролей
                if any(role_name in target_roles for role_name in user_role_names):
                    filtered_users.append(user)
            final_users = filtered_users
            
            logger.info(f"Фильтрация по ролям {target_roles}: {len(final_users)} получателей")
        
        # ФАЗА 1: Оптимизированное batch создание доступов к тестам
        if test_id:
            try:
                # 1. Получаем все существующие доступы одним запросом
                user_ids = [user.id for user in final_users]
                if user_ids:  # Защита от пустого списка
                    existing_result = await session.execute(
                        select(TraineeTestAccess.trainee_id, TraineeTestAccess.test_id)
                        .where(
                            TraineeTestAccess.test_id == test_id,
                            TraineeTestAccess.trainee_id.in_(user_ids),
                            TraineeTestAccess.is_active == True
                        )
                    )
                    existing_pairs = {(row.trainee_id, row.test_id) for row in existing_result}
                    
                    # 2. Формируем список новых доступов (исключаем существующие)
                    # ВАЖНО: Явно указываем granted_date, т.к. default=datetime.now работает только для ORM объектов
                    # datetime уже импортирован в начале файла (database/db.py:6)
                    new_accesses = []
                    for user in final_users:
                        if (user.id, test_id) not in existing_pairs:
                            new_accesses.append({
                                'trainee_id': user.id,
                                'test_id': test_id,
                                'granted_by_id': sent_by_id,
                                'granted_date': datetime.now(),  # Явно указываем дату
                                'is_active': True
                            })
                    
                    # 3. Массовая вставка через bulk insert (1 запрос вместо N)
                    # Используем Model класс напрямую - SQLAlchemy 2.0+ поддерживает это
                    # Альтернатива: можно использовать TraineeTestAccess.__table__ если нужна явность
                    if new_accesses:
                        await session.execute(
                            insert(TraineeTestAccess).values(new_accesses)
                        )
                        await session.commit()
                        logger.info(f"Массово создано {len(new_accesses)} новых доступов к тесту {test_id}")
                    else:
                        logger.info(f"Все доступы к тесту {test_id} уже существуют для выбранных пользователей")
                else:
                    logger.warning(f"Список пользователей для рассылки пуст")
                    
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка массового создания доступов к тесту {test_id}: {e}")
                # Не падаем полностью - продолжаем отправку уведомлений
        
        # ФАЗА 2: Отправляем уведомления ПАРАЛЛЕЛЬНО
        semaphore = asyncio.Semaphore(20)  # Максимум 20 одновременно
        
        async def send_to_user(user):
            async with semaphore:
                try:
                    # Отправляем расширенное уведомление
                    if broadcast_script and bot:
                        success = await send_broadcast_notification(
                            bot=bot,
                            user_tg_id=user.tg_id,
                            broadcast_script=broadcast_script,
                            broadcast_photos=broadcast_photos or [],
                            broadcast_material_id=broadcast_material_id,
                            test_id=test_id,
                            broadcast_docs=broadcast_docs or []
                        )
                        return (True, None) if success else (False, None)
                    elif test_id and bot:
                        # Старая логика для обратной совместимости
                        await send_notification_about_new_test(session, bot, user.id, test_id, sent_by_id)
                        return (True, None)
                    else:
                        return (False, None)
                        
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user.id}: {e}")
                    return (False, e)
        
        # Отправляем параллельно с ограничением
        results = await asyncio.gather(*[send_to_user(user) for user in final_users], return_exceptions=True)
        
        # Подсчитываем результаты
        total_sent = sum(1 for r in results if isinstance(r, tuple) and r[0])
        failed_sends = len(results) - total_sent
        
        # Логируем результат рассылки
        test_name = test.name if test else "без теста"
        logger.info(f"Рассылка ({test_name}) завершена: {total_sent} отправлено, {failed_sends} ошибок")
        
        return {
            "success": True,
            "test_name": test.name if test else None,
            "group_names": group_names,
            "total_users": len(final_users),
            "total_sent": total_sent,
            "failed_sends": failed_sends
        }
        
    except Exception as e:
        logger.error(f"Ошибка массовой рассылки: {e}")
        return {"success": False, "error": str(e)}


# =====================================================================
# CRUD ОПЕРАЦИИ ДЛЯ БАЗЫ ЗНАНИЙ (Task 9)
# =====================================================================

async def create_knowledge_folder(session: AsyncSession, name: str, created_by_id: int, description: str = None) -> Optional[KnowledgeFolder]:
    """Создание новой папки базы знаний"""
    try:
        # Проверяем уникальность названия папки
        existing = await session.execute(
            select(KnowledgeFolder).where(
                func.lower(KnowledgeFolder.name) == func.lower(name),
                KnowledgeFolder.is_active == True
            )
        )
        if existing.scalar_one_or_none():
            logger.error(f"Папка с названием '{name}' уже существует")
            return None
            
        folder = KnowledgeFolder(
            name=name,
            description=description,
            created_by_id=created_by_id
        )
        session.add(folder)
        await session.flush()
        await session.refresh(folder)
        
        logger.info(f"Создана папка базы знаний: {name} (ID: {folder.id})")
        return folder
        
    except Exception as e:
        logger.error(f"Ошибка создания папки базы знаний: {e}")
        return None


async def get_all_knowledge_folders(session: AsyncSession) -> List[KnowledgeFolder]:
    """Получение всех активных папок базы знаний"""
    try:
        result = await session.execute(
            select(KnowledgeFolder)
            .where(KnowledgeFolder.is_active == True)
            .options(
                selectinload(KnowledgeFolder.materials),
                selectinload(KnowledgeFolder.accessible_groups)
            )
            .order_by(KnowledgeFolder.created_date.desc())
        )
        folders = result.scalars().all()
        
        logger.info(f"Получено {len(folders)} папок базы знаний")
        return list(folders)
        
    except Exception as e:
        logger.error(f"Ошибка получения папок базы знаний: {e}")
        return []


async def get_knowledge_folder_by_id(session: AsyncSession, folder_id: int) -> Optional[KnowledgeFolder]:
    """Получение папки базы знаний по ID"""
    try:
        result = await session.execute(
            select(KnowledgeFolder)
            .where(KnowledgeFolder.id == folder_id, KnowledgeFolder.is_active == True)
            .options(
                selectinload(KnowledgeFolder.materials),
                selectinload(KnowledgeFolder.accessible_groups)
            )
        )
        folder = result.scalar_one_or_none()
        
        if folder:
            logger.info(f"Найдена папка: {folder.name} (ID: {folder.id})")
        else:
            logger.warning(f"Папка с ID {folder_id} не найдена")
            
        return folder
        
    except Exception as e:
        logger.error(f"Ошибка получения папки базы знаний по ID {folder_id}: {e}")
        return None


async def update_knowledge_folder_name(session: AsyncSession, folder_id: int, new_name: str, updated_by_id: int) -> bool:
    """Изменение названия папки базы знаний"""
    try:
        # Проверяем существование папки
        folder = await get_knowledge_folder_by_id(session, folder_id)
        if not folder:
            logger.error(f"Папка с ID {folder_id} не найдена")
            return False
            
        # Проверяем уникальность нового названия
        existing = await session.execute(
            select(KnowledgeFolder).where(
                func.lower(KnowledgeFolder.name) == func.lower(new_name),
                KnowledgeFolder.id != folder_id,
                KnowledgeFolder.is_active == True
            )
        )
        if existing.scalar_one_or_none():
            logger.error(f"Папка с названием '{new_name}' уже существует")
            return False
            
        old_name = folder.name
        folder.name = new_name
        await session.flush()
        
        logger.info(f"Папка переименована: '{old_name}' -> '{new_name}' (ID: {folder_id})")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка изменения названия папки {folder_id}: {e}")
        return False


async def delete_knowledge_folder(session: AsyncSession, folder_id: int, deleted_by_id: int) -> bool:
    """Удаление папки базы знаний (soft delete)"""
    try:
        folder = await get_knowledge_folder_by_id(session, folder_id)
        if not folder:
            logger.error(f"Папка с ID {folder_id} не найдена")
            return False
            
        # Помечаем папку как удаленную
        folder.is_active = False
        
        # Помечаем все материалы в папке как удаленные
        await session.execute(
            update(KnowledgeMaterial)
            .where(KnowledgeMaterial.folder_id == folder_id)
            .values(is_active=False)
        )
        
        await session.flush()
        
        logger.info(f"Удалена папка: {folder.name} (ID: {folder_id}) со всеми материалами")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка удаления папки {folder_id}: {e}")
        return False


async def create_knowledge_material(session: AsyncSession, folder_id: int, name: str, material_type: str,
                                  content: str, created_by_id: int, description: str = None, photos: list = None) -> Optional[KnowledgeMaterial]:
    """Создание нового материала в папке базы знаний"""
    try:
        # Проверяем существование папки
        folder = await get_knowledge_folder_by_id(session, folder_id)
        if not folder:
            logger.error(f"Папка с ID {folder_id} не найдена")
            return None

        # Получаем следующий номер порядка для материала в папке
        result = await session.execute(
            select(func.max(KnowledgeMaterial.order_number))
            .where(KnowledgeMaterial.folder_id == folder_id, KnowledgeMaterial.is_active == True)
        )
        max_order = result.scalar() or 0

        material = KnowledgeMaterial(
            folder_id=folder_id,
            name=name,
            description=description,
            material_type=material_type,
            content=content,
            photos=photos if photos else None,
            order_number=max_order + 1,
            created_by_id=created_by_id
        )
        session.add(material)
        await session.flush()
        await session.refresh(material)
        
        logger.info(f"Создан материал '{name}' в папке '{folder.name}' (ID: {material.id})")
        return material
        
    except Exception as e:
        logger.error(f"Ошибка создания материала: {e}")
        return None


async def get_knowledge_material_by_id(session: AsyncSession, material_id: int) -> Optional[KnowledgeMaterial]:
    """Получение материала базы знаний по ID"""
    try:
        result = await session.execute(
            select(KnowledgeMaterial)
            .where(KnowledgeMaterial.id == material_id, KnowledgeMaterial.is_active == True)
            .options(selectinload(KnowledgeMaterial.folder))
        )
        material = result.scalar_one_or_none()
        
        if material:
            logger.info(f"Найден материал: {material.name} (ID: {material.id})")
        else:
            logger.warning(f"Материал с ID {material_id} не найден")
            
        return material
        
    except Exception as e:
        logger.error(f"Ошибка получения материала по ID {material_id}: {e}")
        return None


async def delete_knowledge_material(session: AsyncSession, material_id: int, deleted_by_id: int) -> bool:
    """Удаление материала базы знаний (soft delete)"""
    try:
        material = await get_knowledge_material_by_id(session, material_id)
        if not material:
            logger.error(f"Материал с ID {material_id} не найден")
            return False
            
        # Помечаем материал как удаленный
        material.is_active = False
        await session.flush()
        
        logger.info(f"Удален материал: {material.name} (ID: {material_id})")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка удаления материала {material_id}: {e}")
        return False


async def set_folder_access_groups(session: AsyncSession, folder_id: int, group_ids: List[int], updated_by_id: int) -> bool:
    """Установка доступа к папке для определенных групп"""
    try:
        # Проверяем существование папки
        folder = await get_knowledge_folder_by_id(session, folder_id)
        if not folder:
            logger.error(f"Папка с ID {folder_id} не найдена")
            return False
            
        # Удаляем все текущие связи доступа
        await session.execute(
            delete(folder_group_access).where(folder_group_access.c.folder_id == folder_id)
        )
        
        # Если список групп не пустой, добавляем новые связи
        if group_ids:
            # Проверяем существование всех групп
            result = await session.execute(
                select(Group).where(Group.id.in_(group_ids), Group.is_active == True)
            )
            existing_groups = result.scalars().all()
            existing_group_ids = [group.id for group in existing_groups]
            
            # Добавляем связи только для существующих групп
            for group_id in existing_group_ids:
                await session.execute(
                    insert(folder_group_access).values(
                        folder_id=folder_id,
                        group_id=group_id
                    )
                )
            
            group_names = [group.name for group in existing_groups]
            logger.info(f"Установлен доступ к папке '{folder.name}' для групп: {', '.join(group_names)}")
        else:
            # Пустой список означает доступ для всех групп
            logger.info(f"Установлен доступ к папке '{folder.name}' для всех групп")
            
        await session.flush()
        return True
        
    except Exception as e:
        logger.error(f"Ошибка установки доступа к папке {folder_id}: {e}")
        return False


async def check_folder_access(session: AsyncSession, folder_id: int, user_id: int) -> bool:
    """Проверка доступа пользователя к папке базы знаний"""
    try:
        # Получаем пользователя с его группами
        result = await session.execute(
            select(User)
            .where(User.id == user_id, User.is_active == True)
            .options(selectinload(User.groups))
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.error(f"Пользователь с ID {user_id} не найден")
            return False
            
        # Получаем папку с доступными группами
        folder = await get_knowledge_folder_by_id(session, folder_id)
        if not folder:
            return False
            
        # Если папка не имеет ограничений по группам - доступ открыт для всех
        if not folder.accessible_groups:
            return True
            
        # Проверяем пересечение групп пользователя с доступными группами папки
        user_group_ids = {group.id for group in user.groups if group.is_active}
        accessible_group_ids = {group.id for group in folder.accessible_groups if group.is_active}
        
        has_access = bool(user_group_ids.intersection(accessible_group_ids))
        
        if has_access:
            logger.info(f"Пользователь {user.full_name} имеет доступ к папке '{folder.name}'")
        else:
            logger.info(f"Пользователь {user.full_name} НЕ имеет доступа к папке '{folder.name}'")
            
        return has_access
        
    except Exception as e:
        logger.error(f"Ошибка проверки доступа к папке {folder_id} для пользователя {user_id}: {e}")
        return False


async def get_accessible_knowledge_folders_for_user(session: AsyncSession, user_id: int) -> List[KnowledgeFolder]:
    """Получение всех папок базы знаний, доступных пользователю"""
    try:
        # Получаем пользователя с его группами
        result = await session.execute(
            select(User)
            .where(User.id == user_id, User.is_active == True)
            .options(selectinload(User.groups))
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.error(f"Пользователь с ID {user_id} не найден")
            return []
            
        user_group_ids = [group.id for group in user.groups if group.is_active]
        
        # Получаем все папки
        all_folders = await get_all_knowledge_folders(session)
        accessible_folders = []
        
        for folder in all_folders:
            # Если папка не имеет ограничений - доступна всем
            if not folder.accessible_groups:
                accessible_folders.append(folder)
            else:
                # Проверяем пересечение групп
                accessible_group_ids = [group.id for group in folder.accessible_groups if group.is_active]
                if set(user_group_ids).intersection(set(accessible_group_ids)):
                    accessible_folders.append(folder)
        
        logger.info(f"Пользователь {user.full_name} имеет доступ к {len(accessible_folders)} папкам из {len(all_folders)}")
        return accessible_folders
        
    except Exception as e:
        logger.error(f"Ошибка получения доступных папок для пользователя {user_id}: {e}")
        return []


async def get_folder_access_info(session: AsyncSession, folder_id: int) -> dict:
    """Получение информации о доступе к папке"""
    try:
        folder = await get_knowledge_folder_by_id(session, folder_id)
        if not folder:
            return {"success": False, "error": "Папка не найдена"}
            
        if not folder.accessible_groups:
            return {
                "success": True,
                "access_type": "all_groups",
                "description": "все группы",
                "groups": []
            }
        else:
            group_names = [group.name for group in folder.accessible_groups if group.is_active]
            return {
                "success": True,
                "access_type": "specific_groups",
                "description": "; ".join(group_names),
                "groups": group_names
            }
            
    except Exception as e:
        logger.error(f"Ошибка получения информации о доступе к папке {folder_id}: {e}")
        return {"success": False, "error": str(e)}


async def fix_knowledge_base_permissions(session: AsyncSession) -> bool:
    """Исправление прав доступа к базе знаний для существующих пользователей"""
    try:
        # Проверяем существование права view_knowledge_base
        result = await session.execute(
            select(Permission).where(Permission.name == "view_knowledge_base")
        )
        permission = result.scalar_one_or_none()

        if not permission:
            # Создаем право если его нет
            permission = Permission(
                name="view_knowledge_base",
                description="Просмотр базы знаний"
            )
            session.add(permission)
            await session.flush()
            logger.info("Создано право view_knowledge_base")

        # Назначаем право просмотра базы знаний ролям: Стажер, Сотрудник, Наставник, Руководитель
        roles_to_update = ["Стажер", "Сотрудник", "Наставник", "Руководитель"]
        updated_any = False

        for role_name in roles_to_update:
            result = await session.execute(
                select(Role).where(Role.name == role_name)
            )
            role = result.scalar_one_or_none()

            if role:
                # Проверяем, есть ли уже связь
                result = await session.execute(
                    select(role_permissions).where(
                        and_(
                            role_permissions.c.role_id == role.id,
                            role_permissions.c.permission_id == permission.id
                        )
                    )
                )
                existing_link = result.fetchone()

                if not existing_link:
                    # Добавляем связь
                    stmt = insert(role_permissions).values(
                        role_id=role.id,
                        permission_id=permission.id
                    )
                    await session.execute(stmt)
                    logger.info(f"Назначено право view_knowledge_base роли {role_name}")
                    updated_any = True
                else:
                    logger.info(f"Право view_knowledge_base уже назначено роли {role_name}")
            else:
                logger.error(f"Роль {role_name} не найдена")

        return updated_any or True  # Возвращаем True если хоть что-то обновили или если все уже было назначено

    except Exception as e:
        logger.error(f"Ошибка исправления прав доступа к базе знаний: {e}")
        return False


async def fix_recruiter_take_tests_permission(session: AsyncSession) -> bool:
    """
    Одноразовая миграция: добавление права take_tests для роли Рекрутер
    
    Эта функция проверяет и добавляет право take_tests рекрутерам, если его нет.
    Идемпотентна - можно запускать многократно без побочных эффектов.
    
    Returns:
        bool: True если что-то обновили или все уже назначено, False при ошибке
    """
    try:
        # Проверяем существование права take_tests
        result = await session.execute(
            select(Permission).where(Permission.name == "take_tests")
        )
        permission = result.scalar_one_or_none()
        
        if not permission:
            logger.error("Право take_tests не найдено в системе")
            return False
        
        # Получаем роль Рекрутер
        result = await session.execute(
            select(Role).where(Role.name == "Рекрутер")
        )
        role = result.scalar_one_or_none()
        
        if not role:
            logger.error("Роль Рекрутер не найдена")
            return False
        
        # Проверяем, есть ли уже связь
        result = await session.execute(
            select(role_permissions).where(
                and_(
                    role_permissions.c.role_id == role.id,
                    role_permissions.c.permission_id == permission.id
                )
            )
        )
        existing_link = result.fetchone()
        
        if not existing_link:
            # Добавляем связь
            stmt = insert(role_permissions).values(
                role_id=role.id,
                permission_id=permission.id
            )
            await session.execute(stmt)
            logger.info("✅ Назначено право take_tests роли Рекрутер (миграция)")
            return True
        else:
            logger.info("✓ Право take_tests уже назначено роли Рекрутер")
            return True
    
    except Exception as e:
        logger.error(f"❌ Ошибка миграции прав рекрутера: {e}")
        return False


async def get_trajectory_usage_info(session: AsyncSession, trajectory_id: int) -> dict:
    """Получение информации об использовании траектории"""
    try:
        from database.models import User, TraineeLearningPath
        
        # Получаем всех стажеров, использующих эту траекторию
        trainees_result = await session.execute(
            select(User)
            .join(TraineeLearningPath, User.id == TraineeLearningPath.trainee_id)
            .where(TraineeLearningPath.learning_path_id == trajectory_id)
        )
        trainees = trainees_result.scalars().all()
        
        # Получаем общее количество пользователей
        total_users_result = await session.execute(
            select(func.count(TraineeLearningPath.trainee_id))
            .where(TraineeLearningPath.learning_path_id == trajectory_id)
        )
        total_users = total_users_result.scalar() or 0
        
        return {
            'trainees': trainees,
            'trainees_count': len(trainees),
            'total_users': total_users
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения информации об использовании траектории {trajectory_id}: {e}")
        return {
            'trainees': [],
            'trainees_count': 0,
            'total_users': 0
        }


async def delete_learning_path(session: AsyncSession, trajectory_id: int) -> bool:
    """Удаление траектории обучения"""
    try:
        from database.models import TraineeLearningPath, TraineeStageProgress, TraineeSessionProgress, TestResult, Test, TraineeTestAccess, LearningSession, LearningStage, AttestationResult, AttestationQuestionResult, TraineeAttestation, LearningPath, session_tests
        
        # Получаем траекторию
        trajectory = await get_learning_path_by_id(session, trajectory_id)
        if not trajectory:
            return False
        
        # Удаляем все связанные данные в правильном порядке
        
        # 1. Удаляем прогресс сессий стажеров
        await session.execute(
            delete(TraineeSessionProgress)
            .where(TraineeSessionProgress.stage_progress_id.in_(
                select(TraineeStageProgress.id)
                .select_from(TraineeStageProgress)
                .join(TraineeLearningPath, TraineeStageProgress.trainee_path_id == TraineeLearningPath.id)
                .where(TraineeLearningPath.learning_path_id == trajectory_id)
            ))
        )
        
        # 2. Удаляем прогресс этапов стажеров
        await session.execute(
            delete(TraineeStageProgress)
            .where(TraineeStageProgress.trainee_path_id.in_(
                select(TraineeLearningPath.id)
                .select_from(TraineeLearningPath)
                .where(TraineeLearningPath.learning_path_id == trajectory_id)
            ))
        )
        
        # 3. Удаляем прогресс стажеров по траектории
        await session.execute(
            delete(TraineeLearningPath)
            .where(TraineeLearningPath.learning_path_id == trajectory_id)
        )
        
        # 4. Удаляем только результаты тестов траектории (тесты остаются в системе)
        # Получаем ID тестов через правильную связь через session_tests
        await session.execute(
            delete(TestResult)
            .where(TestResult.test_id.in_(
                select(session_tests.c.test_id)
                .select_from(session_tests)
                .join(LearningSession, session_tests.c.session_id == LearningSession.id)
                .join(LearningStage, LearningSession.stage_id == LearningStage.id)
                .where(LearningStage.learning_path_id == trajectory_id)
            ))
        )
        
        # 5. Удаляем доступы к тестам траектории (тесты остаются в системе)
        # Получаем ID тестов через правильную связь через session_tests
        await session.execute(
            delete(TraineeTestAccess)
            .where(TraineeTestAccess.test_id.in_(
                select(session_tests.c.test_id)
                .select_from(session_tests)
                .join(LearningSession, session_tests.c.session_id == LearningSession.id)
                .join(LearningStage, LearningSession.stage_id == LearningStage.id)
                .where(LearningStage.learning_path_id == trajectory_id)
            ))
        )
        
        # 6. Удаляем прогресс сессий стажеров (если остались) перед удалением сессий
        await session.execute(
            delete(TraineeSessionProgress)
            .where(TraineeSessionProgress.session_id.in_(
                select(LearningSession.id)
                .select_from(LearningSession)
                .join(LearningStage, LearningSession.stage_id == LearningStage.id)
                .where(LearningStage.learning_path_id == trajectory_id)
            ))
        )
        
        # 7. Удаляем только связи тестов с сессиями (тесты остаются в системе)
        await session.execute(
            delete(session_tests)
            .where(session_tests.c.session_id.in_(
                select(LearningSession.id)
                .select_from(LearningSession)
                .join(LearningStage, LearningSession.stage_id == LearningStage.id)
                .where(LearningStage.learning_path_id == trajectory_id)
            ))
        )
        
        # 8. Удаляем сессии этапов
        await session.execute(
            delete(LearningSession)
            .where(LearningSession.stage_id.in_(
                select(LearningStage.id)
                .select_from(LearningStage)
                .where(LearningStage.learning_path_id == trajectory_id)
            ))
        )
        
        # 9. Удаляем прогресс этапов стажеров (если остались) перед удалением этапов
        await session.execute(
            delete(TraineeStageProgress)
            .where(TraineeStageProgress.stage_id.in_(
                select(LearningStage.id)
                .select_from(LearningStage)
                .where(LearningStage.learning_path_id == trajectory_id)
            ))
        )
        
        # 10. Удаляем этапы траектории
        await session.execute(
            delete(LearningStage)
            .where(LearningStage.learning_path_id == trajectory_id)
        )
        
        # 11. Удаляем только связи с аттестацией (аттестация остается в системе)
        if trajectory.attestation_id:
            attestation_id = trajectory.attestation_id
            
            # 11.1. Удаляем результаты ответов на вопросы аттестации
            await session.execute(
                delete(AttestationQuestionResult)
                .where(AttestationQuestionResult.attestation_result_id.in_(
                    select(AttestationResult.id)
                    .select_from(AttestationResult)
                    .where(AttestationResult.attestation_id == attestation_id)
                ))
            )
            
            # 9.2. Удаляем результаты аттестации
            await session.execute(
                delete(AttestationResult)
                .where(AttestationResult.attestation_id == attestation_id)
            )
            
            # 9.3. Удаляем назначения аттестаций стажерам
            await session.execute(
                delete(TraineeAttestation)
                .where(TraineeAttestation.attestation_id == attestation_id)
            )
            
            # 9.4. Обнуляем ссылку на аттестацию в траектории (аттестация остается в системе)
            await session.execute(
                update(LearningPath)
                .where(LearningPath.id == trajectory_id)
                .values(attestation_id=None)
            )
        
        # 10. Удаляем саму траекторию
        await session.execute(
            delete(LearningPath)
            .where(LearningPath.id == trajectory_id)
        )
        
        # Подтверждаем транзакцию
        await session.commit()
        
        logger.info(f"Траектория {trajectory_id} успешно удалена")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка удаления траектории {trajectory_id}: {e}")
        return False


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    """
    Полное удаление пользователя и ВСЕХ связанных данных
    
    Args:
        session: Сессия БД
        user_id: ID пользователя для удаления
        
    Returns:
        bool: True если успешно, False при ошибке
    """
    try:
        from database.models import (
            User, TestResult, Mentorship, TraineeLearningPath, TraineeStageProgress,
            TraineeSessionProgress, AttestationResult, AttestationQuestionResult,
            TraineeAttestation, TraineeManager, TraineeTestAccess, Test, TestQuestion,
            Attestation, AttestationQuestion, LearningPath, LearningStage, LearningSession,
            KnowledgeFolder, KnowledgeMaterial, Group, Object, user_roles, user_groups,
            user_objects, session_tests
        )
        
        # Проверяем существование пользователя
        user = await get_user_by_id(session, user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return False
        
        logger.info(f"Начинаем удаление пользователя {user_id}: {user.full_name}")
        
        # 1. Удаляем AttestationQuestionResult (по attestation_result_id из AttestationResult)
        await session.execute(
            delete(AttestationQuestionResult)
            .where(AttestationQuestionResult.attestation_result_id.in_(
                select(AttestationResult.id)
                .select_from(AttestationResult)
                .where(
                    (AttestationResult.trainee_id == user_id) |
                    (AttestationResult.manager_id == user_id)
                )
            ))
        )
        logger.info(f"Удалены AttestationQuestionResult для пользователя {user_id}")
        
        # 2. Удаляем AttestationResult
        await session.execute(
            delete(AttestationResult)
            .where(
                (AttestationResult.trainee_id == user_id) |
                (AttestationResult.manager_id == user_id)
            )
        )
        logger.info(f"Удалены AttestationResult для пользователя {user_id}")
        
        # 3. Удаляем TraineeSessionProgress (через TraineeLearningPath)
        await session.execute(
            delete(TraineeSessionProgress)
            .where(TraineeSessionProgress.stage_progress_id.in_(
                select(TraineeStageProgress.id)
                .select_from(TraineeStageProgress)
                .join(TraineeLearningPath, TraineeStageProgress.trainee_path_id == TraineeLearningPath.id)
                .where(
                    (TraineeLearningPath.trainee_id == user_id) |
                    (TraineeLearningPath.assigned_by_id == user_id)
                )
            ))
        )
        logger.info(f"Удалены TraineeSessionProgress для пользователя {user_id}")
        
        # 4. Удаляем TraineeStageProgress (через TraineeLearningPath)
        await session.execute(
            delete(TraineeStageProgress)
            .where(TraineeStageProgress.trainee_path_id.in_(
                select(TraineeLearningPath.id)
                .select_from(TraineeLearningPath)
                .where(
                    (TraineeLearningPath.trainee_id == user_id) |
                    (TraineeLearningPath.assigned_by_id == user_id)
                )
            ))
        )
        logger.info(f"Удалены TraineeStageProgress для пользователя {user_id}")
        
        # 5. Удаляем TraineeLearningPath
        await session.execute(
            delete(TraineeLearningPath)
            .where(
                (TraineeLearningPath.trainee_id == user_id) |
                (TraineeLearningPath.assigned_by_id == user_id)
            )
        )
        logger.info(f"Удалены TraineeLearningPath для пользователя {user_id}")
        
        # 6. Удаляем TraineeAttestation
        await session.execute(
            delete(TraineeAttestation)
            .where(
                (TraineeAttestation.trainee_id == user_id) |
                (TraineeAttestation.manager_id == user_id) |
                (TraineeAttestation.assigned_by_id == user_id)
            )
        )
        logger.info(f"Удалены TraineeAttestation для пользователя {user_id}")
        
        # 7. Удаляем TraineeManager
        await session.execute(
            delete(TraineeManager)
            .where(
                (TraineeManager.trainee_id == user_id) |
                (TraineeManager.manager_id == user_id) |
                (TraineeManager.assigned_by_id == user_id)
            )
        )
        logger.info(f"Удалены TraineeManager для пользователя {user_id}")
        
        # 8. Удаляем TraineeTestAccess
        await session.execute(
            delete(TraineeTestAccess)
            .where(
                (TraineeTestAccess.trainee_id == user_id) |
                (TraineeTestAccess.granted_by_id == user_id)
            )
        )
        logger.info(f"Удалены TraineeTestAccess для пользователя {user_id}")
        
        # 9. Удаляем TestResult
        await session.execute(
            delete(TestResult)
            .where(TestResult.user_id == user_id)
        )
        logger.info(f"Удалены TestResult для пользователя {user_id}")
        
        # 10. Удаляем Mentorship
        await session.execute(
            delete(Mentorship)
            .where(
                (Mentorship.mentor_id == user_id) |
                (Mentorship.trainee_id == user_id) |
                (Mentorship.assigned_by_id == user_id)
            )
        )
        logger.info(f"Удалены Mentorship для пользователя {user_id}")
        
        # 11. Обнуляем created_by_id для Test (тесты остаются в системе)
        await session.execute(
            update(Test)
            .where(Test.creator_id == user_id)
            .values(creator_id=None)
        )
        logger.info(f"Обнулен creator_id для тестов пользователя {user_id}")
        
        # 12. Обнуляем created_by_id для Attestation (аттестации остаются в системе)
        await session.execute(
            update(Attestation)
            .where(Attestation.created_by_id == user_id)
            .values(created_by_id=None)
        )
        logger.info(f"Обнулен created_by_id для аттестаций пользователя {user_id}")
        
        # 13. Обнуляем created_by_id для LearningPath (траектории остаются в системе)
        await session.execute(
            update(LearningPath)
            .where(LearningPath.created_by_id == user_id)
            .values(created_by_id=None)
        )
        logger.info(f"Обнулен created_by_id для траекторий пользователя {user_id}")
        
        # 14. Обнуляем created_by_id для KnowledgeMaterial (материалы остаются в системе)
        await session.execute(
            update(KnowledgeMaterial)
            .where(KnowledgeMaterial.created_by_id == user_id)
            .values(created_by_id=None)
        )
        logger.info(f"Обнулен created_by_id для материалов пользователя {user_id}")
        
        # 15. Обнуляем created_by_id для KnowledgeFolder (папки остаются в системе)
        await session.execute(
            update(KnowledgeFolder)
            .where(KnowledgeFolder.created_by_id == user_id)
            .values(created_by_id=None)
        )
        logger.info(f"Обнулен created_by_id для папок знаний пользователя {user_id}")
        
        # 16. Обнуляем created_by_id для Object (объекты остаются в системе)
        await session.execute(
            update(Object)
            .where(Object.created_by_id == user_id)
            .values(created_by_id=None)
        )
        logger.info(f"Обнулен created_by_id для объектов пользователя {user_id}")
        
        # 17. Обнуляем created_by_id для Group (группы остаются в системе)
        await session.execute(
            update(Group)
            .where(Group.created_by_id == user_id)
            .values(created_by_id=None)
        )
        logger.info(f"Обнулен created_by_id для групп пользователя {user_id}")
        
        # 18. Удаляем many-to-many связи
        await session.execute(
            delete(user_roles)
            .where(user_roles.c.user_id == user_id)
        )
        logger.info(f"Удалены user_roles для пользователя {user_id}")
        
        await session.execute(
            delete(user_groups)
            .where(user_groups.c.user_id == user_id)
        )
        logger.info(f"Удалены user_groups для пользователя {user_id}")
        
        await session.execute(
            delete(user_objects)
            .where(user_objects.c.user_id == user_id)
        )
        logger.info(f"Удалены user_objects для пользователя {user_id}")
        
        # 19. Удаляем самого пользователя
        await session.execute(
            delete(User)
            .where(User.id == user_id)
        )
        logger.info(f"Удален сам пользователь {user_id}")
        
        # Подтверждаем транзакцию
        await session.commit()
        
        logger.info(f"Пользователь {user_id} успешно удален со всеми связанными данными")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
        return False