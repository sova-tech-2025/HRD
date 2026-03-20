"""
Обработчики для управления объектами.
Включает создание, изменение и управление объектами.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import (
    check_user_permission,
    create_object,
    delete_object,
    ensure_company_id,
    get_all_objects,
    get_object_by_id,
    get_object_users,
    get_user_by_tg_id,
    get_user_roles,
    update_object_name,
)
from bot.keyboards.keyboards import (
    get_main_menu_keyboard,
    get_object_delete_confirmation_keyboard,
    get_object_delete_selection_keyboard,
    get_object_management_keyboard,
    get_object_rename_confirmation_keyboard,
    get_object_selection_keyboard,
)
from bot.states.states import ObjectManagementStates
from bot.utils.auth.auth import check_auth
from bot.utils.logger import log_user_action, log_user_error
from bot.utils.validation.input import validate_object_name

router = Router()


@router.message(F.text.in_(["Объекты", "Объекты 📍"]))
async def cmd_objects(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Объекты'"""
    try:
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return

        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            return

        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_objects")
        if not has_permission:
            await message.answer(
                "❌ <b>Недостаточно прав</b>\n\nУ тебя нет прав для управления объектами.", parse_mode="HTML"
            )
            return

        await message.answer(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n\n"
            "В данном меню ты можешь:\n"
            "1. Создавать объекты\n"
            "2. Посмотреть существующие объекты\n"
            "3. Менять названия объектам\n"
            "4. Удалять объекты",
            reply_markup=get_object_management_keyboard(),
            parse_mode="HTML",
        )
        log_user_action(user.tg_id, "objects_menu_opened", "Открыл меню управления объектами")
    except Exception as e:
        await message.answer("Произошла ошибка при открытии меню объектов")
        log_user_error(message.from_user.id, "objects_menu_error", str(e))


@router.callback_query(F.data == "create_object")
async def callback_create_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик создания нового объекта"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            await callback.answer()
            return

        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_objects")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\nУ тебя нет прав для управления объектами.", parse_mode="HTML"
            )
            await callback.answer()
            return

        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n➕<b>Создание объекта</b>➕\nВведи название объекта на клавиатуре",
            parse_mode="HTML",
        )
        await state.set_state(ObjectManagementStates.waiting_for_object_name)
        await callback.answer()
        log_user_action(user.tg_id, "object_creation_started", "Начал создание объекта")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_creation_start_error", str(e))


@router.message(ObjectManagementStates.waiting_for_object_name)
async def process_object_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка введенного названия объекта"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            await state.clear()
            return

        # Получаем company_id
        company_id = await ensure_company_id(session, state, message.from_user.id)
        if company_id is None:
            await message.answer("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            log_user_error(message.from_user.id, "object_company_missing", "company_id not resolved")
            return

        object_name = message.text.strip()

        # Валидация названия
        if not validate_object_name(object_name):
            await message.answer(
                "❌ Некорректное название объекта.\n"
                "Название должно содержать только буквы, цифры, пробелы, знаки препинания и слеш для адресов.\n"
                "Попробуй еще раз:"
            )
            return

        # Создаем объект
        obj = await create_object(session, object_name, user.id, company_id)
        if obj:
            await message.answer(
                f"📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
                f"✅<b>Объект успешно создан</b>\n"
                f"Название объекта: <b>{object_name}</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
            log_user_action(user.tg_id, "object_created", f"Создал объект: {object_name}")
        else:
            await message.answer(
                "❌ Ошибка создания объекта. Возможно, объект с таким названием уже существует.\n"
                "Попробуй другое название:",
            )
            return

        await state.clear()
    except Exception as e:
        await message.answer("Произошла ошибка при создании объекта")
        log_user_error(message.from_user.id, "object_creation_error", str(e))
        await state.clear()


@router.callback_query(F.data == "edit_object")
async def callback_edit_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик изменения объектов"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            await callback.answer()
            return

        # Получаем company_id
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await callback.answer()
            await state.clear()
            log_user_error(callback.from_user.id, "object_edit_company_missing", "company_id not resolved")
            return

        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_objects")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\nУ тебя нет прав для управления объектами.", parse_mode="HTML"
            )
            await callback.answer()
            return

        objects = await get_all_objects(session, company_id)

        if not objects:
            await callback.message.edit_text(
                "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n❌ Объектов не найдено. Сначала создай объект.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n👇<b>Выбери объект для изменения:</b>",
            reply_markup=get_object_selection_keyboard(objects, page=0),
            parse_mode="HTML",
        )
        await state.update_data(objects=objects, current_page=0)
        await state.set_state(ObjectManagementStates.waiting_for_object_selection)
        await callback.answer()
        log_user_action(user.tg_id, "object_edit_started", "Начал изменение объекта")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_edit_start_error", str(e))


@router.callback_query(F.data.startswith("select_object:"), ObjectManagementStates.waiting_for_object_selection)
async def callback_select_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора объекта для изменения"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            await callback.answer()
            await state.clear()
            return

        object_id = int(callback.data.split(":")[1])
        obj = await get_object_by_id(session, object_id, company_id=user.company_id)

        if not obj:
            await callback.message.edit_text("Объект не найден")
            await callback.answer()
            await state.clear()
            return

        # Получаем company_id
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await callback.answer()
            await state.clear()
            log_user_error(callback.from_user.id, "object_selection_company_missing", "company_id not resolved")
            return

        # Получаем пользователей объекта
        object_users = await get_object_users(session, object_id, company_id=company_id)
        user_list = ""
        if object_users:
            for object_user in object_users:
                user_roles = await get_user_roles(session, object_user.id)
                role_names = ", ".join([role.name for role in user_roles])
                user_list += f"{object_user.full_name} ({role_names})\n"
        else:
            user_list = "Пользователей на объекте нет"

        await callback.message.edit_text(
            f"📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            f"👉Ты выбрал объект: <b>{obj.name}</b>\n"
            f"Сотрудников на объекте: <b>{len(object_users)}</b>\n\n"
            f"<b>ФИО сотрудников:</b>\n"
            f"{user_list}\n\n"
            f"Введи новое название для данного объекта и отправь чат-боту",
            parse_mode="HTML",
        )

        # Сохраняем данные объекта для дальнейшего использования
        await state.update_data(object_id=object_id, old_name=obj.name)
        await state.set_state(ObjectManagementStates.waiting_for_new_object_name)
        await callback.answer()

        log_user_action(user.tg_id, "object_selected", f"Выбрал объект для изменения: {obj.name}")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_selection_error", str(e))
        await state.clear()


@router.callback_query(F.data.startswith("objects_page:"), ObjectManagementStates.waiting_for_object_selection)
async def callback_objects_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации объектов"""
    try:
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        objects = data.get("objects", [])

        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n👇<b>Выбери объект для изменения:</b>",
            reply_markup=get_object_selection_keyboard(objects, page=page),
            parse_mode="HTML",
        )
        await state.update_data(current_page=page)
        await callback.answer()
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при навигации")
        log_user_error(callback.from_user.id, "objects_pagination_error", str(e))


@router.callback_query(F.data == "cancel_edit", ObjectManagementStates.waiting_for_object_selection)
async def callback_cancel_object_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены выбора объекта - возврат в меню управления объектами"""
    try:
        # Получение пользователя для логирования
        user = await get_user_by_tg_id(session, callback.from_user.id)

        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n\n"
            "В данном меню ты можешь:\n"
            "1. Создавать объекты\n"
            "2. Посмотреть существующие объекты\n"
            "3. Менять названия объектам\n"
            "4. Удалять объекты",
            reply_markup=get_object_management_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()

        if user:
            log_user_action(user.tg_id, "object_edit_cancelled", "Отменил выбор объекта")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_edit_cancel_error", str(e))
        await state.clear()


@router.message(ObjectManagementStates.waiting_for_new_object_name)
async def process_new_object_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия объекта"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            await state.clear()
            return

        new_name = message.text.strip()
        data = await state.get_data()
        object_id = data.get("object_id")
        old_name = data.get("old_name")

        # Валидация названия
        if not validate_object_name(new_name):
            await message.answer(
                "❌ Некорректное название объекта.\n"
                "Название должно содержать только буквы, цифры, пробелы, знаки препинания и слеш для адресов.\n"
                "Попробуй еще раз:"
            )
            return

        # Проверяем, что название отличается от старого
        if new_name == old_name:
            await message.answer("❌ Новое название совпадает со старым.\nВведи другое название:")
            return

        await message.answer(
            f"📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            f"Ты уверен, что хочешь изменить название?\n\n"
            f"Старое название: <b>{old_name}</b>\n"
            f"Новое название: <b>{new_name}</b>",
            reply_markup=get_object_rename_confirmation_keyboard(object_id),
            parse_mode="HTML",
        )

        await state.update_data(new_name=new_name)
        await state.set_state(ObjectManagementStates.waiting_for_object_rename_confirmation)
        log_user_action(
            user.tg_id, "object_rename_confirmation", f"Подтверждение переименования: {old_name} -> {new_name}"
        )
    except Exception as e:
        await message.answer("Произошла ошибка при обработке нового названия")
        log_user_error(message.from_user.id, "object_rename_process_error", str(e))
        await state.clear()


@router.callback_query(
    F.data.startswith("confirm_object_rename:"), ObjectManagementStates.waiting_for_object_rename_confirmation
)
async def callback_confirm_object_rename(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения переименования объекта"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            await callback.answer()
            await state.clear()
            return

        object_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        new_name = data.get("new_name")
        old_name = data.get("old_name")
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await callback.answer()
            await state.clear()
            log_user_error(callback.from_user.id, "object_rename_company_missing", "company_id not resolved")
            return

        if await update_object_name(session, object_id, new_name, company_id=company_id):
            await callback.message.edit_text(
                f"📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n✅<b>Название успешно изменено на:</b>\n<b>{new_name}</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
            log_user_action(user.tg_id, "object_renamed", f"Переименовал объект: {old_name} -> {new_name}")
        else:
            await callback.message.edit_text(
                "❌ Ошибка переименования объекта. Возможно, объект с таким названием уже существует.",
                reply_markup=get_main_menu_keyboard(),
            )

        await state.clear()
        await callback.answer()
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при переименовании")
        log_user_error(callback.from_user.id, "object_rename_confirm_error", str(e))
        await state.clear()


@router.callback_query(F.data == "cancel_object_rename", ObjectManagementStates.waiting_for_object_rename_confirmation)
async def callback_cancel_object_rename(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены переименования объекта"""
    try:
        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n❌<b>Ты отменил изменение</b>",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        log_user_action(callback.from_user.id, "object_rename_cancelled", "Отменил переименование объекта")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_rename_cancel_error", str(e))
        await state.clear()


@router.callback_query(F.data == "manage_delete_object")
async def callback_manage_delete_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Удалить объект'"""
    try:
        # Проверяем права доступа
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user or not await check_user_permission(session, user.id, "manage_objects"):
            await callback.answer("У тебя нет прав для удаления объектов", show_alert=True)
            return

        # Получаем company_id
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.answer("Не удалось определить компанию. Обнови сессию командой /start.", show_alert=True)
            await state.clear()
            log_user_error(callback.from_user.id, "object_delete_company_missing", "company_id not resolved")
            return

        # Получаем все объекты
        objects = await get_all_objects(session, company_id)
        if not objects:
            await callback.message.edit_text(
                "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
                "🗑️<b>Удаление объекта</b>🗑️\n\n"
                "❌ <b>Объекты не найдены!</b>\n\n"
                "Сначала создай объекты для удаления.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
            return

        # Показываем предупреждение и список объектов
        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            "🗑️<b>Удаление объекта</b>🗑️\n\n"
            "⚠️ <b>Внимание!</b> Это действие необратимо!\n"
            "Объект будет полностью удален из системы.\n\n"
            "Выбери объект для удаления:",
            reply_markup=get_object_delete_selection_keyboard(objects),
            parse_mode="HTML",
        )
        await state.set_state(ObjectManagementStates.waiting_for_delete_object_selection)
        await callback.answer()

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при получении списка объектов")
        log_user_error(callback.from_user.id, "object_delete_list_error", str(e))
        await state.clear()


@router.callback_query(F.data.startswith("object_delete_page:"))
async def callback_object_delete_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации при выборе объекта для удаления"""
    try:
        page = int(callback.data.split(":")[1])

        # Получаем company_id
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.answer("Не удалось определить компанию. Обнови сессию командой /start.", show_alert=True)
            await state.clear()
            log_user_error(callback.from_user.id, "object_delete_page_company_missing", "company_id not resolved")
            return

        # Получаем все объекты
        objects = await get_all_objects(session, company_id)
        if not objects:
            await callback.answer("Объекты не найдены", show_alert=True)
            return

        # Показываем страницу
        page_objects = objects[page * 5 : (page + 1) * 5]
        if not page_objects:
            await callback.answer("Страница пуста", show_alert=True)
            return

        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            "🗑️<b>Удаление объекта</b>🗑️\n\n"
            "⚠️ <b>Внимание!</b> Это действие необратимо!\n"
            "Объект будет полностью удален из системы.\n\n"
            "Выбери объект для удаления:",
            reply_markup=get_object_delete_selection_keyboard(objects, page),
            parse_mode="HTML",
        )
        await callback.answer()

    except Exception as e:
        await callback.answer("Ошибка при переключении страницы", show_alert=True)
        log_user_error(callback.from_user.id, "object_delete_page_error", str(e))


@router.callback_query(F.data.startswith("delete_object:"))
async def callback_delete_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора объекта для удаления"""
    try:
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return

        object_id = int(callback.data.split(":")[1])

        # Проверяем повторное нажатие на тот же объект
        data = await state.get_data()
        selected_object_id = data.get("selected_object_id")
        last_error_message = data.get("last_error_message")

        # Если пользователь нажал на тот же объект и состояние не изменилось
        if selected_object_id == object_id and last_error_message:
            await callback.answer(last_error_message, show_alert=True)
            return

        # Получаем информацию об объекте
        object_obj = await get_object_by_id(session, object_id, company_id=user.company_id)
        if not object_obj:
            await callback.answer("Объект не найден", show_alert=True)
            return

        # Получаем company_id из контекста
        data = await state.get_data()
        company_id = data.get("company_id")

        # Проверяем, можно ли удалить объект (включает все проверки: user_objects, internship_object_id, work_object_id)
        users_in_object = await get_object_users(session, object_id, company_id=company_id)
        if users_in_object:
            error_msg = f"❌ В объекте есть пользователи ({len(users_in_object)} чел.)"
            await callback.message.edit_text(
                "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
                "🗑️<b>Удаление объекта</b>🗑️\n\n"
                f"❌ <b>Нельзя удалить объект!</b>\n\n"
                f"<b>Объект:</b> {object_obj.name}\n"
                f"<b>ID:</b> {object_obj.id}\n"
                f"<b>Создан:</b> {object_obj.created_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"⚠️ <b>В объекте есть пользователи ({len(users_in_object)} чел.)</b>\n"
                f"Сначала удали всех пользователей из объекта или измени их объекты стажировки/работы.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
            await state.update_data(selected_object_id=object_id, last_error_message=error_msg)
            await state.clear()
            return

        # Показываем подтверждение удаления
        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            "🗑️<b>Удаление объекта</b>🗑️\n\n"
            f"<b>Объект:</b> {object_obj.name}\n"
            f"<b>ID:</b> {object_obj.id}\n"
            f"<b>Создан:</b> {object_obj.created_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ <b>Внимание!</b> Это действие необратимо!\n"
            f"Объект будет полностью удален из системы.\n\n"
            f"Ты уверен, что хочешь удалить этот объект?",
            reply_markup=get_object_delete_confirmation_keyboard(object_id),
            parse_mode="HTML",
        )
        await state.set_state(ObjectManagementStates.waiting_for_delete_confirmation)
        await state.update_data(selected_object_id=object_id, last_error_message=None)
        await callback.answer()

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при получении информации об объекте")
        log_user_error(callback.from_user.id, "object_delete_info_error", str(e))
        await state.clear()


@router.callback_query(F.data.startswith("confirm_object_delete:"))
async def callback_confirm_delete_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения удаления объекта"""
    try:
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            await state.clear()
            return

        object_id = int(callback.data.split(":")[1])

        # Получаем информацию об объекте
        object_obj = await get_object_by_id(session, object_id, company_id=user.company_id)
        if not object_obj:
            await callback.message.edit_text("Объект не найден")
            await state.clear()
            return

        # Удаляем объект
        success = await delete_object(session, object_id, callback.from_user.id, company_id=user.company_id)

        if success:
            await callback.message.edit_text(
                "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
                "🗑️<b>Удаление объекта</b>🗑️\n\n"
                f"✅ <b>Объект успешно удален!</b>\n\n"
                f"<b>Удаленный объект:</b> {object_obj.name}\n"
                f"<b>ID:</b> {object_obj.id}\n\n"
                f"Объект полностью удален из системы.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )
            log_user_action(
                callback.from_user.id, "object_deleted", f"Удалил объект {object_obj.name} (ID: {object_id})"
            )
        else:
            await callback.message.edit_text(
                "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
                "🗑️<b>Удаление объекта</b>🗑️\n\n"
                f"❌ <b>Не удалось удалить объект!</b>\n\n"
                f"<b>Объект:</b> {object_obj.name}\n"
                f"<b>ID:</b> {object_obj.id}\n\n"
                f"Возможно, объект используется в системе.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML",
            )

        await state.clear()
        await callback.answer()

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при удалении объекта")
        log_user_error(callback.from_user.id, "object_delete_error", str(e))
        await state.clear()


@router.callback_query(F.data == "cancel_object_delete")
async def callback_cancel_delete_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены удаления объекта"""
    try:
        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n\n"
            "В данном меню ты можешь:\n"
            "1. Создавать объекты\n"
            "2. Посмотреть существующие объекты\n"
            "3. Менять названия объектам\n"
            "4. Удалять объекты",
            reply_markup=get_object_management_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        log_user_action(callback.from_user.id, "object_delete_cancelled", "Отменил удаление объекта")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_delete_cancel_error", str(e))
        await state.clear()
