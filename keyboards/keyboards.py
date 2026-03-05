from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.media.photo import get_trainee_menu_photo, get_mentor_menu_photo, get_main_menu_photo


# Тексты кнопок главного меню для всех ролей
# Используется для валидации ввода - чтобы случайное нажатие на меню не сохранялось как данные
MAIN_MENU_TEXTS = {
    # Общие для всех
    "Мой профиль 🦸🏻‍♂️",
    "Помощь ❓",
    "Помощь❓",
    "База знаний 📁️",
    "База знаний 📒",
    "Мои тесты 📋",
    "Мои тесты 🗒",
    "Мои тесты 📁",  # старая версия или опечатка
    "Посмотреть баллы 📊",
    # Стажер
    "Траектория обучения 📖",
    "Мой наставник 🎓",
    "Тесты траектории 🗺️",
    # Рекрутер
    "Рассылка ✈️",
    "Тесты 📄",
    "Наставники 🦉",
    "Наставники 🎓",  # возможная путаница с "Мой наставник"
    "Стажеры 🐣",
    "Группы 🗂️",
    "Объекты 📍",
    "Траектория 📖",
    "Все пользователи 🚸",
    "Новые пользователи ➕",
    "Компания 🏢",
    # Наставник
    "Панель наставника 🎓",
    "☰ Главное меню",
    # Руководитель
    "Аттестация ✔️",
    # Главное меню (текст)
    "≡ Главное меню",
}


def is_main_menu_text(text: str) -> bool:
    """Проверяет, является ли текст кнопкой главного меню"""
    return text.strip() in MAIN_MENU_TEXTS


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для приветствия незарегистрированных пользователей"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Зарегистрироваться", callback_data="register:normal")],
        [InlineKeyboardButton(text="У меня есть код", callback_data="register:with_code")]
    ])
    return keyboard


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


def get_role_selection_keyboard(is_editing: bool = False) -> InlineKeyboardMarkup:
    import os
    allow_auto_role = os.getenv("ALLOW_AUTO_ROLE_ASSIGNMENT", "false").lower() == "true"
    default_role = os.getenv("DEFAULT_ROLE", "Стажер")
    
    # Базовые роли
    all_roles = [
        ("Стажёр", "Стажер"),
        ("Сотрудник", "Сотрудник"), 
        ("Наставник", "Наставник"),
        ("Рекрутер", "Рекрутер"),
        ("Руководитель", "Руководитель")
    ]
    
    keyboard_buttons = []
    
    # Если включено автоназначение, добавляем рекомендуемую роль вверху
    if allow_auto_role:
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"🚀 {default_role} (рекомендуемая роль)", 
            callback_data=f"role:{default_role}"
        )])
    
    # Добавляем остальные роли, исключая дублирование с рекомендуемой
    for display_name, role_name in all_roles:
        if not (allow_auto_role and role_name == default_role):
            keyboard_buttons.append([InlineKeyboardButton(text=display_name, callback_data=f"role:{role_name}")])
    
    # В режиме редактирования показываем "Назад", иначе "Отмена"
    if is_editing:
        keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_edit")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_registration")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_trainee_inline_menu() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура главного меню стажера"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мой профиль 🦸🏻‍♂️", callback_data="trainee_profile")],
        [InlineKeyboardButton(text="Траектория обучения 📖", callback_data="trainee_trajectory")],
        [InlineKeyboardButton(text="База знаний 📒", callback_data="trainee_knowledge_base")],
        [InlineKeyboardButton(text="Мой наставник 🎓", callback_data="trainee_my_mentor")],
        [InlineKeyboardButton(text="Тесты траектории 🗺️", callback_data="trainee_trajectory_tests")],
        [InlineKeyboardButton(text="Мои тесты 📋", callback_data="trainee_my_tests")],
        [InlineKeyboardButton(text="Посмотреть баллы 📊", callback_data="trainee_scores")],
        [InlineKeyboardButton(text="Помощь ❓", callback_data="trainee_help")],
    ])


def get_recruiter_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мой профиль 🦸🏻‍♂️")],
            [KeyboardButton(text="Рассылка ✈️")],
            [KeyboardButton(text="Тесты 📄")],
            [KeyboardButton(text="Мои тесты 📋")],
            [KeyboardButton(text="Наставники 🦉")],
            [KeyboardButton(text="Стажеры 🐣")],
            [KeyboardButton(text="Группы 🗂️")],
            [KeyboardButton(text="Объекты 📍")],
            [KeyboardButton(text="Траектория 📖")],
            [KeyboardButton(text="База знаний 📁️")],
            [KeyboardButton(text="Все пользователи 🚸")],
            [KeyboardButton(text="Новые пользователи ➕")],
            [KeyboardButton(text="Помощь ❓")],
            [KeyboardButton(text="Компания 🏢")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_mentor_keyboard() -> ReplyKeyboardMarkup:
    """Минимальная reply-клавиатура для наставника (fallback)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="☰ Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_mentor_inline_menu() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура главного меню наставника (по Figma)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мой профиль 🦸🏻‍♂️", callback_data="mentor_profile")],
        [InlineKeyboardButton(text="База знаний 📒", callback_data="mentor_knowledge_base")],
        [InlineKeyboardButton(text="Мои тесты 🗒", callback_data="mentor_my_tests")],
        [InlineKeyboardButton(text="Панель наставника 🎓", callback_data="mentor_panel")],
        [InlineKeyboardButton(text="Помощь ❓", callback_data="mentor_help")],
    ])


def get_employee_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для роли Сотрудник (прошедшие аттестацию стажеры) - Task 7"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мой профиль 🦸🏻‍♂️")],
            [KeyboardButton(text="Мои тесты 📋")],
            [KeyboardButton(text="База знаний 📁️")],
            [KeyboardButton(text="Помощь ❓")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_manager_keyboard() -> ReplyKeyboardMarkup:
    """Меню для руководителя - проведение аттестаций стажеров (обновлено для Task 7 + Knowledge Base)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мой профиль 🦸🏻‍♂️")],
            [KeyboardButton(text="Аттестация ✔️")],
            [KeyboardButton(text="Мои тесты 📋")],
            [KeyboardButton(text="База знаний 📁️")],
            [KeyboardButton(text="Помощь ❓")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_user_selection_keyboard(users: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком пользователей"""

    keyboard = []
    
    for user in users:
        button = InlineKeyboardButton(
            text=f"{user.full_name} ({user.username or 'нет юзернейма'})",
            callback_data=f"user:{user.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_action_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с действиями для пользователя"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Изменить роль", callback_data=f"change_role:{user_id}")],
            [InlineKeyboardButton(text="Назад к списку", callback_data="back_to_users")]
        ]
    )
    return keyboard


def get_role_change_keyboard(user_id: int, roles: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора новой роли пользователя"""

    keyboard = []
    
    for role in roles:
        button = InlineKeyboardButton(
            text=role.name,
            callback_data=f"set_role:{user_id}:{role.name}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data=f"cancel_role_change:{user_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(user_id: int, role_name: str, action: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для подтверждения изменения роли"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{action}:{user_id}:{role_name}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_role_change:{user_id}")]
        ]
    )
    return keyboard


def get_menu_by_role(primary_role: str):
    """Возвращает (keyboard, photo_source) для главного меню по роли.

    Для Стажера/Наставника — инлайн-клавиатура + фото баннера.
    Для остальных — reply-клавиатура + фото main menu (если настроено).
    """
    if primary_role == "Стажер":
        return get_trainee_inline_menu(), get_trainee_menu_photo()
    elif primary_role == "Наставник":
        return get_mentor_inline_menu(), get_mentor_menu_photo()
    else:
        return get_keyboard_by_role(primary_role), get_main_menu_photo()


def get_keyboard_by_role(roles) -> ReplyKeyboardMarkup:
    """Получение клавиатуры по роли пользователя (обновлено для Task 7)"""
    # Поддержка как строки, так и списка ролей
    if isinstance(roles, str):
        role_names = [roles]
    else:
        role_names = roles if isinstance(roles, list) else [role.name for role in roles]
    
    # Определяем клавиатуру по приоритету ролей
    if "Рекрутер" in role_names:
        return get_recruiter_keyboard()
    elif "Руководитель" in role_names:
        return get_manager_keyboard()
    elif "Наставник" in role_names:
        return get_mentor_keyboard()
    elif "Сотрудник" in role_names:
        return get_employee_keyboard()
    elif "Стажер" in role_names:
        return None
    else:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Мой профиль"), KeyboardButton(text="Помощь")]],
            resize_keyboard=True
        )


def get_role_management_keyboard(roles: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора роли, чьи права будут изменяться"""

    keyboard = []
    
    for role in roles:
        button = InlineKeyboardButton(
            text=role.name,
            callback_data=f"manage_role_permissions:{role.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_permission_action_keyboard(role_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с действиями для управления правами роли """

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Расширить возможности роли", callback_data=f"add_permission:{role_id}")],
            [InlineKeyboardButton(text="Ограничить возможности роли", callback_data=f"remove_permission:{role_id}")],
            [InlineKeyboardButton(text="Назад к списку ролей", callback_data="back_to_roles")]
        ]
    )
    return keyboard


def get_permission_selection_keyboard(permissions: list, role_id: int, action: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора права """

    keyboard = []
    
    for permission in permissions:
        button = InlineKeyboardButton(
            text=f"{permission.description}",
            callback_data=f"select_permission:{action}:{role_id}:{permission.name}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data=f"cancel_permission_selection:{role_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_permission_confirmation_keyboard(role_id: int, permission_name: str, action: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для подтверждения изменения прав"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_permission:{action}:{role_id}:{permission_name}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_permission_confirmation:{role_id}:{permission_name}")]
        ]
    )
    return keyboard


# =================================
# КЛАВИАТУРЫ ДЛЯ РАБОТЫ С ТЕСТАМИ
# =================================

def get_yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с кнопками Да/Нет"""
    keyboard_buttons = [
        [InlineKeyboardButton(text="✅ Да", callback_data=f"{prefix}:yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"{prefix}:no")]
    ]
    
    # Добавляем кнопку отмены для этапов создания теста
    if prefix in ["more_questions", "materials"]:
        keyboard_buttons.append([InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_test_description_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода описания теста с кнопкой Назад"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="test_back")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="description:skip")],
            [InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")]
        ]
    )
    return keyboard


def get_test_materials_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода материалов теста с кнопкой Назад"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="test_back")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="materials:skip")],
            [InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")]
        ]
    )
    return keyboard


def get_materials_choice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора добавления материалов с кнопкой Назад"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="materials:yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="materials:no")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="test_back")],
            [InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")]
        ]
    )
    return keyboard


def get_test_created_success_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешного создания теста"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 К списку тестов", callback_data="list_tests")],
            [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
        ]
    )
    return keyboard


def get_question_type_keyboard(is_creating_test: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа вопроса"""
    keyboard_buttons = [
        [InlineKeyboardButton(text="Свободный ответ (текст)", callback_data="q_type:text")],
        [InlineKeyboardButton(text="Выбор одного правильного ответа", callback_data="q_type:single_choice")],
        [InlineKeyboardButton(text="Выбор нескольких правильных ответов", callback_data="q_type:multiple_choice")],
        [InlineKeyboardButton(text="Ответ 'Да' или 'Нет'", callback_data="q_type:yes_no")]
    ]
    
    # Разные кнопки отмены в зависимости от контекста
    if is_creating_test:
        keyboard_buttons.append([InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отменить добавление вопроса", callback_data="cancel_question")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_test_edit_menu(test_id: int, session_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура для главного меню редактирования теста
    
    Args:
        test_id: ID теста
        session_id: ID сессии, если тест открыт из редактора траекторий
    """
    # Определяем callback для кнопки "Назад"
    if session_id:
        # Если открыто из редактора траекторий - возвращаемся в редактор сессии
        back_callback = f"edit_session_view:{session_id}"
        back_text = "⬅️ Назад к сессии"
    else:
        # Обычный возврат к детальной информации о тесте
        back_callback = f"test:{test_id}"
        back_text = "⬅️ Назад к тесту"
    
    keyboard_buttons = [
        [
            InlineKeyboardButton(text="✏️ Название/Описание", callback_data=f"edit_test_meta:{test_id}"),
            InlineKeyboardButton(text="🔗 Материалы", callback_data=f"edit_test_materials:{test_id}")
        ],
        [
            InlineKeyboardButton(text="❓ Управление вопросов", callback_data=f"edit_test_questions:{test_id}"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"edit_test_settings:{test_id}")
        ],
        [InlineKeyboardButton(text="👁️ Предпросмотр", callback_data=f"preview_test:{test_id}")]
    ]
    
    # Добавляем кнопку удаления из сессии, только если тест открыт из редактора траекторий
    if session_id:
        keyboard_buttons.append([InlineKeyboardButton(text="🚫 Удалить из сессии", callback_data=f"remove_test_from_session:{session_id}:{test_id}")])
    
    keyboard_buttons.append([InlineKeyboardButton(text=back_text, callback_data=back_callback)])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_test_filter_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора фильтра тестов для рекрутера"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗂️ Мои тесты", callback_data="test_filter:my"),
                InlineKeyboardButton(text="📚 Все тесты", callback_data="test_filter:all")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tests_menu")]
        ]
    )
    return keyboard


def get_simple_test_selection_keyboard(tests: list, page: int = 0, per_page: int = 5, filter_type: str = "all") -> InlineKeyboardMarkup:
    """Создает простую инлайн-клавиатуру со списком тестов с пагинацией"""
    keyboard = []
    
    # Пагинация
    start_index = page * per_page
    end_index = start_index + per_page
    page_tests = tests[start_index:end_index]
    
    # Кнопки тестов для текущей страницы
    for test in page_tests:
        button = InlineKeyboardButton(
            text=f"{test.name} (макс. {test.max_score:.1f} б.)",
            callback_data=f"test:{test.id}"
        )
        keyboard.append([button])
    
    # Навигационные кнопки
    total_pages = (len(tests) + per_page - 1) // per_page
    nav_buttons = []
    
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"tests_list_page:{filter_type}:{page-1}"))
        
        # Информация о странице
        page_info = f"📄 {page+1}/{total_pages}"
        nav_buttons.append(InlineKeyboardButton(text=page_info, callback_data="noop"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"tests_list_page:{filter_type}:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_results_keyboard(test_results: list, page: int = 0, per_page: int = 5, user_role: str = "пользователь", mentor_tg_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура для результатов тестов с пагинацией"""
    keyboard = []
    
    # Пагинация
    total_pages = (len(test_results) + per_page - 1) // per_page if test_results else 0
    
    # Навигационные кнопки (если больше одной страницы)
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"test_scores_page:{page-1}"))
        
        # Информация о странице
        page_info = f"📄 {page+1}/{total_pages}"
        nav_buttons.append(InlineKeyboardButton(text=page_info, callback_data="noop"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"test_scores_page:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    # Кнопка связи с наставником (только для стажеров)
    if user_role == "стажер" and mentor_tg_id:
        keyboard.append([InlineKeyboardButton(text="✍️ Написать наставнику", url=f"tg://user?id={mentor_tg_id}")])
    
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_test_selection_keyboard(tests: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора теста для рассылки (Task 8)"""
    keyboard = []
    
    for test in tests:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{test.name}",
                callback_data=f"broadcast_test:{test.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_groups_selection_keyboard(groups: list, selected_groups: list = None) -> InlineKeyboardMarkup:
    """Клавиатура для выбора групп для рассылки (Task 8)"""
    if selected_groups is None:
        selected_groups = []
    
    keyboard = []
    
    for group in groups:
        # Показываем выбранные группы с галочкой
        if group.id in selected_groups:
            text = f"✅ {group.name}"
        else:
            text = f"{group.name}"
        
        keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"broadcast_group:{group.id}"
            )
        ])
    
    # Кнопка отправки доступна только если выбрана хотя бы одна группа
    if selected_groups:
        keyboard.append([
            InlineKeyboardButton(text="📤 Отправить", callback_data="broadcast_send")
        ])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_success_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешной рассылки (Task 8)"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
        ]
    )
    return keyboard


def get_broadcast_photos_keyboard(has_photos: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для загрузки фото в рассылку"""
    keyboard = []
    
    if has_photos:
        keyboard.append([InlineKeyboardButton(text="✅ Завершить загрузку", callback_data="broadcast_finish_photos")])
    
    keyboard.append([InlineKeyboardButton(text="⏩ Пропустить", callback_data="broadcast_skip_photos")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_folders_keyboard(folders: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора папки для материала в рассылке"""
    keyboard = []
    
    for folder in folders:
        folder_name = folder.name[:30] + "..." if len(folder.name) > 30 else folder.name
        keyboard.append([InlineKeyboardButton(
            text=f"📁 {folder_name}",
            callback_data=f"broadcast_folder:{folder.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="⏩ Пропустить материал", callback_data="broadcast_skip_material")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_materials_keyboard(folder_name: str, materials: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора материала из папки для рассылки"""
    keyboard = []
    
    for material in materials:
        if material.is_active:
            material_name = material.name[:35] + "..." if len(material.name) > 35 else material.name
            material_icon = "🔗" if material.material_type == "link" else "📄"
            keyboard.append([InlineKeyboardButton(
                text=f"{material_icon} {material_name}",
                callback_data=f"broadcast_select_material:{material.id}"
            )])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад к папкам", callback_data="broadcast_back_to_folders")])
    keyboard.append([InlineKeyboardButton(text="⏩ Пропустить материал", callback_data="broadcast_skip_material")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_tests_keyboard(tests: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора теста для рассылки (опционально)"""
    keyboard = []
    
    for test in tests:
        test_name = test.name[:40] + "..." if len(test.name) > 40 else test.name
        keyboard.append([InlineKeyboardButton(
            text=test_name,
            callback_data=f"broadcast_test:{test.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="⏩ Пропустить тест", callback_data="broadcast_skip_test")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_notification_keyboard(test_id: int = None, material_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура для уведомления о рассылке"""
    keyboard = []
    
    if test_id:
        keyboard.append([InlineKeyboardButton(text="Перейти к тесту 🚀", callback_data=f"take_test:{test_id}")])
    
    if material_id:
        keyboard.append([InlineKeyboardButton(text="Материалы 📚", callback_data=f"broadcast_material:{material_id}")])
    
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню раздела рассылки"""
    keyboard = [
        [InlineKeyboardButton(text="📝 Создать рассылку", callback_data="create_broadcast")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_broadcast_roles_selection_keyboard(selected_roles: list = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора ролей для рассылки"""
    if selected_roles is None:
        selected_roles = []
    
    roles = [
        ("Стажер", "trainee"),
        ("Сотрудник", "employee"),
        ("Наставник", "mentor"),
        ("Рекрутер", "recruiter"),
        ("Руководитель", "manager")
    ]
    
    keyboard = InlineKeyboardBuilder()
    
    for role_display, role_key in roles:
        checkmark = "✅ " if role_key in selected_roles else ""
        keyboard.button(
            text=f"{checkmark}{role_display}",
            callback_data=f"broadcast_role:{role_key}"
        )
    
    keyboard.adjust(2)  # 2 кнопки в ряд
    
    # Кнопки управления
    if selected_roles:
        keyboard.row(
            InlineKeyboardButton(text="➡️ Далее", callback_data="broadcast_roles_next")
        )
    
    # Динамический текст кнопки "Все роли" / "Снять все"
    all_roles_set = {"trainee", "employee", "mentor", "recruiter", "manager"}
    if set(selected_roles) == all_roles_set:
        all_button_text = "❌ Снять все"
    else:
        all_button_text = "🌐 Все роли"
    
    keyboard.row(
        InlineKeyboardButton(text=all_button_text, callback_data="broadcast_roles_all"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    
    return keyboard.as_markup()


def get_question_edit_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для редактирования вопроса"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить текст вопроса", callback_data=f"edit_question_text:{question_id}")],
            [InlineKeyboardButton(text="✏️ Изменить ответ", callback_data=f"edit_question_answer:{question_id}")],
            [InlineKeyboardButton(text="✏️ Изменить баллы", callback_data=f"edit_question_points:{question_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить вопрос", callback_data=f"delete_question:{question_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_questions")]
        ]
    )
    return keyboard


def get_stage_selection_keyboard(stages: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора этапа стажировки"""
    keyboard = []
    
    for stage in stages:
        button = InlineKeyboardButton(
            text=f"{stage.order_number}. {stage.name}",
            callback_data=f"stage:{stage.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="🔓 Тест без этапа", callback_data="stage:none")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_actions_keyboard(test_id: int, user_role: str = "creator") -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с действиями для теста"""
    keyboard = []
    
    if user_role == "creator":
        # Кнопки для создателя теста (рекрутера)
        keyboard.extend([
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_test:{test_id}")],
            [InlineKeyboardButton(text="📚 Материалы", callback_data=f"view_materials:{test_id}")],
            [InlineKeyboardButton(text="📊 Результаты", callback_data=f"test_results:{test_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_test:{test_id}")]
        ])
    else:
        # Кнопки для наставника
        keyboard.extend([
            [InlineKeyboardButton(text="🔐 Предоставить доступ стажерам", callback_data=f"grant_access_to_test:{test_id}")],
            [InlineKeyboardButton(text="📚 Материалы", callback_data=f"view_materials:{test_id}")],
            [InlineKeyboardButton(text="📊 Результаты", callback_data=f"test_results:{test_id}")]
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tests")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_question_selection_keyboard(questions: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора вопроса"""
    keyboard = []
    
    for question in questions:
        button = InlineKeyboardButton(
            text=f"Вопрос {question.question_number}",
            callback_data=f"question:{question.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ НАСТАВНИЧЕСТВА
# =================================

def get_trainee_selection_keyboard(trainees: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком стажеров"""
    keyboard = []
    
    for trainee in trainees:
        button = InlineKeyboardButton(
            text=f"{trainee.full_name}",
            callback_data=f"trainee:{trainee.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_mentor_selection_keyboard(mentors: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком наставников"""
    keyboard = []
    
    for mentor in mentors:
        button = InlineKeyboardButton(
            text=f"{mentor.full_name}",
            callback_data=f"mentor:{mentor.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_assignment_confirmation_keyboard(mentor_id: int, trainee_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для подтверждения назначения наставника"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_assignment:{mentor_id}:{trainee_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_assignment")]
        ]
    )
    return keyboard


def get_trainee_actions_keyboard(trainee_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с действиями для стажера"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Добавить тест", callback_data=f"add_test_access:{trainee_id}")],
            [InlineKeyboardButton(text="📊 Результаты тестов", callback_data=f"trainee_results:{trainee_id}")],
            [InlineKeyboardButton(text="👤 Профиль", callback_data=f"trainee_profile:{trainee_id}")],
            [InlineKeyboardButton(text="👨‍🏫 Руководитель", callback_data=f"manager_actions:{trainee_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trainees")]
        ]
    )
    return keyboard


def get_test_access_keyboard(tests: list, trainee_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для предоставления доступа к тестам"""
    keyboard = []
    
    for test in tests:
        button = InlineKeyboardButton(
            text=f"{test.name}",
            callback_data=f"grant_access:{trainee_id}:{test.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ ПРОХОЖДЕНИЯ ТЕСТОВ
# =================================

# Функция удалена - используется get_test_start_keyboard с расширенным функционалом

def get_test_navigation_keyboard(current_question: int, total_questions: int, test_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для навигации по тесту"""
    keyboard = []
    
    # Навигация
    nav_row = []
    if current_question > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Предыдущий", callback_data=f"prev_question:{test_id}"))
    if current_question < total_questions:
        nav_row.append(InlineKeyboardButton(text="Следующий ➡️", callback_data=f"next_question:{test_id}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Завершение теста
    if current_question == total_questions:
        keyboard.append([InlineKeyboardButton(text="✅ Завершить тест", callback_data=f"finish_test:{test_id}")])
    
    keyboard.append([InlineKeyboardButton(text="❌ Прервать тест", callback_data=f"cancel_test:{test_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ
# =================================

def get_unassigned_trainees_keyboard(trainees: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком стажеров без наставника"""
    keyboard = []
    
    for trainee in trainees:
        button = InlineKeyboardButton(
            text=f"{trainee.full_name}",
            callback_data=f"unassigned_trainee:{trainee.id}"
        )
        keyboard.append([button])
    
    if not trainees:
        keyboard.append([InlineKeyboardButton(text="ℹ️ Нет неназначенных стажеров", callback_data="info")])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_start_keyboard(test_id: int, has_previous_result: bool = False, has_material: bool = False) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для начала теста с дополнительными опциями согласно макету 4.5"""
    keyboard = []
    
    # Кнопка начала теста согласно макету 4.6
    start_text = "Начать тест 🚀"
    keyboard.append([InlineKeyboardButton(text=start_text, callback_data=f"start_test:{test_id}")])
    
    # Кнопка просмотра материалов согласно макету 4.7 (только если есть материал)
    if has_material:
        keyboard.append([InlineKeyboardButton(text="Пройти обучение 📖", callback_data=f"view_materials:{test_id}")])
    
    # Кнопка назад согласно макету 4.8
    keyboard.append([InlineKeyboardButton(text="← назад", callback_data="back_to_test_list")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_selection_for_taking_keyboard(tests: list, page: int = 0, per_page: int = 5, callback_prefix: str = "my_tests_page") -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком тестов для прохождения с пагинацией
    
    Args:
        tests: Список тестов
        page: Номер страницы (начиная с 0)
        per_page: Количество тестов на страницу
        callback_prefix: Префикс для callback_data кнопок пагинации (по умолчанию "my_tests_page" для "Мои тесты", 
                        можно использовать "trajectory_tests_page" для "Тесты траектории")
    """
    keyboard = []
    
    # Пагинация: показываем только тесты текущей страницы
    start_index = page * per_page
    end_index = start_index + per_page
    page_tests = tests[start_index:end_index]
    
    for test in page_tests:
        button = InlineKeyboardButton(
            text=f"📋 {test.name}",
            callback_data=f"test:{test.id}"
        )
        keyboard.append([button])
    
    # Навигационные кнопки
    total_pages = (len(tests) + per_page - 1) // per_page
    nav_buttons = []
    
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{callback_prefix}:{page-1}"))
        
        page_info = f"📄 {page+1}/{total_pages}"
        nav_buttons.append(InlineKeyboardButton(text=page_info, callback_data="noop"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"{callback_prefix}:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_question_management_keyboard(question_id: int, is_first: bool, is_last: bool) -> InlineKeyboardMarkup:
    """Клавиатура для управления конкретным вопросом"""
    nav_buttons = []
    if not is_first:
        nav_buttons.append(InlineKeyboardButton(text="⬆️", callback_data=f"move_q_up:{question_id}"))
    if not is_last:
        nav_buttons.append(InlineKeyboardButton(text="⬇️", callback_data=f"move_q_down:{question_id}"))

    keyboard = [
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"edit_q_text:{question_id}")],
        [InlineKeyboardButton(text="🔄 Изменить ответ", callback_data=f"edit_q_answer:{question_id}")],
        [InlineKeyboardButton(text="🔢 Изменить баллы", callback_data=f"edit_q_points:{question_id}")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"q_stats:{question_id}")],
        nav_buttons,
        [InlineKeyboardButton(text="🗑️ Удалить вопрос", callback_data=f"delete_q:{question_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к вопросам", callback_data="back_to_q_list")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_settings_keyboard(test_id: int, shuffle: bool, attempts: int, session_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура настроек теста
    
    Args:
        test_id: ID теста
        shuffle: Перемешивание вопросов
        attempts: Количество попыток
        session_id: ID сессии, если тест открыт из редактора траекторий
    """
    shuffle_text = "✅ Перемешивать вопросы" if shuffle else "☑️ Не перемешивать вопросы"
    
    if attempts == 0:
        attempts_text = "♾️ Попытки: бесконечно"
    else:
        attempts_text = f"🔢 Попытки: {attempts}"

    # Определяем callback для кнопки "Назад"
    if session_id:
        back_callback = f"edit_test:{test_id}:{session_id}"
    else:
        back_callback = f"edit_test:{test_id}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=shuffle_text, callback_data=f"toggle_shuffle:{test_id}")],
            [InlineKeyboardButton(text=attempts_text, callback_data=f"edit_attempts:{test_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
        ]
    )
    return keyboard


def get_finish_options_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для завершения добавления вариантов ответа"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Завершить добавление вариантов", callback_data="finish_options")],
            [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
        ]
    )
    return keyboard


def format_help_message(role_name: str) -> str:
    """Форматирует справочное сообщение для роли"""
    base_text = "🤖 <b>Справочная система HRD-бота</b>\n\n"
    
    role_specific_help = {
        "Стажер": """🎓 <b>Ты — стажер.</b>
Твоя основная задача — проходить тесты и траектории обучения, назначенные наставником.

<b>Основные функции:</b>
• <b>Мой профиль 🦸🏻‍♂️</b> — посмотреть информацию о себе
• <b>Траектория обучения 📖</b> — перейти к твоей траектории обучения
• <b>База знаний 📁️</b> — изучить корпоративные материалы
• <b>Мой наставник 🎓</b> — получить информацию о твоем наставнике
• <b>Тесты траектории 🗺️</b> — тесты от наставника по траектории
• <b>Мои тесты 📋</b> — тесты от рекрутера через рассылку
• <b>Посмотреть баллы 📊</b> — увидеть твои баллы за пройденные тесты

<b>Команды:</b>
• <code>/start</code> — запуск/перезапуск бота
• <code>/logout</code> — выйти из системы
""",
        "Сотрудник": """👨‍💼 <b>Ты — сотрудник.</b>
Ты прошел стажировку и теперь можешь проходить тесты, назначаемые рекрутером.

<b>Основные функции:</b>
• <b>Мой профиль 🦸🏻‍♂️</b> — просмотреть свой профиль
• <b>Мои тесты 📋</b> — посмотреть назначенные тебе тесты
• <b>База знаний 📁️</b> — получить доступ к корпоративным материалам

<b>Команды:</b>
• <code>/start</code> — запуск/перезапуск бота
• <code>/logout</code> — выйти из системы
""",
        "Наставник": """👨‍🏫 <b>Ты — наставник.</b>
Твоя задача — курировать назначенных тебе стажеров и управлять их прогрессом.

<b>Основные функции:</b>
• <b>Панель наставника 🎓</b> — список стажеров, управление траекториями и этапами
• <b>Мои тесты 🗒</b> — пройти тесты, назначенные рекрутером через рассылку
• <b>База знаний 📒</b> — корпоративные материалы

<b>Возможности:</b>
• Назначение траекторий обучения своим стажерам
• Открытие этапов траекторий по мере прогресса стажеров
• Назначение дополнительных тестов стажерам
• Мониторинг прогресса стажеров
• Назначение аттестаций стажерам через руководителей

<b>Команды:</b>
• <code>/start</code> — запуск/перезапуск бота
• <code>/logout</code> — выйти из системы
""",
        "Рекрутер": """👔 <b>Ты — рекрутер.</b>
Твоя задача — создавать контент для обучения и управлять процессом наставничества.

<b>Основные функции:</b>
• <b>Мой профиль 🦸🏻‍♂️</b> — посмотреть информацию о себе
• <b>Компания 🏢</b> — просмотреть и редактировать информацию о компании, код приглашения и ссылку на бот
• <b>Рассылка ✈️</b> — массовая рассылка тестов сотрудникам по группам
• <b>Тесты 📄</b> — управление тестами (создание и просмотр)
• <b>Мои тесты 📋</b> — прохождение тестов из рассылок
• <b>Назначить наставника</b> — назначить наставника новому стажеру
• <b>Наставники 🦉</b> — просмотреть список наставников
• <b>Стажеры 🐣</b> — просмотреть список стажеров
• <b>Группы 🗂️</b> — управлять группами сотрудников
• <b>Объекты 📍</b> — управлять объектами работы
• <b>Траектория 📖</b> — создавать и управлять траекториями обучения
• <b>База знаний 📁️</b> — управлять корпоративными материалами
• <b>Все пользователи 🚸</b> — редактировать данные пользователей
• <b>Новые пользователи ➕</b> — активировать новых пользователей

<b>Возможности:</b>
• Управление информацией о компании (название, описание, код приглашения)
• Создание и управление траекториями обучения
• Создание аттестаций для руководителей
• Активация новых пользователей и назначение им наставников
• Редактирование данных пользователей
• Управление группами и объектами
• Массовая рассылка тестов по группам
• Полный доступ к базе знаний

<b>Команды:</b>
• <code>/start</code> — запуск/перезапуск бота
• <code>/logout</code> — выйти из системы
""",
        "Руководитель": """🔧 <b>Ты — руководитель.</b>
Твоя задача — проводить аттестации стажеров и управлять их переходом в сотрудники.

<b>Основные функции:</b>
• <b>Аттестация</b> — проводить аттестации стажеров
• <b>Мои тесты 📋</b> — прохождение тестов из рассылок
• <b>База знаний 📂</b> — получить доступ к корпоративным материалам

<b>Возможности:</b>
• Проведение аттестаций стажеров
• Управление расписанием аттестаций
• Просмотр результатов аттестаций
• Переход стажеров в статус сотрудника

<b>Команды:</b>
• <code>/start</code> — запуск/перезапуск бота
• <code>/logout</code> — выйти из системы
""",
        "Неавторизованный": """👋 <b>Добро пожаловать!</b>
Ты еще не вошел в систему.

<b>Доступные команды:</b>
• <code>/start</code> — запуск/перезапуск бота
• <code>/register</code> — пройти регистрацию, чтобы получить доступ к функциям бота
• <code>/login</code> — войти в систему, если ты уже зарегистрирован
"""
    }

    base_text += role_specific_help.get(role_name, "Для твоей роли нет специальной справки.")

    # Добавляем общую команду /help для всех ролей
    base_text += "\n\n• <code>/help</code> — вызвать эту справку"
    
    return base_text 

def get_tests_for_access_keyboard(tests: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора тестов для предоставления доступа из уведомлений"""
    keyboard = []
    
    for test in tests:
        button = InlineKeyboardButton(
            text=f"📋 {test.name}",
            callback_data=f"grant_access_to_test:{test.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ УПРАВЛЕНИЯ ГРУППАМИ
# =================================

def get_group_management_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура управления группами"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать группу", callback_data="create_group")],
        [InlineKeyboardButton(text="📝 Изменить группу", callback_data="manage_edit_group")],
        [InlineKeyboardButton(text="🗑️ Удалить группу", callback_data="manage_delete_group")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_group_selection_keyboard(groups: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура для выбора группы для изменения с пагинацией"""
    keyboard = []
    
    # Пагинация
    start_index = page * per_page
    end_index = start_index + per_page
    page_groups = groups[start_index:end_index]
    
    # Кнопки групп
    for group in page_groups:
        button = InlineKeyboardButton(
            text=f"🗂️ {group.name}",
            callback_data=f"select_group:{group.id}"
        )
        keyboard.append([button])
    
    # Навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"groups_page:{page-1}"))
    
    total_pages = (len(groups) + per_page - 1) // per_page
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"groups_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Информация о страницах
    if total_pages > 1:
        page_info = InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="page_info"
        )
        keyboard.append([page_info])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_edit")])
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_group_rename_confirmation_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения переименования группы"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_rename:{group_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_rename")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_group_delete_selection_keyboard(groups: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура для выбора группы для удаления с пагинацией"""
    keyboard = []
    
    # Пагинация
    start_index = page * per_page
    end_index = start_index + per_page
    page_groups = groups[start_index:end_index]
    
    # Кнопки групп
    for group in page_groups:
        button = InlineKeyboardButton(
            text=f"🗂️ {group.name}",
            callback_data=f"delete_group:{group.id}"
        )
        keyboard.append([button])
    
    # Навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"delete_group_page:{page-1}"))
    if end_index < len(groups):
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"delete_group_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Информация о страницах
    total_pages = (len(groups) + per_page - 1) // per_page
    if total_pages > 1:
        page_info = InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="page_info"
        )
        keyboard.append([page_info])
    
    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_delete_group"),
        InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_group_delete_confirmation_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления группы"""
    keyboard = [
        [InlineKeyboardButton(text="🗑️ Да, удалить", callback_data=f"confirm_delete_group:{group_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_delete_group")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Простая клавиатура с кнопкой 'Главное меню'"""
    keyboard = [
        [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ УПРАВЛЕНИЯ ОБЪЕКТАМИ
# =================================

def get_object_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления объектами"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать объект", callback_data="create_object")],
        [InlineKeyboardButton(text="✏️ Изменить объект", callback_data="edit_object")],
        [InlineKeyboardButton(text="🗑️ Удалить объект", callback_data="manage_delete_object")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_object_selection_keyboard(objects: list, page: int = 0, per_page: int = 5, object_type: str = "") -> InlineKeyboardMarkup:
    """Клавиатура для выбора объекта для изменения с пагинацией"""
    keyboard = []
    
    # Пагинация
    start_index = page * per_page
    end_index = start_index + per_page
    page_objects = objects[start_index:end_index]
    
    # Кнопки объектов
    for obj in page_objects:
        # Определяем callback_data в зависимости от типа объекта
        if object_type == "internship":
            callback_data = f"select_internship_object:{obj.id}"
        elif object_type == "work":
            callback_data = f"select_work_object:{obj.id}"
        else:
            callback_data = f"select_object:{obj.id}"
            
        keyboard.append([
            InlineKeyboardButton(
                text=obj.name,
                callback_data=callback_data
            )
        ])
    
    # Навигация по страницам
    navigation_row = []
    total_pages = (len(objects) + per_page - 1) // per_page
    
    # Определяем префикс для callback_data пагинации
    if object_type == "internship":
        page_callback = "internship_object_page"
    elif object_type == "work":
        page_callback = "work_object_page"
    else:
        page_callback = "objects_page"
    
    if page > 0:
        navigation_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{page_callback}:{page-1}"))
    
    if total_pages > 1:
        navigation_row.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="page_info"))
    
    if page < total_pages - 1:
        navigation_row.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"{page_callback}:{page+1}"))
    
    if navigation_row:
        keyboard.append(navigation_row)
    
    # Кнопка возврата к редактору и главное меню
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_edit")])
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_object_rename_confirmation_keyboard(object_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения переименования объекта"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_object_rename:{object_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_object_rename")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_object_delete_selection_keyboard(objects: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура для выбора объекта для удаления с пагинацией"""
    keyboard = []
    
    # Добавляем объекты для текущей страницы
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_objects = objects[start_idx:end_idx]
    
    for obj in page_objects:
        keyboard.append([InlineKeyboardButton(
            text=f"🗑️ {obj.name}",
            callback_data=f"delete_object:{obj.id}"
        )])
    
    # Добавляем кнопки навигации если нужно
    total_pages = (len(objects) + per_page - 1) // per_page
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"object_delete_page:{page-1}"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"object_delete_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопки управления
    keyboard.extend([
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_object_delete")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_object_delete_confirmation_keyboard(object_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения удаления объекта"""
    keyboard = [
        [InlineKeyboardButton(text="🗑️ Да, удалить", callback_data=f"confirm_object_delete:{object_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_object_delete")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_editor_keyboard(is_trainee: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для редактора пользователя"""
    keyboard = [
        [InlineKeyboardButton(text="Имя", callback_data="edit_full_name")],
        [InlineKeyboardButton(text="Телефон", callback_data="edit_phone")],
        [InlineKeyboardButton(text="Роль", callback_data="edit_role")],
        [InlineKeyboardButton(text="Группу", callback_data="edit_group")]
    ]
    
    # Добавляем объект стажировки только для стажеров
    if is_trainee:
        keyboard.append([InlineKeyboardButton(text="Объект стажировки", callback_data="edit_internship_object")])
    
    keyboard.append([InlineKeyboardButton(text="Объект работы", callback_data="edit_work_object")])
    keyboard.append([InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data="delete_user")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_view_user")])
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_deletion_confirmation_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления пользователя"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_user:{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cancel_delete_user:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_edit_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения изменений"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Изменить", callback_data="confirm_change")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_change")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================== ТРАЕКТОРИИ ОБУЧЕНИЯ ==================

def get_learning_paths_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню редактора траекторий"""
    keyboard = [
        [InlineKeyboardButton(text="➕Создать", callback_data="create_trajectory")],
        [InlineKeyboardButton(text="👁️Просмотреть", callback_data="edit_trajectory")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete_trajectory")],
        [InlineKeyboardButton(text="🔍Аттестации", callback_data="manage_attestations")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_creation_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для начала создания траектории"""
    keyboard = [
        [InlineKeyboardButton(text="Начать", callback_data="start_trajectory_creation")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_selection_keyboard(tests: list, existing_tests_in_session: list = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора тестов для сессии"""
    keyboard = []
    
    # Кнопка создания нового теста
    keyboard.append([InlineKeyboardButton(text="➕Создать новый тест", callback_data="create_new_test")])
    
    # Если есть существующие тесты в сессии, добавляем кнопку сохранения
    if existing_tests_in_session:
        keyboard.append([InlineKeyboardButton(text="✅Сохранить Сессию", callback_data="save_session")])
    
    # Добавляем доступные тесты
    for test in tests:
        # Исключаем уже добавленные тесты
        if not existing_tests_in_session or test.id not in [t['id'] for t in existing_tests_in_session]:
            keyboard.append([InlineKeyboardButton(
                text=test.name, 
                callback_data=f"select_test:{test.id}"
            )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_creation_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отмены создания теста"""
    keyboard = [
        [InlineKeyboardButton(text="🚫Отменить создание теста", callback_data="cancel_test_creation")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_materials_choice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора материалов для теста"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да", callback_data="add_materials")],
        [InlineKeyboardButton(text="❌Нет", callback_data="skip_materials")],
        [InlineKeyboardButton(text="🚫Отменить создание теста", callback_data="cancel_test_creation")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_materials_skip_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пропуска материалов"""
    keyboard = [
        [InlineKeyboardButton(text="⏩Пропустить", callback_data="skip_materials")],
        [InlineKeyboardButton(text="🚫Отменить создание теста", callback_data="cancel_test_creation")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_description_skip_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пропуска описания теста"""
    keyboard = [
        [InlineKeyboardButton(text="⏩Пропустить", callback_data="skip_description")],
        [InlineKeyboardButton(text="🚫Отменить создание теста", callback_data="cancel_test_creation")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)




def get_more_questions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для добавления дополнительных вопросов"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да", callback_data="add_more_questions")],
        [InlineKeyboardButton(text="❌Нет", callback_data="finish_questions")],
        [InlineKeyboardButton(text="🚫Отменить создание теста", callback_data="cancel_test_creation")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_session_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления сессиями после создания"""
    keyboard = [
        [InlineKeyboardButton(text="Добавить сессию", callback_data="add_session")],
        [InlineKeyboardButton(text="Новый Этап", callback_data="add_stage")],
        [InlineKeyboardButton(text="Сохранить траекторию", callback_data="save_trajectory")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_attestation_selection_keyboard(attestations: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора аттестации для траектории"""
    keyboard = []
    
    # Добавляем доступные аттестации
    for attestation in attestations:
        keyboard.append([InlineKeyboardButton(
            text=attestation.name,
            callback_data=f"select_attestation:{attestation.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🚫Отменить", callback_data="cancel_attestation_selection")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_save_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения сохранения траектории"""
    keyboard = [
        [InlineKeyboardButton(text="✅Да", callback_data="confirm_trajectory_save")],
        [InlineKeyboardButton(text="🚫Отменить", callback_data="cancel_trajectory_save")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_attestation_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения траектории с аттестацией (пункт 49 ТЗ)"""
    keyboard = [
        [InlineKeyboardButton(text="✅Да", callback_data="confirm_attestation_and_proceed")],
        [InlineKeyboardButton(text="🚫Отменить", callback_data="cancel_attestation_confirmation")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_final_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура финального подтверждения траектории с группой (пункт 54 ТЗ)"""
    keyboard = [
        [InlineKeyboardButton(text="✅Сохранить", callback_data="final_confirm_save")],
        [InlineKeyboardButton(text="🚫Отменить", callback_data="cancel_final_confirmation")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================== АТТЕСТАЦИИ ==================

def get_attestations_main_keyboard(attestations: list) -> InlineKeyboardMarkup:
    """Главное меню редактора аттестаций"""
    keyboard = []
    
    # Кнопка создания новой аттестации
    keyboard.append([InlineKeyboardButton(text="➕Создать", callback_data="create_attestation")])
    
    # Добавляем существующие аттестации
    for attestation in attestations:
        keyboard.append([InlineKeyboardButton(
            text=attestation.name,
            callback_data=f"view_attestation:{attestation.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trajectories_main")])
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_attestation_creation_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для начала создания аттестации"""
    keyboard = [
        [InlineKeyboardButton(text="Далее⏩", callback_data="start_attestation_creation")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_attestation_questions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления вопросами аттестации"""
    keyboard = [
        [InlineKeyboardButton(text="Сохранить вопросы", callback_data="save_attestation_questions")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================== ФИЛЬТРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ ==================

def get_users_filter_keyboard(groups: list, objects: list) -> InlineKeyboardMarkup:
    """Клавиатура фильтрации пользователей по группам и объектам"""
    keyboard = []
    
    # Показать всех пользователей
    keyboard.append([InlineKeyboardButton(text="👥 Все пользователи", callback_data="filter_all_users")])
    
    # Фильтр по группам
    if groups:
        keyboard.append([InlineKeyboardButton(text="🗂️ Фильтр по группам", callback_data="filter_by_groups")])
    
    # Фильтр по объектам  
    if objects:
        keyboard.append([InlineKeyboardButton(text="📍 Фильтр по объектам", callback_data="filter_by_objects")])
    
    # Поиск по ФИО
    keyboard.append([InlineKeyboardButton(text="🔍 Поиск по ФИО", callback_data="search_all_users")])
    
    # Кнопка главного меню
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_group_filter_keyboard(groups: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура выбора группы для фильтрации с пагинацией"""
    keyboard = []
    total_groups = len(groups)
    start_idx = page * per_page
    end_idx = start_idx + per_page
    
    # Добавляем кнопки групп для текущей страницы
    for group in groups[start_idx:end_idx]:
        keyboard.append([InlineKeyboardButton(
            text=f"🗂️ {group.name}",
            callback_data=f"filter_group:{group.id}"
        )])
    
    # Навигационные кнопки
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"group_filter_page:{page - 1}"))
    
    if end_idx < total_groups:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"group_filter_page:{page + 1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton(text="↩️ Назад к фильтрам", callback_data="back_to_filters")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_object_filter_keyboard(objects: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура выбора объекта для фильтрации с пагинацией"""
    keyboard = []
    total_objects = len(objects)
    start_idx = page * per_page
    end_idx = start_idx + per_page
    
    # Добавляем кнопки объектов для текущей страницы
    for obj in objects[start_idx:end_idx]:
        keyboard.append([InlineKeyboardButton(
            text=f"📍 {obj.name}",
            callback_data=f"filter_object:{obj.id}"
        )])
    
    # Навигационные кнопки
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"object_filter_page:{page - 1}"))
    
    if end_idx < total_objects:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"object_filter_page:{page + 1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton(text="↩️ Назад к фильтрам", callback_data="back_to_filters")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_users_list_keyboard(users: list, page: int = 0, per_page: int = 5, filter_type: str = "all") -> InlineKeyboardMarkup:
    """Клавиатура списка пользователей с пагинацией"""
    keyboard = []
    total_users = len(users)
    start_idx = page * per_page
    end_idx = start_idx + per_page
    
    # Добавляем кнопки пользователей для текущей страницы
    for user in users[start_idx:end_idx]:
        # Роль для отображения
        role_name = user.roles[0].name if user.roles else "Без роли"
        
        keyboard.append([InlineKeyboardButton(
            text=f"👤 {user.full_name} ({role_name})",
            callback_data=f"view_user:{user.id}"
        )])
    
    # Навигационные кнопки
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"users_page:{filter_type}:{page - 1}"))
    
    if end_idx < total_users:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"users_page:{filter_type}:{page + 1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton(text="↩️ Назад к фильтрам", callback_data="back_to_filters")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_new_users_list_keyboard(users: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура списка новых (неактивированных) пользователей с пагинацией"""
    keyboard = []
    total_users = len(users)
    start_idx = page * per_page
    end_idx = start_idx + per_page
    
    # Добавляем кнопки пользователей для текущей страницы
    for user in users[start_idx:end_idx]:
        registration_date = user.registration_date.strftime('%d.%m.%Y') if user.registration_date else "Неизвестно"
        button_text = f"{user.full_name} ({registration_date})"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"activate_user:{user.id}"
            )
        ])
    
    # Навигационные кнопки
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"new_users_page:{page - 1}"))
    
    if end_idx < total_users:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"new_users_page:{page + 1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Показываем номер страницы
    if total_users > per_page:
        total_pages = (total_users + per_page - 1) // per_page
        keyboard.append([InlineKeyboardButton(
            text=f"📄 Страница {page + 1}/{total_pages}",
            callback_data="noop"
        )])
    
    # Кнопка поиска
    keyboard.append([InlineKeyboardButton(text="🔍 Поиск по ФИО", callback_data="search_new_users")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_info_keyboard(user_id: int, filter_type: str = "all") -> InlineKeyboardMarkup:
    """Клавиатура для просмотра информации о пользователе"""
    keyboard = [
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_user:{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_users:{filter_type}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ===== КЛАВИАТУРЫ ДЛЯ РАБОТЫ С РУКОВОДИТЕЛЯМИ =====

def get_manager_selection_keyboard(managers: list) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора руководителя из списка доступных
    """
    keyboard = []

    for manager in managers:
        keyboard.append([InlineKeyboardButton(
            text=f"{manager.full_name}",
            callback_data=f"select_manager:{manager.id}"
        )])

    # Кнопка отмены
    keyboard.append([InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_manager_selection")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_manager_assignment_confirmation_keyboard(trainee_id: int, manager_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения назначения руководителя стажеру
    """
    keyboard = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_manager:{trainee_id}:{manager_id}")],
        [InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_manager_assignment")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_manager_actions_keyboard(trainee_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура действий для работы с руководителем стажера
    """
    keyboard = [
        [InlineKeyboardButton(text="👨‍🏫 Назначить руководителя", callback_data=f"assign_manager:{trainee_id}")],
        [InlineKeyboardButton(text="📋 Посмотреть руководителя", callback_data=f"view_manager:{trainee_id}")],
        [InlineKeyboardButton(text="🎯 Аттестация", callback_data=f"attestation:{trainee_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data=f"back_to_trainee:{trainee_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ БАЗЫ ЗНАНИЙ (Task 9)
# =================================

def get_knowledge_base_main_keyboard(has_folders: bool = False) -> InlineKeyboardMarkup:
    """Основная клавиатура базы знаний для рекрутера (ТЗ 9-1 шаг 2)"""
    keyboard = [
        [InlineKeyboardButton(text="Создать папку", callback_data="kb_create_folder")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    
    # Если папки есть, показываем их кнопки будут добавлены динамически
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_knowledge_folders_keyboard(folders: list, show_create: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура со списком всех папок базы знаний (ТЗ 9-2 шаг 2)"""
    keyboard = []
    
    # Кнопки управления
    if show_create:
        keyboard.append([InlineKeyboardButton(text="Создать папку", callback_data="kb_create_folder")])
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    # Папки (максимум 4-5 для читабельности)
    for folder in folders:
        folder_name = folder.name[:25] + "..." if len(folder.name) > 25 else folder.name
        keyboard.append([InlineKeyboardButton(
            text=f"{{ {folder_name} }}", 
            callback_data=f"kb_folder:{folder.id}"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_folder_created_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после создания папки (ТЗ 9-1 шаг 6)"""
    keyboard = [
        [InlineKeyboardButton(text="Добавить материал", callback_data="kb_add_material")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_material_description_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пропуска описания материала (ТЗ 9-1 шаг 12)"""
    keyboard = [
        [InlineKeyboardButton(text="⏩Пропустить", callback_data="kb_skip_description")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_material_save_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для сохранения материала (ТЗ 9-1 шаг 14)"""
    keyboard = [
        [InlineKeyboardButton(text="✅Сохранить", callback_data="kb_save_material")],
        [InlineKeyboardButton(text="🚫Отменить", callback_data="kb_cancel_material")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_material_saved_keyboard(folder_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура после сохранения материала (ТЗ 9-1 шаг 16)"""
    keyboard = [
        [InlineKeyboardButton(text="Добавить материал", callback_data="kb_add_material")]
    ]
    
    # Добавляем кнопку возврата к папке, если передан folder_id
    if folder_id:
        keyboard.append([InlineKeyboardButton(text="📁 К папке", callback_data=f"kb_folder:{folder_id}")])
    
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_folder_view_keyboard(folder_id: int, materials: list) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра содержимого папки (ТЗ 9-2 шаг 4)"""
    keyboard = []

    # Материалы в папке (фильтруем только активные)
    for material in materials:
        if material.is_active:  # Показываем только активные материалы
            material_name = material.name[:20] + "..." if len(material.name) > 20 else material.name
            keyboard.append([InlineKeyboardButton(
                text=material_name,
                callback_data=f"kb_material:{material.id}"
            )])
    
    # Кнопки управления папкой
    keyboard.extend([
        [InlineKeyboardButton(text="➕ Добавить материал", callback_data=f"kb_add_material_to_folder:{folder_id}")],
        [InlineKeyboardButton(text="Доступ", callback_data=f"kb_access:{folder_id}")],
        [InlineKeyboardButton(text="Удалить папку", callback_data=f"kb_delete_folder:{folder_id}")],
        [InlineKeyboardButton(text="Изменить название", callback_data=f"kb_rename_folder:{folder_id}")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_material_view_keyboard(material_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра материала (ТЗ 9-2 шаг 6)"""
    keyboard = [
        [InlineKeyboardButton(text="Удалить материал", callback_data=f"kb_delete_material:{material_id}")],
        [InlineKeyboardButton(text="Назад", callback_data="kb_back")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_material_delete_confirmation_keyboard(material_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления материала (ТЗ 9-2 шаг 7-2)"""
    keyboard = [
        [InlineKeyboardButton(text="✅Да, удалить", callback_data=f"kb_confirm_delete_material:{material_id}")],
        [InlineKeyboardButton(text="🚫Нет, отмена", callback_data="kb_cancel_delete")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_group_access_selection_keyboard(groups: list, selected_group_ids: list = None) -> InlineKeyboardMarkup:
    """Клавиатура для выбора групп доступа к папке (ТЗ 9-3 шаг 5)"""
    keyboard = []
    selected_group_ids = selected_group_ids or []
    
    # Группы с отметками о выборе
    for group in groups:
        # Отмечаем выбранные группы
        prefix = "✅ " if group.id in selected_group_ids else ""
        group_name = group.name[:15] + "..." if len(group.name) > 15 else group.name
        keyboard.append([InlineKeyboardButton(
            text=f"{prefix}{{ {group_name} }}",
            callback_data=f"kb_toggle_group:{group.id}"
        )])
    
    # Кнопки управления
    keyboard.append([InlineKeyboardButton(text="Назад", callback_data="kb_back")])
    
    # Показываем кнопку "Сохранить изменения" только если есть выбранные группы
    if selected_group_ids:
        keyboard.insert(-1, [InlineKeyboardButton(text="Сохранить изменения", callback_data="kb_save_access")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_folder_rename_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения переименования папки (ТЗ 9-4 шаг 7)"""
    keyboard = [
        [InlineKeyboardButton(text="✅Сохранить", callback_data="kb_confirm_rename")],
        [InlineKeyboardButton(text="🚫Отменить", callback_data="kb_cancel_rename")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_folder_delete_confirmation_keyboard(folder_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления папки (ТЗ 9-5 шаг 5)"""
    keyboard = [
        [InlineKeyboardButton(text="✅Да, удалить", callback_data=f"kb_confirm_delete_folder:{folder_id}")],
        [InlineKeyboardButton(text="🚫Нет, отмена", callback_data="kb_cancel_delete")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_folder_deleted_keyboard(folder_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура после удаления/переименования папки (ТЗ 9-5 шаг 7)"""
    keyboard = []
    
    # Если передан folder_id (переименование), показываем кнопку возврата к папке
    if folder_id:
        keyboard.append([InlineKeyboardButton(text="📁 К папке", callback_data=f"kb_folder:{folder_id}")])
    else:
        # Если folder_id нет (удаление), показываем возврат к списку
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="kb_back")])
    
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Клавиатуры для сотрудников (просмотр базы знаний)
def get_employee_knowledge_folders_keyboard(folders: list) -> InlineKeyboardMarkup:
    """Клавиатура папок базы знаний для сотрудников"""
    keyboard = []

    # Папки, доступные сотруднику (фильтруем только активные)
    for folder in folders:
        if folder.is_active:  # Показываем только активные папки
            folder_name = folder.name[:25] + "..." if len(folder.name) > 25 else folder.name
            keyboard.append([InlineKeyboardButton(
                text=f"📁 {folder_name}",
                callback_data=f"kb_emp_folder:{folder.id}"
            )])
    
    # Кнопка возврата
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад к профилю", callback_data="back_to_employee_profile")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_employee_folder_materials_keyboard(folder_id: int, materials: list) -> InlineKeyboardMarkup:
    """Клавиатура материалов папки для сотрудников"""
    keyboard = []

    # Материалы в папке (фильтруем только активные)
    for material in materials:
        if material.is_active:  # Показываем только активные материалы
            material_name = material.name[:25] + "..." if len(material.name) > 25 else material.name
            keyboard.append([InlineKeyboardButton(
                text=f"📄 {material_name}",
                callback_data=f"kb_emp_material:{material.id}"
            )])
    
    # Кнопка возврата
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад к папкам", callback_data="kb_emp_back_to_folders")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_employee_material_view_keyboard(folder_id: int) -> InlineKeyboardMarkup:
    """Клавиатура просмотра материала для сотрудников"""
    keyboard = [
        [InlineKeyboardButton(text="⬅️ Назад к материалам", callback_data=f"kb_emp_folder:{folder_id}")],
        [InlineKeyboardButton(text="📚 К папкам", callback_data="kb_emp_back_to_folders")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_mentor_contact_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для экрана 'траектория не назначена' (Figma 17.5)"""
    keyboard = [
        [
            InlineKeyboardButton(text="← назад", callback_data="main_menu"),
            InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_tests_main_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления тестами (ракировка из главного меню)"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать новый", callback_data="create_test")],
        [InlineKeyboardButton(text="📋 Список тестов", callback_data="list_tests")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_fallback_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для fallback сообщений с неожиданным вводом"""
    keyboard = [
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="fallback_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ РАБОТЫ СО СТАЖЕРАМИ (РЕКРУТЕР)
# =================================

def get_trainees_list_keyboard(trainees: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура со списком стажеров с пагинацией для рекрутера"""
    keyboard = []
    
    # Пагинация
    start_index = page * per_page
    end_index = start_index + per_page
    page_trainees = trainees[start_index:end_index]
    
    # Кнопки стажеров
    for trainee in page_trainees:
        button = InlineKeyboardButton(
            text=f"{trainee.full_name}",
            callback_data=f"view_trainee:{trainee.id}"
        )
        keyboard.append([button])
    
    # Навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"trainees_page:{page-1}"))
    
    total_pages = (len(trainees) + per_page - 1) // per_page
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"trainees_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Информация о страницах
    if total_pages > 1:
        page_info = InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="page_info"
        )
        keyboard.append([page_info])
    
    # Кнопка главного меню
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trainee_detail_keyboard(trainee_id: int, has_attestation: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для детального просмотра стажера

    Args:
        trainee_id: ID стажера
        has_attestation: True если у стажера есть траектория с аттестацией
    """
    keyboard = [
        [InlineKeyboardButton(text="📊 Просмотреть прогресс", callback_data=f"view_trainee_progress:{trainee_id}")]
    ]

    # Добавляем кнопку открытия аттестации если есть траектория с аттестацией
    if has_attestation:
        keyboard.append([InlineKeyboardButton(text="🏁 Открыть аттестацию", callback_data=f"recruiter_open_attestation:{trainee_id}")])

    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_recruiter_trainees")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trainee_progress_keyboard(trainee_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра прогресса стажера"""
    keyboard = [
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_trainee_detail:{trainee_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_selection_keyboard(trajectories: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора траектории для удаления"""
    keyboard = []
    
    for trajectory in trajectories:
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗑️ {trajectory.name}",
                callback_data=f"select_trajectory_to_delete:{trajectory.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trajectories_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_deletion_confirmation_keyboard(trajectory_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления траектории"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_trajectory_deletion:{trajectory_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_trajectory_selection")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_mentors_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню наставников для рекрутера"""
    keyboard = [
        [InlineKeyboardButton(text="👥 Список наставников", callback_data="view_all_mentors")],
        [InlineKeyboardButton(text="👨‍🏫 Назначить наставника", callback_data="mentor_assignment_management")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_mentor_assignment_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления назначениями наставников"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Назначить наставника", callback_data="assign_mentor")],
        [InlineKeyboardButton(text="👥 Просмотреть назначения", callback_data="view_mentor_assignments")],
        [InlineKeyboardButton(text="🔄 Переназначить наставника", callback_data="reassign_mentor")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_mentors_menu")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trainees_with_mentors_keyboard(trainees: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора стажера с наставником для переназначения"""
    keyboard = []
    
    for trainee in trainees:
        keyboard.append([
            InlineKeyboardButton(
                text=f"👤 {trainee.full_name}",
                callback_data=f"select_trainee_for_reassign:{trainee.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="mentor_assignment_management")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_mentors_pagination_keyboard(mentors: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура для пагинации списка наставников"""
    keyboard = []
    
    # Добавляем кнопки наставников для текущей страницы
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_mentors = mentors[start_idx:end_idx]
    
    for mentor in page_mentors:
        keyboard.append([
            InlineKeyboardButton(
                text=f"👤 {mentor.full_name}",
                callback_data=f"view_mentor_detail:{mentor.id}"
            )
        ])
    
    # Добавляем кнопки пагинации
    total_pages = (len(mentors) + per_page - 1) // per_page
    pagination_buttons = []
    
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"mentors_page:{page-1}"))
    
    if page < total_pages - 1:
        pagination_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"mentors_page:{page+1}"))
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    
    # Кнопка "Назад" к подменю наставников
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_mentors_menu")])
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================== РЕДАКТОР ТРАЕКТОРИЙ ==================

def get_trajectory_editor_main_keyboard(stages: list, path_id: int) -> InlineKeyboardMarkup:
    """Главное меню редактора конкретной траектории с кнопками этапов"""
    keyboard = []
    
    # Кнопки для каждого этапа
    for stage in sorted(stages, key=lambda s: s.order_number):
        keyboard.append([InlineKeyboardButton(
            text=f"Этап {stage.order_number}",
            callback_data=f"edit_stage_view:{stage.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="➕ Добавить этап", callback_data=f"add_stage_to_trajectory:{path_id}")])
    keyboard.append([InlineKeyboardButton(text="Аттестация", callback_data=f"edit_trajectory_attestation:{path_id}")])
    keyboard.append([InlineKeyboardButton(text="✏️ Группы траектории", callback_data=f"edit_trajectory_group:{path_id}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_trajectory")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_edit_info_keyboard(path_id: int) -> InlineKeyboardMarkup:
    """Меню редактирования информации о траектории"""
    keyboard = [
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"change_trajectory_name:{path_id}")],
        [InlineKeyboardButton(text="🗂️ Изменить группу", callback_data=f"change_trajectory_group:{path_id}")],
        [InlineKeyboardButton(text="🔍 Изменить аттестацию", callback_data=f"change_trajectory_attestation:{path_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить аттестацию", callback_data=f"remove_trajectory_attestation:{path_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editor_main_menu:{path_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_stage_editor_keyboard(stage, sessions: list, path_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для экрана редактирования этапа (показывает сессии этапа)
    
    Args:
        stage: Объект LearningStage
        sessions: Список сессий этапа
        path_id: ID траектории
    """
    keyboard = []
    
    # Кнопки сессий этого этапа
    for session in sorted(sessions, key=lambda s: s.order_number):
        keyboard.append([InlineKeyboardButton(
            text=f"Сессия {session.order_number}",
            callback_data=f"edit_session_view:{session.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="➕ Добавить сессию", callback_data=f"add_session_to_stage:{stage.id}")])
    keyboard.append([InlineKeyboardButton(text="✏️ Название этапа", callback_data=f"edit_stage_name:{stage.id}")])
    keyboard.append([InlineKeyboardButton(text="🚫 Удалить этап", callback_data=f"delete_stage:{stage.id}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editor_main_menu:{path_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)




def get_session_tests_keyboard(tests: list, session_id: int, stage_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления тестами в сессии для экрана редактирования"""
    keyboard = []
    
    # Список тестов в сессии (кнопки для редактирования)
    for i, test in enumerate(tests, 1):
        keyboard.append([InlineKeyboardButton(
            text=test.name,
            callback_data=f"edit_test:{test.id}:{session_id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="➕ Добавить тест", callback_data=f"add_test_to_session:{session_id}")])
    keyboard.append([InlineKeyboardButton(text="✏️ Название сессии", callback_data=f"edit_session_name:{session_id}")])
    keyboard.append([InlineKeyboardButton(text="🚫 Удалить сессию", callback_data=f"delete_session:{session_id}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_stage_view:{stage_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_selection_for_session_keyboard(tests: list, session_id: int, existing_test_ids: list = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора тестов для добавления в сессию"""
    keyboard = []
    
    if existing_test_ids is None:
        existing_test_ids = []
    
    for test in tests:
        # Показываем только тесты, которых еще нет в сессии
        if test.id not in existing_test_ids:
            keyboard.append([InlineKeyboardButton(
                text=test.name,
                callback_data=f"select_test_for_session:{session_id}:{test.id}"
            )])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_session_view:{session_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_group_selection_for_trajectory_keyboard(groups: list, path_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора группы для траектории"""
    keyboard = []
    
    for group in groups:
        keyboard.append([InlineKeyboardButton(
            text=group.name,
            callback_data=f"select_group_for_trajectory:{path_id}:{group.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editor_main_menu:{path_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_attestation_selection_for_trajectory_keyboard(attestations: list, path_id: int, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура выбора аттестации для траектории с пагинацией"""
    keyboard = []
    
    # Пагинация
    total_attestations = len(attestations)
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_attestations = attestations[start_idx:end_idx]
    
    # Кнопки аттестаций для текущей страницы
    for attestation in page_attestations:
        keyboard.append([InlineKeyboardButton(
            text=attestation.name,
            callback_data=f"select_attestation_for_trajectory:{path_id}:{attestation.id}"
        )])
    
    # Навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"attestations_page_prev:{path_id}:{page-1}"))
    
    total_pages = (total_attestations + per_page - 1) // per_page
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"attestations_page_next:{path_id}:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="🚫 Не назначать", callback_data=f"remove_trajectory_attestation:{path_id}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editor_main_menu:{path_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_attestation_management_keyboard(path_id: int, has_attestation: bool = False, attestation_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура управления аттестацией траектории"""
    keyboard = []
    
    if has_attestation:
        keyboard.append([InlineKeyboardButton(text="👁️ Просмотреть", callback_data=f"view_trajectory_attestation:{path_id}:{attestation_id}")])
        keyboard.append([InlineKeyboardButton(text="✏️ Заменить", callback_data=f"replace_trajectory_attestation:{path_id}")])
    else:
        keyboard.append([InlineKeyboardButton(text="Добавить", callback_data=f"add_trajectory_attestation:{path_id}")])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editor_main_menu:{path_id}")])
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_stage_deletion_confirmation_keyboard(stage_id: int, path_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления этапа"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_stage:{stage_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_stage_view:{stage_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_session_deletion_confirmation_keyboard(session_id: int, stage_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления сессии"""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_session:{session_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_session_view:{session_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_to_editor_keyboard(path_id: int) -> InlineKeyboardMarkup:
    """Универсальная клавиатура возврата в редактор"""
    keyboard = [
        [InlineKeyboardButton(text="⬅️ Назад в редактор", callback_data=f"editor_main_menu:{path_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_trajectory_selection_for_editor_keyboard(learning_paths: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура выбора траектории для редактирования с пагинацией"""
    keyboard = []
    
    # Пагинация
    total_trajectories = len(learning_paths)
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_trajectories = learning_paths[start_idx:end_idx]
    
    # Кнопки траекторий для текущей страницы
    for path in page_trajectories:
        keyboard.append([InlineKeyboardButton(
            text=f"{path.name}",
            callback_data=f"edit_path:{path.id}"
        )])
    
    # Навигационные кнопки
    nav_buttons = []
    total_pages = (total_trajectories + per_page - 1) // per_page if total_trajectories > 0 else 1
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"trajectories_page_prev:{page-1}"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"trajectories_page_next:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_company_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора: создать или присоединиться к компании"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 Создать компанию", callback_data="company:create")],
        [InlineKeyboardButton(text="🔗 Присоединиться к компании", callback_data="company:join")]
    ])
    return keyboard


# =================================
# КЛАВИАТУРЫ ДЛЯ УПРАВЛЕНИЯ КОМПАНИЕЙ (РЕКРУТЕР)
# =================================

def get_company_info_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура с информацией о компании и кнопками редактирования"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Название", callback_data="company:edit_name")],
        [InlineKeyboardButton(text="✏️ Описание", callback_data="company:edit_description")],
        [InlineKeyboardButton(text="🔑 Код компании", callback_data="company:view_code")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ])
    return keyboard


def get_company_edit_name_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для редактирования названия компании"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="company:info")]
    ])
    return keyboard


def get_company_edit_description_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для редактирования описания компании"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="company:info")]
    ])
    return keyboard


def get_company_code_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для просмотра кода компании"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Код отдельно", callback_data="company:code_only")],
        [InlineKeyboardButton(text="📎 Ссылка на бот", callback_data="company:bot_link")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="company:info")]
    ])
    return keyboard


def get_company_code_only_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для показа кода отдельно"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="company:view_code")]
    ])
    return keyboard


def get_company_bot_link_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для показа ссылки на бот"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="company:view_code")]
    ])
    return keyboard


def get_user_groups_multiselect_keyboard(
    groups: list,
    selected_group_ids: list,
    page: int = 0,
    per_page: int = 5
) -> InlineKeyboardMarkup:
    """Клавиатура мультивыбора групп для редактирования пользователя (наставника)

    Args:
        groups: Список объектов Group
        selected_group_ids: Список ID выбранных групп
        page: Номер текущей страницы (0-indexed)
        per_page: Количество групп на странице

    Returns:
        InlineKeyboardMarkup с кнопками групп, пагинацией и управлением
    """
    keyboard = []
    selected_group_ids = selected_group_ids or []

    # Пагинация: вычисляем срез групп для текущей страницы
    total_groups = len(groups)
    total_pages = (total_groups + per_page - 1) // per_page if total_groups > 0 else 1
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, total_groups)
    page_groups = groups[start_idx:end_idx]

    # Кнопки групп с отметками о выборе
    for group in page_groups:
        prefix = "✅ " if group.id in selected_group_ids else ""
        group_name = group.name[:20] + "..." if len(group.name) > 20 else group.name
        keyboard.append([InlineKeyboardButton(
            text=f"{prefix}{group_name}",
            callback_data=f"user_edit_toggle_group:{group.id}"
        )])

    # Кнопки пагинации
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton(
            text="⬅️",
            callback_data=f"user_edit_groups_page:{page - 1}"
        ))
    if page < total_pages - 1:
        pagination_row.append(InlineKeyboardButton(
            text="➡️",
            callback_data=f"user_edit_groups_page:{page + 1}"
        ))
    if pagination_row:
        keyboard.append(pagination_row)

    # Кнопка сохранения (только если есть выбранные группы)
    if selected_group_ids:
        keyboard.append([InlineKeyboardButton(
            text="💾 Сохранить",
            callback_data="user_edit_save_groups"
        )])

    # Кнопки навигации
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_edit")])
    keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)