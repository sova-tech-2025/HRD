from __future__ import annotations

from sqlalchemy import func, insert, select, text

from bot.database.models import Permission, Role, role_permissions
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger

FRANCHISEE_ROLE = "Франчайзи"
FRANCHISEE_DESCRIPTION = "Прокачанный сотрудник: администрирует пользователей в рамках своих объектов"

NEW_PERMISSIONS = {
    "send_broadcast": "Отправка рассылок",
    "view_tests": "Просмотр тестов без редактирования",
    "view_learning_paths": "Просмотр траекторий без редактирования",
}

FRANCHISEE_PERMISSIONS = [
    "view_profile",
    "edit_profile",
    "view_trainee_list",
    "manage_trainees",
    "manage_users",
    "assign_mentors",
    "view_mentorship",
    "view_test_results",
    "view_knowledge_base",
    "view_tests",
    "take_tests",
    "grant_test_access",
    "view_learning_paths",
    "send_broadcast",
]

# Права, которые нужно доустановить Рекрутеру (поведение Рекрутера не сужается)
RECRUITER_EXTRA_PERMISSIONS = ["send_broadcast", "manage_users"]


class RoleProvisioningRepository(BaseRepository):
    """Идемпотентное создание роли «Франчайзи», новых прав и их выдача.

    Безопасно вызывать при каждом старте (init_db) на свежей и существующей БД.
    """

    async def _ensure_permission(self, name: str, description: str) -> Permission:
        result = await self.session.execute(select(Permission).where(Permission.name == name))
        permission = result.scalar_one_or_none()
        if permission is None:
            permission = Permission(name=name, description=description)
            self.session.add(permission)
            await self.session.flush()
        return permission

    async def _ensure_role(self, name: str, description: str) -> Role:
        result = await self.session.execute(select(Role).where(Role.name == name))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=name, description=description)
            self.session.add(role)
            await self.session.flush()
            logger.info(f"Роль {name} создана")
        return role

    async def _grant(self, role: Role, permission_name: str) -> None:
        perm_result = await self.session.execute(select(Permission).where(Permission.name == permission_name))
        permission = perm_result.scalar_one_or_none()
        if permission is None:
            return
        exists = await self.session.execute(
            select(func.count())
            .select_from(role_permissions)
            .where(role_permissions.c.role_id == role.id, role_permissions.c.permission_id == permission.id)
        )
        if exists.scalar() == 0:
            await self.session.execute(insert(role_permissions).values(role_id=role.id, permission_id=permission.id))

    async def ensure_schema(self) -> None:
        """Идемпотентная DDL-миграция: таблица user_work_objects (для прод-БД).

        Дублирует Base.metadata.create_all, но не зависит от порядка импорта моделей.
        """
        await self.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_work_objects (
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    object_id INTEGER NOT NULL REFERENCES objects(id),
                    PRIMARY KEY (user_id, object_id)
                )
                """
            )
        )
        await self.session.commit()

    async def provision_franchisee_role(self) -> None:
        try:
            await self.ensure_schema()

            for name, description in NEW_PERMISSIONS.items():
                await self._ensure_permission(name, description)

            franchisee = await self._ensure_role(FRANCHISEE_ROLE, FRANCHISEE_DESCRIPTION)
            for perm_name in FRANCHISEE_PERMISSIONS:
                await self._grant(franchisee, perm_name)

            recruiter_result = await self.session.execute(select(Role).where(Role.name == "Рекрутер"))
            recruiter = recruiter_result.scalar_one_or_none()
            if recruiter is not None:
                for perm_name in RECRUITER_EXTRA_PERMISSIONS:
                    await self._grant(recruiter, perm_name)

            await self.session.commit()
            logger.info("Роль «Франчайзи» и права актуализированы")
        except Exception as e:
            logger.error(f"Ошибка провизионинга роли «Франчайзи»: {e}")
            await self.session.rollback()
