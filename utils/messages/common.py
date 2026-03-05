"""Формирование текстовых сообщений для общих хэндлеров (профиль, меню)."""
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_roles
from utils.bot.roles import get_primary_role


async def format_profile_text(user, session: AsyncSession) -> str:
    """Универсальная функция формирования текста профиля для всех ролей"""
    roles = await get_user_roles(session, user.id)
    primary_role = get_primary_role(roles)

    groups_str = ", ".join([group.name for group in user.groups]) if user.groups else "Не указана"
    groups_label = "Группы" if user.groups and len(user.groups) > 1 else "Группа"

    internship_obj = user.internship_object.name if user.internship_object else "Не указан"
    work_obj = user.work_object.name if user.work_object else "Не указан"

    username_display = f"@{user.username}" if user.username else "Не указан"

    profile_text = f"""🦸🏻‍♂️ <b>Пользователь:</b> {user.full_name}

<b>Телефон:</b> {user.phone_number}
<b>Username:</b> {username_display}
<b>Номер:</b> #{user.id}
<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M')}

━━━━━━━━━━━━

🗂️ <b>Статус ▾</b>
<b>{groups_label}:</b> {groups_str}
<b>Роль:</b> {primary_role}

━━━━━━━━━━━━

📍 <b>Объект ▾</b>"""

    if primary_role == "Стажер":
        profile_text += f"""
<b>Стажировки:</b> {internship_obj}
<b>Работы:</b> {work_obj}"""
    else:
        profile_text += f"""
<b>Работы:</b> {work_obj}"""

    return profile_text


def get_main_menu_text(is_inline: bool = True) -> str:
    """Текст главного меню.

    is_inline=True — для наставника/стажёра (с HTML bold),
    is_inline=False — для остальных ролей.
    """
    if is_inline:
        return (
            "☰ <b>Главное меню</b>\n\n"
            "Используй команды бота или кнопки клавиатуры для навигации по системе"
        )
    return (
        "☰ Главное меню\n\n"
        "Используй команды бота или кнопки клавиатуры для навигации по системе."
    )


def get_reload_menu_text() -> str:
    """Текст при перезагрузке клавиатуры."""
    return (
        "🔄 <b>Клавиатура обновлена</b>\n\n"
        "Твоя клавиатура обновлена согласно текущей роли. Используй кнопки для навигации по системе."
    )


def get_reload_inline_menu_text() -> str:
    """Текст при перезагрузке инлайн-меню (наставник/стажёр)."""
    return (
        "☰ <b>Главное меню</b>\n\n"
        "Используй кнопки для навигации по системе"
    )
