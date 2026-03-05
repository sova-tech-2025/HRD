from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id
from keyboards.keyboards import (
    get_fallback_keyboard,
    get_role_selection_keyboard,
)
from states.states import (
    AdminStates,
    AttestationAssignmentStates,
    AttestationStates,
    AuthStates,
    BroadcastStates,
    CompanyManagementStates,
    GroupManagementStates,
    KnowledgeBaseStates,
    LearningPathStates,
    ManagerAttestationStates,
    MentorshipStates,
    ObjectManagementStates,
    RecruiterAttestationStates,
    RegistrationStates,
    TestCreationStates,
    TestTakingStates,
    TraineeManagementStates,
    TraineeTrajectoryStates,
    UserActivationStates,
    UserEditStates,
)
from utils.logger import log_user_action

router = Router()


# =================================
# ФИЛЬТРЫ
# =================================

# Состояния, где достаточно "используй кнопки"
USE_BUTTONS_FILTER = StateFilter(
    # Admin states
    AdminStates.waiting_for_user_selection,
    AdminStates.waiting_for_user_action,
    AdminStates.waiting_for_role_change,
    AdminStates.waiting_for_confirmation,
    AdminStates.waiting_for_role_selection,
    AdminStates.waiting_for_permission_action,
    AdminStates.waiting_for_permission_selection,
    AdminStates.waiting_for_permission_confirmation,
    # Registration
    RegistrationStates.waiting_for_admin_token,
    # TestCreation - button-based states
    TestCreationStates.waiting_for_more_questions,
    TestCreationStates.waiting_for_stage_selection,
    TestCreationStates.waiting_for_final_confirmation,
    TestCreationStates.waiting_for_edit_action,
    TestCreationStates.waiting_for_new_stage,
    TestCreationStates.waiting_for_new_attempts,
    TestCreationStates.waiting_for_question_selection,
    TestCreationStates.waiting_for_question_action,
    # TestTaking
    TestTakingStates.waiting_for_test_selection,
    TestTakingStates.waiting_for_test_start,
    # Mentorship
    MentorshipStates.waiting_for_trainee_selection,
    MentorshipStates.waiting_for_mentor_selection,
    MentorshipStates.waiting_for_assignment_confirmation,
    MentorshipStates.waiting_for_trainee_action,
    MentorshipStates.waiting_for_test_assignment,
    MentorshipStates.waiting_for_test_selection_for_trainee,
    # TraineeManagement
    TraineeManagementStates.waiting_for_trainee_selection,
    TraineeManagementStates.waiting_for_trainee_action,
    TraineeManagementStates.waiting_for_test_access_grant,
    # ObjectManagement
    ObjectManagementStates.waiting_for_delete_object_selection,
    ObjectManagementStates.waiting_for_delete_confirmation,
)

# Состояния с повторным вводом текста
TEXT_RETRY_FILTER = StateFilter(
    TestCreationStates.waiting_for_description,
    TestCreationStates.waiting_for_new_test_description,
    TestCreationStates.waiting_for_answer_edit,
)

# Названия групп/объектов
GROUP_NAME_FILTER = StateFilter(
    GroupManagementStates.waiting_for_group_name,
    GroupManagementStates.waiting_for_new_group_name,
)

OBJECT_NAME_FILTER = StateFilter(
    ObjectManagementStates.waiting_for_object_name,
    ObjectManagementStates.waiting_for_new_object_name,
)

# Названия траекторий/этапов/сессий/аттестаций
ENTITY_NAME_FILTER = StateFilter(
    LearningPathStates.waiting_for_trajectory_name,
    LearningPathStates.waiting_for_stage_name,
    LearningPathStates.waiting_for_session_name,
    AttestationStates.waiting_for_attestation_name,
)

# Числовые поля (баллы/пороги)
NUMERIC_INPUT_FILTER = StateFilter(
    AttestationStates.waiting_for_passing_score,
    LearningPathStates.creating_test_threshold,
    LearningPathStates.creating_test_question_points,
)

# Текстовые поля при создании теста в траектории
LP_TEST_TEXT_FILTER = StateFilter(
    LearningPathStates.creating_test_name,
    LearningPathStates.creating_test_question_text,
    LearningPathStates.creating_test_question_options,
    LearningPathStates.creating_test_question_answer,
    LearningPathStates.creating_test_description,
)

# Баллы при создании/редактировании теста
POINTS_FILTER = StateFilter(
    TestCreationStates.waiting_for_points,
    TestCreationStates.waiting_for_points_edit,
)

# Стандартный fallback для множества состояний
GENERIC_FALLBACK_FILTER = StateFilter(
    AuthStates.waiting_for_auth,
    # Group management
    GroupManagementStates.waiting_for_group_selection,
    GroupManagementStates.waiting_for_rename_confirmation,
    GroupManagementStates.waiting_for_delete_group_selection,
    GroupManagementStates.waiting_for_delete_confirmation,
    # Object management
    ObjectManagementStates.waiting_for_object_selection,
    ObjectManagementStates.waiting_for_object_rename_confirmation,
    # User activation
    UserActivationStates.waiting_for_user_selection,
    UserActivationStates.waiting_for_role_selection,
    UserActivationStates.waiting_for_group_selection,
    UserActivationStates.waiting_for_internship_object_selection,
    UserActivationStates.waiting_for_work_object_selection,
    UserActivationStates.waiting_for_activation_confirmation,
    # User edit
    UserEditStates.waiting_for_user_number,
    UserEditStates.waiting_for_new_full_name,
    UserEditStates.waiting_for_new_phone,
    UserEditStates.waiting_for_new_role,
    UserEditStates.waiting_for_new_group,
    UserEditStates.waiting_for_new_internship_object,
    UserEditStates.waiting_for_new_work_object,
    UserEditStates.waiting_for_change_confirmation,
    UserEditStates.waiting_for_filter_selection,
    UserEditStates.waiting_for_user_selection,
    UserEditStates.viewing_user_info,
    # Learning paths
    LearningPathStates.main_menu,
    LearningPathStates.waiting_for_test_selection,
    LearningPathStates.creating_test_materials_choice,
    LearningPathStates.creating_test_question_type,
    LearningPathStates.creating_test_more_questions,
    LearningPathStates.adding_session_to_stage,
    LearningPathStates.adding_stage_to_trajectory,
    LearningPathStates.waiting_for_attestation_selection,
    LearningPathStates.waiting_for_group_selection,
    LearningPathStates.waiting_for_final_save_confirmation,
    LearningPathStates.waiting_for_trajectory_save_confirmation,
    LearningPathStates.waiting_for_trajectory_selection,
    LearningPathStates.editing_trajectory,
    # Attestation
    AttestationStates.main_menu,
    AttestationStates.waiting_for_more_questions,
    AttestationStates.waiting_for_attestation_selection,
    AttestationStates.editing_attestation,
    AttestationStates.waiting_for_delete_confirmation,
    # Broadcast
    BroadcastStates.selecting_test,
    BroadcastStates.selecting_groups,
    # Attestation assignment
    AttestationAssignmentStates.selecting_manager_for_attestation,
    AttestationAssignmentStates.confirming_attestation_assignment,
    # Recruiter attestation
    RecruiterAttestationStates.selecting_manager,
    RecruiterAttestationStates.confirming_assignment,
    # Manager attestation
    ManagerAttestationStates.confirming_schedule,
    ManagerAttestationStates.confirming_result,
    # Trainee trajectory
    TraineeTrajectoryStates.selecting_stage,
    TraineeTrajectoryStates.selecting_session,
    TraineeTrajectoryStates.selecting_test,
    TraineeTrajectoryStates.viewing_materials,
    TraineeTrajectoryStates.taking_test,
    # Knowledge base
    KnowledgeBaseStates.main_menu,
    KnowledgeBaseStates.folder_created_add_material,
    KnowledgeBaseStates.confirming_material_save,
    KnowledgeBaseStates.viewing_folder,
)


# =================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =================================


async def send_fallback_message(message: Message, state: FSMContext):
    """Универсальная функция для отправки fallback сообщения с неожиданным вводом"""
    await message.answer(
        "👀 <b>Команда не распознана</b>\n\n"
        "Бот не знает такую команду. Похоже, ты ввел что-то случайно…\n\n"
        "Вот что можно сделать дальше:",
        parse_mode="HTML",
        reply_markup=get_fallback_keyboard(),
    )


async def send_use_buttons_message(message: Message):
    """Сообщение для состояний, где нужно использовать кнопки"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используй кнопки для выбора действия.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


# =================================
# ОБРАБОТЧИКИ С УНИКАЛЬНОЙ ЛОГИКОЙ ВАЛИДАЦИИ
# =================================


@router.message(StateFilter(RegistrationStates.waiting_for_full_name))
async def handle_unexpected_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе имени"""
    if not message.text or len(message.text.strip()) < 2:
        await message.answer(
            "❌ <b>Некорректное имя</b>\n\n"
            "Пожалуйста, введи своё полное имя (минимум 2 символа).\n"
            "Например: <code>Иван Петров</code>\n\n"
            "Для отмены регистрации используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )
    else:
        await send_fallback_message(message, state)


@router.message(StateFilter(RegistrationStates.waiting_for_phone))
async def handle_unexpected_phone_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе телефона"""
    await message.answer(
        "❌ <b>Некорректный формат телефона</b>\n\n"
        "Пожалуйста, отправь свой номер телефона, используя кнопку 'Поделиться контактом' или введи в формате:\n"
        "• <code>+7 (999) 123-45-67</code>\n"
        "• <code>89991234567</code>\n\n"
        "Для отмены регистрации используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(RegistrationStates.waiting_for_role))
async def handle_unexpected_role_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе роли"""
    await message.answer(
        "❌ <b>Некорректный выбор роли</b>\n\nПожалуйста, выбери роль, используя кнопки ниже:",
        parse_mode="HTML",
        reply_markup=get_role_selection_keyboard(),
    )


@router.message(StateFilter(TestCreationStates.waiting_for_materials))
async def handle_unexpected_materials_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении материалов"""
    if message.photo:
        await message.answer(
            "❌ <b>Изображения не поддерживаются</b>\n\n"
            "Для материалов можно использовать:\n"
            "• 📎 Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
            "• 🖼️ Изображения: JPG, PNG, GIF, WEBP\n"
            "• 📝 Текстовые ссылки\n"
            "• ⏭️ Пропустить (если материалы не нужны)\n\n"
            "Пожалуйста, отправь документ, изображение или текст.",
            parse_mode="HTML",
        )
    elif message.audio or message.voice or message.video_note:
        await message.answer(
            "❌ <b>Аудио/голосовые сообщения не поддерживаются</b>\n\n"
            "Для материалов можно использовать:\n"
            "• 📎 Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
            "• 🎬 Видео: MP4, MOV\n"
            "• 🖼️ Изображения: JPG, PNG, GIF, WEBP\n"
            "• 📝 Текстовые ссылки\n"
            "• ⏭️ Пропустить (если материалы не нужны)\n\n"
            "Пожалуйста, отправь документ, видео, изображение или текст.",
            parse_mode="HTML",
        )
    elif message.sticker:
        await message.answer(
            "❌ <b>Стикеры не поддерживаются</b>\n\n"
            "Для материалов можно использовать:\n"
            "• 📎 Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
            "• 🖼️ Изображения: JPG, PNG, GIF, WEBP\n"
            "• 📝 Текстовые ссылки\n"
            "• ⏭️ Пропустить (если материалы не нужны)",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\n"
            "Пожалуйста, отправь материалы для изучения:\n"
            "• 📎 Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
            "• 🖼️ Изображения: JPG, PNG, GIF, WEBP\n"
            "• 📝 Текстовую информацию или ссылки\n"
            "• Или нажми кнопку 'Пропустить', если материалы не нужны",
            parse_mode="HTML",
        )


@router.message(StateFilter(TestCreationStates.waiting_for_test_name))
async def handle_unexpected_test_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе названия теста"""
    if not message.text or len(message.text.strip()) < 3:
        await message.answer(
            "❌ <b>Некорректное название</b>\n\n"
            "Название теста должно содержать минимум 3 символа.\n"
            "Пожалуйста, введи осмысленное название для твоего теста.\n\n"
            "Для отмены создания теста используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\nПожалуйста, введи название для твоего теста:", parse_mode="HTML"
        )


@router.message(StateFilter(TestCreationStates.waiting_for_question_text))
async def handle_unexpected_question_text_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе текста вопроса"""
    if not message.text or len(message.text.strip()) < 5:
        await message.answer(
            "❌ <b>Слишком короткий вопрос</b>\n\n"
            "Текст вопроса должен содержать минимум 5 символов.\n"
            "Пожалуйста, сформулируй вопрос более подробно.",
            parse_mode="HTML",
        )
    else:
        await message.answer("🔄 <b>Повтори ввод</b>\n\nПожалуйста, введи текст вопроса:", parse_mode="HTML")


@router.message(StateFilter(TestCreationStates.waiting_for_answer))
async def handle_unexpected_answer_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе правильного ответа"""
    data = await state.get_data()
    q_type = data.get("current_question_type")

    if q_type == "single_choice":
        await message.answer(
            "❌ <b>Некорректный номер ответа</b>\n\n"
            "Пожалуйста, введи номер правильного ответа из предложенных вариантов.\n"
            "Например: <code>2</code>",
            parse_mode="HTML",
        )
    elif q_type == "multiple_choice":
        await message.answer(
            "❌ <b>Некорректный формат ответа</b>\n\n"
            "Пожалуйста, введи номера правильных ответов через запятую.\n"
            "Например: <code>1, 3</code> или <code>2, 4, 5</code>",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\nПожалуйста, введи правильный ответ на вопрос:", parse_mode="HTML"
        )


@router.message(POINTS_FILTER)
async def handle_unexpected_points_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе баллов"""
    if message.text:
        try:
            points = float(message.text.replace(",", "."))
            if points <= 0:
                await message.answer(
                    "❌ <b>Баллы должны быть больше нуля</b>\n\n"
                    "Пожалуйста, введи положительное число баллов.\n"
                    "Например: <code>1</code>, <code>2.5</code>, <code>0.5</code>",
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    "❌ <b>Неожиданная ошибка</b>\n\nПовтори ввод количества баллов:", parse_mode="HTML"
                )
        except ValueError:
            await message.answer(
                "❌ <b>Некорректное количество баллов</b>\n\n"
                "Пожалуйста, введи положительное число баллов.\n"
                "Можно использовать дробные числа: <code>1</code>, <code>2.5</code>, <code>0.5</code>",
                parse_mode="HTML",
            )
    else:
        await message.answer(
            "❌ <b>Пустое значение</b>\n\nПожалуйста, введи количество баллов числом.", parse_mode="HTML"
        )


@router.message(StateFilter(TestCreationStates.waiting_for_threshold))
async def handle_unexpected_threshold_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе проходного балла"""
    data = await state.get_data()
    questions = data.get("questions", [])
    max_score = sum(q["points"] for q in questions) if questions else 100

    await message.answer(
        f"❌ <b>Некорректный проходной балл</b>\n\n"
        f"Проходной балл должен быть числом от 0.5 до {max_score:.1f}.\n"
        f"Введи корректное значение проходного балла:",
        parse_mode="HTML",
    )


@router.message(StateFilter(TestCreationStates.waiting_for_new_test_name))
async def handle_unexpected_new_test_name(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении названия теста"""
    if not message.text or len(message.text.strip()) < 3:
        await message.answer(
            "❌ <b>Некорректное название</b>\n\n"
            "Новое название теста должно содержать минимум 3 символа.\n\n"
            "Для отмены используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )
    else:
        await message.answer("🔄 <b>Повтори ввод</b>\n\nПожалуйста, введи новое название для теста:", parse_mode="HTML")


@router.message(StateFilter(TestCreationStates.waiting_for_new_threshold))
async def handle_unexpected_new_threshold(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении проходного балла"""
    if message.text:
        try:
            threshold = float(message.text.replace(",", "."))
            if threshold <= 0:
                await message.answer(
                    "❌ <b>Проходной балл должен быть больше нуля</b>\n\nПожалуйста, введи корректное значение.",
                    parse_mode="HTML",
                )
            else:
                await message.answer("🔄 <b>Повтори ввод</b>\n\nВведи новый проходной балл:", parse_mode="HTML")
        except ValueError:
            await message.answer(
                "❌ <b>Некорректный проходной балл</b>\n\n"
                "Пожалуйста, введи числовое значение проходного балла.\n\n"
                "Для отмены используй кнопку 'Отмена' в интерфейсе",
                parse_mode="HTML",
            )
    else:
        await message.answer("❌ <b>Пустое значение</b>\n\nПожалуйста, введи проходной балл числом.", parse_mode="HTML")


@router.message(StateFilter(TestCreationStates.waiting_for_question_edit))
async def handle_unexpected_question_edit(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании вопроса"""
    if not message.text or len(message.text.strip()) < 5:
        await message.answer(
            "❌ <b>Слишком короткий вопрос</b>\n\n"
            "Текст вопроса должен содержать минимум 5 символов.\n\n"
            "Для отмены используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )
    else:
        await message.answer("🔄 <b>Повтори ввод</b>\n\nПожалуйста, введи новый текст вопроса:", parse_mode="HTML")


@router.message(StateFilter(TestTakingStates.taking_test))
async def handle_unexpected_test_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода во время прохождения теста"""
    data = await state.get_data()
    questions = data.get("questions", [])
    if not questions:
        await message.answer(
            "❌ <b>Ошибка теста</b>\n\nПроизошла ошибка при прохождении теста. Попробуй начать заново.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    current_index = data.get("current_question_index", 0)
    if current_index >= len(questions):
        await message.answer(
            "❌ <b>Тест завершен</b>\n\nТы уже ответил на все вопросы. Ожидай результатов.", parse_mode="HTML"
        )
        return

    question = questions[current_index]

    if question.question_type == "text":
        await message.answer(
            "🔄 <b>Повтори ответ</b>\n\nПожалуйста, введи свой ответ на текущий вопрос в виде текста.",
            parse_mode="HTML",
        )
    elif question.question_type == "number":
        await message.answer(
            "❌ <b>Некорректный числовой ответ</b>\n\nПожалуйста, введи число в качестве ответа на вопрос.",
            parse_mode="HTML",
        )
    elif question.question_type == "multiple_choice":
        await message.answer(
            "❌ <b>Некорректный формат ответа</b>\n\n"
            "Для вопросов с множественным выбором введи номера правильных ответов через запятую.\n"
            "Например: <code>1, 3</code>",
            parse_mode="HTML",
        )
    else:
        await send_fallback_message(message, state)


@router.message(StateFilter(TestTakingStates.test_completed))
async def handle_unexpected_test_completed(message: Message, state: FSMContext):
    """Обработка неожиданного ввода после завершения теста"""
    await message.answer(
        "✅ <b>Тест уже завершен</b>\n\n"
        "Ты уже завершил прохождение теста. Результаты сохранены.\n\n"
        "Используй <code>/start</code> для перехода в главное меню.",
        parse_mode="HTML",
    )


@router.message(StateFilter(ManagerAttestationStates.waiting_for_date))
async def handle_unexpected_date_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе даты аттестации"""
    await message.answer(
        "❓ <b>Неправильный формат даты</b>\n\n"
        "Пожалуйста, введи дату в формате: <code>ДД.ММ.ГГГГ</code>\n\n"
        "📅 <b>Примеры корректного ввода:</b>\n"
        "• 28.08.2025\n"
        "• 01.12.2025\n"
        "• 15.09.2025\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(ManagerAttestationStates.waiting_for_time))
async def handle_unexpected_time_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе времени аттестации"""
    await message.answer(
        "❓ <b>Неправильный формат времени</b>\n\n"
        "Пожалуйста, введи время в формате: <code>ЧЧ:ММ</code>\n\n"
        "⏰ <b>Примеры корректного ввода:</b>\n"
        "• 12:00\n"
        "• 09:30\n"
        "• 16:45\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(ManagerAttestationStates.waiting_for_score))
async def handle_unexpected_score_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при оценке вопроса аттестации"""
    await message.answer(
        "❓ <b>Неправильный формат балла</b>\n\n"
        "Пожалуйста, введи балл числом от 0 до максимального балла за вопрос.\n\n"
        "📊 <b>Примеры корректного ввода:</b>\n"
        "• 10 - отличный ответ\n"
        "• 5 - удовлетворительный ответ\n"
        "• 0 - неправильный/отсутствующий ответ\n\n"
        "⚠️ Балл не может быть больше максимального или отрицательным.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(CompanyManagementStates.waiting_for_company_name_edit))
async def handle_unexpected_company_name_edit_input(message: Message, state: FSMContext):
    """Обработчик неожиданного ввода при редактировании названия компании"""
    await message.answer(
        "❌ <b>Ожидается текстовое сообщение</b>\n\n"
        "Пожалуйста, введи новое название для компании текстом.\n"
        "Название должно содержать от 3 до 100 символов.",
        parse_mode="HTML",
    )


@router.message(StateFilter(CompanyManagementStates.waiting_for_company_description_edit))
async def handle_unexpected_company_description_edit_input(message: Message, state: FSMContext):
    """Обработчик неожиданного ввода при редактировании описания компании"""
    await message.answer(
        "❌ <b>Ожидается текстовое сообщение</b>\n\n"
        "Пожалуйста, введи новое описание для компании текстом.\n"
        "Описание не должно превышать 500 символов.",
        parse_mode="HTML",
    )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_folder_name))
async def handle_unexpected_folder_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании папки"""
    if not message.text:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Название папки должно быть текстом.\n\n"
            "📝 <b>Требования:</b>\n"
            "• Только текст (без файлов, изображений)\n"
            "• От 3 до 50 символов\n"
            "• Уникальное название\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_name))
async def handle_unexpected_material_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании материала"""
    if not message.text:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Название материала должно быть текстом.\n\n"
            "📝 <b>Требования:</b>\n"
            "• Только текст (без файлов, изображений)\n"
            "• От 3 до 100 символов\n"
            "• Понятное название для сотрудников\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_content))
async def handle_unexpected_material_content_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении содержимого материала"""
    if not message.text and not message.document:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Содержимое материала должно быть ссылкой или документом.\n\n"
            "📎 <b>Поддерживаемые форматы:</b>\n"
            "• Ссылка (URL) - отправь текстом\n"
            "• Документы: PDF, DOC, DOCX, TXT, RTF, ODT\n"
            "• Таблицы: XLS, XLSX\n"
            "• Презентации: PPT, PPTX\n"
            "• Изображения: JPG, PNG, GIF, WEBP\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_description))
async def handle_unexpected_material_description_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении описания материала"""
    if not message.text:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Описание материала должно быть текстом.\n\n"
            "📝 <b>Как правильно:</b>\n"
            "• Введи описание текстом\n"
            '• Или нажми "⏩Пропустить" для продолжения без описания\n\n'
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_photos))
async def handle_unexpected_material_photos_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении фотографий к материалу"""
    if not message.photo and not message.media_group_id:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Ожидаются фотографии для материала.\n\n"
            "🖼️ <b>Как правильно:</b>\n"
            "• Отправь фотографию или несколько фотографий\n"
            '• Или нажми "⏩Пропустить" для продолжения без фото\n\n'
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(LearningPathStates.waiting_for_attestation_confirmation))
async def handle_unexpected_attestation_confirmation_input(message: Message, state: FSMContext):
    """Fallback для состояния подтверждения аттестации"""
    await message.answer(
        "⚠️ <b>Пожалуйста, используй кнопки!</b>\n\n"
        "📋 Доступные действия:\n"
        "• ✅Да - подтвердить добавление аттестации\n"
        "• 🚫Отменить - вернуться к выбору аттестации\n\n"
        "❓ Нажмите на соответствующую кнопку ниже.",
        parse_mode="HTML",
    )


@router.message(StateFilter(TestCreationStates.waiting_for_option))
async def handle_unexpected_option_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении вариантов ответа"""
    if not message.text or len(message.text.strip()) < 1:
        await message.answer(
            "❌ <b>Пустой вариант ответа</b>\n\n"
            "Вариант ответа не может быть пустым.\n"
            "Пожалуйста, введи текст варианта ответа:",
            parse_mode="HTML",
        )
    else:
        await message.answer("🔄 <b>Повтори ввод</b>\n\nПожалуйста, введи вариант ответа:", parse_mode="HTML")


@router.message(StateFilter(TestCreationStates.waiting_for_new_materials))
async def handle_unexpected_new_materials(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении материалов"""
    await message.answer(
        "🔄 <b>Повтори ввод</b>\n\n"
        "Пожалуйста, отправь новые материалы:\n"
        "• 📎 Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
        "• 🖼️ Изображения: JPG, PNG, GIF, WEBP\n"
        "• 📝 Текстовую информацию\n"
        "• Или напиши 'удалить', чтобы убрать материалы\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(AttestationStates.waiting_for_attestation_question))
async def handle_unexpected_attestation_question_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении вопроса аттестации"""
    await message.answer(
        "❓ <b>Некорректный вопрос аттестации</b>\n\n"
        "Пожалуйста, введи полный текст вопроса с критериями оценки.\n\n"
        "Формат вопроса должен включать:\n"
        "• Сам вопрос\n"
        "• Правильный ответ или критерии\n"
        "• Систему оценки (например: все назвал - 10, половину - 5, ничего - 0)\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(LearningPathStates.creating_test_materials))
async def handle_unexpected_test_materials_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении материалов"""
    await message.answer(
        "❓ <b>Некорректные материалы</b>\n\n"
        "Пожалуйста, отправь:\n"
        "• Ссылку на материалы\n"
        "• Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
        "• Изображения: JPG, PNG, GIF, WEBP\n"
        "• Или нажми кнопку 'Пропустить'\n\n"
        "Для отмены создания теста используй кнопку 'Отменить' в интерфейсе",
        parse_mode="HTML",
    )


# =================================
# ГРУППОВЫЕ ОБРАБОТЧИКИ
# =================================


@router.message(USE_BUTTONS_FILTER)
async def handle_use_buttons_states(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в состояниях, где нужно использовать кнопки"""
    await send_use_buttons_message(message)


@router.message(TEXT_RETRY_FILTER)
async def handle_text_retry_states(message: Message, state: FSMContext):
    """Обработка повторного ввода текста"""
    await message.answer(
        "🔄 <b>Повтори ввод</b>\n\nПожалуйста, введи текст ещё раз.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(GROUP_NAME_FILTER)
async def handle_unexpected_group_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании/переименовании группы"""
    await message.answer(
        "❓ <b>Некорректное название группы</b>\n\n"
        "Пожалуйста, введи корректное название для группы.\n"
        "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(OBJECT_NAME_FILTER)
async def handle_unexpected_object_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании/переименовании объекта"""
    await message.answer(
        "❓ <b>Некорректное название объекта</b>\n\n"
        "Пожалуйста, введи корректное название для объекта.\n"
        "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(ENTITY_NAME_FILTER)
async def handle_unexpected_name_inputs(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе названий (траектория/этап/сессия/аттестация)"""
    await message.answer(
        "❓ <b>Некорректное название</b>\n\n"
        "Пожалуйста, введи корректное название (минимум 3 символа).\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(NUMERIC_INPUT_FILTER)
async def handle_unexpected_numeric_inputs(message: Message, state: FSMContext):
    """Обработка неожиданного ввода числовых значений (баллы/пороги)"""
    await message.answer(
        "❓ <b>Некорректное число</b>\n\n"
        "Пожалуйста, введи положительное число.\n"
        "Можно использовать дробные числа (например: 1.5)\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(LP_TEST_TEXT_FILTER)
async def handle_unexpected_lp_test_text_inputs(message: Message, state: FSMContext):
    """Обработка неожиданного текстового ввода при создании теста в траектории"""
    await message.answer(
        "❓ <b>Некорректный ввод</b>\n\n"
        "Пожалуйста, введи корректный текст.\n\n"
        "Для отмены создания теста используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(GENERIC_FALLBACK_FILTER)
async def handle_generic_fallback_states(message: Message, state: FSMContext):
    """Обработка неожиданного ввода — стандартный fallback для множества состояний"""
    await send_fallback_message(message, state)


# =================================
# УНИВЕРСАЛЬНЫЙ FALLBACK ДЛЯ ТЕКСТОВЫХ СООБЩЕНИЙ
# =================================


@router.message(F.text)
async def handle_unexpected_input_with_state(message: Message, state: FSMContext, session: AsyncSession):
    """Универсальный обработчик для неожиданного ввода в любых состояниях"""
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        from keyboards.keyboards import get_company_selection_keyboard

        await message.answer(
            "Привет! Добро пожаловать в чат-бот.\n\n🏢 Выбери действие:", reply_markup=get_company_selection_keyboard()
        )
        log_user_action(message.from_user.id, message.from_user.username, "unregistered user sent text")
        return

    current_state = await state.get_state()

    if current_state:
        await message.answer(
            "👀 <b>Команда не распознана</b>\n\n"
            "Бот не знает такую команду. Похоже, ты ввел что-то случайно…\n\n"
            "Вот что можно сделать дальше:",
            parse_mode="HTML",
            reply_markup=get_fallback_keyboard(),
        )

        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "unexpected_input",
            {"state": current_state, "input": message.text[:100]},
        )
    else:
        await send_fallback_message(message, state)


# =================================
# ОБРАБОТЧИК ДЛЯ НЕОЖИДАННЫХ CALLBACK QUERY
# =================================


@router.callback_query(F.data & ~F.data.in_(["main_menu", "fallback_back"]))
async def handle_unexpected_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик для неожиданных callback запросов"""
    current_state = await state.get_state()

    await callback.message.edit_text(
        "👀 <b>Команда не распознана</b>\n\n"
        "Бот не знает такую команду. Похоже, ты ввел что-то случайно…\n\n"
        "Вот что можно сделать дальше:",
        parse_mode="HTML",
        reply_markup=get_fallback_keyboard(),
    )

    await callback.answer("👀 Команда не распознана", show_alert=True)

    log_user_action(
        callback.from_user.id,
        callback.from_user.username,
        "unexpected_callback",
        {"state": current_state, "data": callback.data},
    )
