from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Role, user_roles
from bot.utils.logger import logger


async def is_admin_user(session: AsyncSession, user_id: int) -> bool:
    """Проверяет, есть ли у пользователя роль ADMIN в БД."""
    stmt = (
        select(func.count())
        .select_from(user_roles)
        .join(Role, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user_id, Role.name == "ADMIN")
    )
    result = await session.execute(stmt)
    return result.scalar() > 0


def admin_inclusive_role_filter(role_names: list[str]):
    """Возвращает SQLAlchemy фильтр, включающий указанные роли + ADMIN.

    Использование: .where(admin_inclusive_role_filter(["Наставник", "Руководитель"]))
    """
    return or_(Role.name.in_(role_names), Role.name == "ADMIN")


async def exit_admin_role(session: AsyncSession, user_id: int) -> bool:
    """Выход из ADMIN: удаляет роль ADMIN, назначает Рекрутер. Необратимо."""
    try:
        # Получаем id ролей ADMIN и Рекрутер
        admin_role = await session.execute(select(Role).where(Role.name == "ADMIN"))
        admin_role = admin_role.scalar_one_or_none()
        recruiter_role = await session.execute(select(Role).where(Role.name == "Рекрутер"))
        recruiter_role = recruiter_role.scalar_one_or_none()

        if not admin_role or not recruiter_role:
            logger.error(f"Не найдена роль ADMIN или Рекрутер при выходе из ADMIN для user_id={user_id}")
            return False

        # Удаляем роль ADMIN
        await session.execute(
            delete(user_roles).where(
                user_roles.c.user_id == user_id,
                user_roles.c.role_id == admin_role.id,
            )
        )

        # Назначаем роль Рекрутер
        await session.execute(insert(user_roles).values(user_id=user_id, role_id=recruiter_role.id))

        await session.commit()
        logger.info(f"Пользователь {user_id} вышел из роли ADMIN, назначен Рекрутер")
        return True

    except Exception as e:
        logger.error(f"Ошибка выхода из роли ADMIN для user_id={user_id}: {e}")
        await session.rollback()
        return False
