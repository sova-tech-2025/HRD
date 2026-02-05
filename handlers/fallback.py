from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession
from database.db import get_user_by_tg_id

from states.states import (
    AuthStates, RegistrationStates, AdminStates,
    TestCreationStates, TestTakingStates,
    MentorshipStates, TraineeManagementStates,
    GroupManagementStates, ObjectManagementStates, UserActivationStates,
    UserEditStates, LearningPathStates, AttestationStates,
    TraineeTrajectoryStates, MentorAssignmentStates, AttestationAssignmentStates,
    ManagerAttestationStates, BroadcastStates, KnowledgeBaseStates,
    CompanyManagementStates, RecruiterAttestationStates
)
from keyboards.keyboards import get_role_selection_keyboard, get_yes_no_keyboard, get_question_type_keyboard, get_fallback_keyboard
from utils.logger import log_user_action

router = Router()

# =================================
# УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ FALLBACK СООБЩЕНИЙ
# =================================

async def send_fallback_message(message: Message, state: FSMContext):
    """Универсальная функция для отправки fallback сообщения с неожиданным вводом"""
    await message.answer(
        "👀 <b>Команда не распознана</b>\n\n"
        "Бот не знает такую команду. Похоже, ты ввел что-то случайно…\n\n"
        "Вот что можно сделать дальше:",
        parse_mode="HTML",
        reply_markup=get_fallback_keyboard()
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ АВТОРИЗАЦИИ
# =================================

@router.message(StateFilter(AuthStates.waiting_for_auth))
async def handle_unexpected_auth_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в состоянии авторизации"""
    await send_fallback_message(message, state)

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ РЕГИСТРАЦИИ
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
            parse_mode="HTML"
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
        parse_mode="HTML"
    )

@router.message(StateFilter(RegistrationStates.waiting_for_role))
async def handle_unexpected_role_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе роли"""
    await message.answer(
        "❌ <b>Некорректный выбор роли</b>\n\n"
        "Пожалуйста, выбери роль, используя кнопки ниже:",
        parse_mode="HTML",
        reply_markup=get_role_selection_keyboard()
    )

@router.message(StateFilter(RegistrationStates.waiting_for_admin_token))
async def handle_unexpected_token_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе админ-токена"""
    await message.answer(
        "❌ <b>Некорректный токен</b>\n\n"
        "Введи корректный токен администратора для регистрации в роли управляющего.\n"
        "Если у тебя нет токена, вернись к выбору роли.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ СОЗДАНИЯ ТЕСТОВ
# =================================

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
            parse_mode="HTML"
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
            parse_mode="HTML"
        )
    elif message.sticker:
        await message.answer(
            "❌ <b>Стикеры не поддерживаются</b>\n\n"
            "Для материалов можно использовать:\n"
            "• 📎 Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
            "• 🖼️ Изображения: JPG, PNG, GIF, WEBP\n"
            "• 📝 Текстовые ссылки\n"
            "• ⏭️ Пропустить (если материалы не нужны)",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\n"
            "Пожалуйста, отправь материалы для изучения:\n"
            "• 📎 Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
            "• 🖼️ Изображения: JPG, PNG, GIF, WEBP\n"
            "• 📝 Текстовую информацию или ссылки\n"
            "• Или нажми кнопку 'Пропустить', если материалы не нужны",
            parse_mode="HTML"
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
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\n"
            "Пожалуйста, введи название для твоего теста:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_description))
async def handle_unexpected_description_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе описания теста"""
    await message.answer(
        "🔄 <b>Повтори ввод</b>\n\n"
        "Пожалуйста, введи описание для своего теста.\n"
        "Описание поможет стажерам понять цель и содержание теста.\n\n"
        "Ты можешь нажать кнопку 'Пропустить', если не хочешь добавлять описание.",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_question_text))
async def handle_unexpected_question_text_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе текста вопроса"""
    if not message.text or len(message.text.strip()) < 5:
        await message.answer(
            "❌ <b>Слишком короткий вопрос</b>\n\n"
            "Текст вопроса должен содержать минимум 5 символов.\n"
            "Пожалуйста, сформулируй вопрос более подробно.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\n"
            "Пожалуйста, введи текст вопроса:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_option))
async def handle_unexpected_option_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении вариантов ответа"""
    if not message.text or len(message.text.strip()) < 1:
        await message.answer(
            "❌ <b>Пустой вариант ответа</b>\n\n"
            "Вариант ответа не может быть пустым.\n"
            "Пожалуйста, введи текст варианта ответа:",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\n"
            "Пожалуйста, введи вариант ответа:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_answer))
async def handle_unexpected_answer_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе правильного ответа"""
    data = await state.get_data()
    q_type = data.get('current_question_type')
    
    if q_type == 'single_choice':
        await message.answer(
            "❌ <b>Некорректный номер ответа</b>\n\n"
            "Пожалуйста, введи номер правильного ответа из предложенных вариантов.\n"
            "Например: <code>2</code>",
            parse_mode="HTML"
        )
    elif q_type == 'multiple_choice':
        await message.answer(
            "❌ <b>Некорректный формат ответа</b>\n\n"
            "Пожалуйста, введи номера правильных ответов через запятую.\n"
            "Например: <code>1, 3</code> или <code>2, 4, 5</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\n"
            "Пожалуйста, введи правильный ответ на вопрос:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_points))
async def handle_unexpected_points_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе баллов"""
    if message.text:
        try:
            points = float(message.text.replace(',', '.'))
            if points <= 0:
                await message.answer(
                    "❌ <b>Баллы должны быть больше нуля</b>\n\n"
                    "Пожалуйста, введи положительное число баллов.\n"
                    "Например: <code>1</code>, <code>2.5</code>, <code>0.5</code>",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "❌ <b>Неожиданная ошибка</b>\n\n"
                    "Повтори ввод количества баллов:",
                    parse_mode="HTML"
                )
        except ValueError:
            await message.answer(
                "❌ <b>Некорректное количество баллов</b>\n\n"
                "Пожалуйста, введи положительное число баллов за правильный ответ.\n"
                "Можно использовать дробные числа: <code>1</code>, <code>2.5</code>, <code>0.5</code>\n\n"
                "Баллы должны быть больше нуля.",
                parse_mode="HTML"
            )
    else:
        await message.answer(
            "❌ <b>Пустое значение</b>\n\n"
            "Пожалуйста, введи количество баллов числом.",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_threshold))
async def handle_unexpected_threshold_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе проходного балла"""
    data = await state.get_data()
    questions = data.get('questions', [])
    max_score = sum(q['points'] for q in questions) if questions else 100
    
    await message.answer(
        f"❌ <b>Некорректный проходной балл</b>\n\n"
        f"Проходной балл должен быть числом от 0.5 до {max_score:.1f}.\n"
        f"Введи корректное значение проходного балла:",
        parse_mode="HTML"
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ АДМИНИСТРАТИВНЫХ СОСТОЯНИЙ
# =================================

@router.message(StateFilter(AdminStates.waiting_for_user_selection))
async def handle_unexpected_admin_user_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе пользователя для управления"""
    await message.answer(
        "❌ <b>Некорректный выбор пользователя</b>\n\n"
        "Пожалуйста, используй кнопки для выбора пользователя из списка.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(AdminStates.waiting_for_user_action))
async def handle_unexpected_admin_user_action(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе действия с пользователем"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используй кнопки для выбора действия с пользователем.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(AdminStates.waiting_for_role_change))
async def handle_unexpected_admin_role_change(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении роли"""
    await message.answer(
        "❌ <b>Некорректная роль</b>\n\n"
        "Пожалуйста, используй кнопки для выбора новой роли пользователя.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(AdminStates.waiting_for_confirmation))
async def handle_unexpected_admin_confirmation(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении действия"""
    await message.answer(
        "❌ <b>Некорректное подтверждение</b>\n\n"
        "Пожалуйста, используй кнопки 'Да' или 'Нет' для подтверждения действия.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(AdminStates.waiting_for_role_selection, AdminStates.waiting_for_permission_action, AdminStates.waiting_for_permission_selection, AdminStates.waiting_for_permission_confirmation))
async def handle_unexpected_admin_permissions(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в состояниях управления правами"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используй кнопки для управления ролями и правами.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

# =================================
# ДОПОЛНИТЕЛЬНЫЕ ОБРАБОТЧИКИ ДЛЯ РЕДАКТИРОВАНИЯ ТЕСТОВ
# =================================

@router.message(StateFilter(TestCreationStates.waiting_for_more_questions))
async def handle_unexpected_more_questions(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе добавления вопросов"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используй кнопки для выбора:\n"
        "• 'Добавить еще вопрос'\n"
        "• 'Завершить создание теста'\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_stage_selection))
async def handle_unexpected_stage_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе этапа"""
    await message.answer(
        "❌ <b>Некорректный этап</b>\n\n"
        "Пожалуйста, используй кнопки для выбора этапа стажировки.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_final_confirmation))
async def handle_unexpected_final_confirmation(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при финальном подтверждении"""
    await message.answer(
        "❌ <b>Некорректное подтверждение</b>\n\n"
        "Пожалуйста, используй кнопки 'Да' или 'Нет' для подтверждения создания теста.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_edit_action))
async def handle_unexpected_edit_action(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе действия редактирования"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используй кнопки для выбора действия редактирования теста.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_new_test_name))
async def handle_unexpected_new_test_name(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении названия теста"""
    if not message.text or len(message.text.strip()) < 3:
        await message.answer(
            "❌ <b>Некорректное название</b>\n\n"
            "Новое название теста должно содержать минимум 3 символа.\n\n"
            "Для отмены используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\n"
            "Пожалуйста, введи новое название для теста:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_new_test_description))
async def handle_unexpected_new_description(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении описания теста"""
    await message.answer(
        "🔄 <b>Повтори ввод</b>\n\n"
        "Пожалуйста, введи новое описание для теста.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_new_threshold))
async def handle_unexpected_new_threshold(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении проходного балла"""
    if message.text:
        try:
            threshold = float(message.text.replace(',', '.'))
            if threshold <= 0:
                await message.answer(
                    "❌ <b>Проходной балл должен быть больше нуля</b>\n\n"
                    "Пожалуйста, введи корректное значение.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "🔄 <b>Повтори ввод</b>\n\n"
                    "Введи новый проходной балл:",
                    parse_mode="HTML"
                )
        except ValueError:
            await message.answer(
                "❌ <b>Некорректный проходной балл</b>\n\n"
                "Пожалуйста, введи числовое значение проходного балла.\n\n"
                "Для отмены используй кнопку 'Отмена' в интерфейсе",
                parse_mode="HTML"
            )
    else:
        await message.answer(
            "❌ <b>Пустое значение</b>\n\n"
            "Пожалуйста, введи проходной балл числом.",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_new_stage, TestCreationStates.waiting_for_new_attempts))
async def handle_unexpected_test_settings(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении настроек теста"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используй кнопки для изменения настроек теста.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

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
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_question_selection, TestCreationStates.waiting_for_question_action))
async def handle_unexpected_question_management(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при управлении вопросами"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используй кнопки для управления вопросами теста.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_question_edit))
async def handle_unexpected_question_edit(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании вопроса"""
    if not message.text or len(message.text.strip()) < 5:
        await message.answer(
            "❌ <b>Слишком короткий вопрос</b>\n\n"
            "Текст вопроса должен содержать минимум 5 символов.\n\n"
            "Для отмены используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повтори ввод</b>\n\n"
            "Пожалуйста, введи новый текст вопроса:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_answer_edit))
async def handle_unexpected_answer_edit(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании ответа"""
    await message.answer(
        "🔄 <b>Повтори ввод</b>\n\n"
        "Пожалуйста, введи новый правильный ответ.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_points_edit))
async def handle_unexpected_points_edit(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании баллов"""
    if message.text:
        try:
            points = float(message.text.replace(',', '.'))
            if points <= 0:
                await message.answer(
                    "❌ <b>Баллы должны быть больше нуля</b>\n\n"
                    "Пожалуйста, введи положительное число.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "🔄 <b>Повтори ввод</b>\n\n"
                    "Введи новое количество баллов:",
                    parse_mode="HTML"
                )
        except ValueError:
            await message.answer(
                "❌ <b>Некорректное количество баллов</b>\n\n"
                "Пожалуйста, введи числовое значение.\n\n"
                "Для отмены используй кнопку 'Отмена' в интерфейсе",
                parse_mode="HTML"
            )
    else:
        await message.answer(
            "❌ <b>Пустое значение</b>\n\n"
            "Пожалуйста, введи количество баллов числом.",
            parse_mode="HTML"
        )

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ ПРОХОЖДЕНИЯ ТЕСТОВ
# =================================

@router.message(StateFilter(TestTakingStates.waiting_for_test_selection))
async def handle_unexpected_test_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе теста для прохождения"""
    await message.answer(
        "❌ <b>Некорректный выбор теста</b>\n\n"
        "Пожалуйста, используй кнопки для выбора теста из списка.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestTakingStates.waiting_for_test_start))
async def handle_unexpected_test_start(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении начала теста"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используй кнопки для начала теста или отмены.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestTakingStates.test_completed))
async def handle_unexpected_test_completed(message: Message, state: FSMContext):
    """Обработка неожиданного ввода после завершения теста"""
    await message.answer(
        "✅ <b>Тест уже завершен</b>\n\n"
        "Ты уже завершил прохождение теста. Результаты сохранены.\n\n"
        "Используй <code>/start</code> для перехода в главное меню.",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestTakingStates.taking_test))
async def handle_unexpected_test_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода во время прохождения теста"""
    data = await state.get_data()
    questions = data.get('questions', [])
    if not questions:
        await message.answer(
            "❌ <b>Ошибка теста</b>\n\n"
            "Произошла ошибка при прохождении теста. Попробуй начать заново.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    current_index = data.get('current_question_index', 0)
    if current_index >= len(questions):
        await message.answer(
            "❌ <b>Тест завершен</b>\n\n"
            "Ты уже ответил на все вопросы. Ожидай результатов.",
            parse_mode="HTML"
        )
        return
    
    question = questions[current_index]
    
    if question.question_type == 'text':
        await message.answer(
            "🔄 <b>Повтори ответ</b>\n\n"
            "Пожалуйста, введи свой ответ на текущий вопрос в виде текста.",
            parse_mode="HTML"
        )
    elif question.question_type == 'number':
        await message.answer(
            "❌ <b>Некорректный числовой ответ</b>\n\n"
            "Пожалуйста, введи число в качестве ответа на вопрос.",
            parse_mode="HTML"
        )
    elif question.question_type == 'multiple_choice':
        await message.answer(
            "❌ <b>Некорректный формат ответа</b>\n\n"
            "Для вопросов с множественным выбором введи номера правильных ответов через запятую.\n"
            "Например: <code>1, 3</code>",
            parse_mode="HTML"
        )
    else:
        await send_fallback_message(message, state)

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ НАСТАВНИЧЕСТВА
# =================================

@router.message(StateFilter(MentorshipStates.waiting_for_trainee_selection))
async def handle_unexpected_mentor_trainee_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе стажера для назначения наставника"""
    await message.answer(
        "❌ <b>Некорректный выбор стажера</b>\n\n"
        "Пожалуйста, используй кнопки для выбора стажера из списка.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_mentor_selection))
async def handle_unexpected_mentor_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе наставника"""
    await message.answer(
        "❌ <b>Некорректный выбор наставника</b>\n\n"
        "Пожалуйста, используй кнопки для выбора наставника из списка.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_assignment_confirmation))
async def handle_unexpected_mentor_assignment_confirmation(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении назначения наставника"""
    await message.answer(
        "❌ <b>Некорректное подтверждение</b>\n\n"
        "Пожалуйста, используй кнопки 'Да' или 'Нет' для подтверждения назначения наставника.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_trainee_action))
async def handle_unexpected_mentor_trainee_action(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе действия со стажером"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используй кнопки для выбора действия со стажером.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_test_assignment))
async def handle_unexpected_mentor_test_assignment(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при назначении теста стажеру"""
    await message.answer(
        "❌ <b>Некорректное назначение теста</b>\n\n"
        "Пожалуйста, используй кнопки для назначения теста стажеру.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_test_selection_for_trainee))
async def handle_unexpected_mentor_test_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе теста для назначения стажеру"""
    await message.answer(
        "❌ <b>Некорректный выбор теста</b>\n\n"
        "Пожалуйста, используй кнопки для выбора теста для назначения стажеру.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ УПРАВЛЕНИЯ СТАЖЕРАМИ
# =================================

@router.message(StateFilter(TraineeManagementStates.waiting_for_trainee_selection))
async def handle_unexpected_trainee_management_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе стажера для управления"""
    await message.answer(
        "❌ <b>Некорректный выбор стажера</b>\n\n"
        "Пожалуйста, используй кнопки для выбора стажера из списка.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TraineeManagementStates.waiting_for_trainee_action))
async def handle_unexpected_trainee_management_action(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе действия со стажером"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используй кнопки для выбора действия со стажером.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

@router.message(StateFilter(TraineeManagementStates.waiting_for_test_access_grant))
async def handle_unexpected_trainee_test_access(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при предоставлении доступа к тесту"""
    await message.answer(
        "❌ <b>Некорректное предоставление доступа</b>\n\n"
        "Пожалуйста, используй кнопки для предоставления доступа к тесту стажеру.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ УПРАВЛЕНИЯ ГРУППАМИ
# =================================

@router.message(StateFilter(GroupManagementStates.waiting_for_group_name))
async def handle_unexpected_group_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании группы"""
    await message.answer(
        "❓ <b>Некорректное название группы</b>\n\n"
        "Пожалуйста, введи корректное название для новой группы.\n"
        "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(GroupManagementStates.waiting_for_group_selection))
async def handle_unexpected_group_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе группы"""
    await send_fallback_message(message, state)
@router.message(StateFilter(GroupManagementStates.waiting_for_new_group_name))
async def handle_unexpected_new_group_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении названия группы"""
    await message.answer(
        "❓ <b>Некорректное новое название группы</b>\n\n"
        "Пожалуйста, введи корректное новое название для группы.\n"
        "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(GroupManagementStates.waiting_for_rename_confirmation))
async def handle_unexpected_rename_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении переименования"""
    await send_fallback_message(message, state)


@router.message(StateFilter(GroupManagementStates.waiting_for_delete_group_selection))
async def handle_unexpected_delete_group_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе группы для удаления"""
    await send_fallback_message(message, state)


@router.message(StateFilter(GroupManagementStates.waiting_for_delete_confirmation))
async def handle_unexpected_delete_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении удаления группы"""
    await send_fallback_message(message, state)
@router.message(StateFilter(ObjectManagementStates.waiting_for_object_name))
async def handle_unexpected_object_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании объекта"""
    await message.answer(
        "❓ <b>Некорректное название объекта</b>\n\n"
        "Пожалуйста, введи корректное название для нового объекта.\n"
        "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(ObjectManagementStates.waiting_for_object_selection))
async def handle_unexpected_object_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе объекта"""
    await send_fallback_message(message, state)
@router.message(StateFilter(ObjectManagementStates.waiting_for_new_object_name))
async def handle_unexpected_new_object_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении названия объекта"""
    await message.answer(
        "❓ <b>Некорректное новое название объекта</b>\n\n"
        "Пожалуйста, введи корректное новое название для объекта.\n"
        "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(ObjectManagementStates.waiting_for_object_rename_confirmation))
async def handle_unexpected_object_rename_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении переименования объекта"""
    await send_fallback_message(message, state)


@router.message(StateFilter(ObjectManagementStates.waiting_for_delete_object_selection))
async def handle_unexpected_delete_object_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе объекта для удаления"""
    await message.answer(
        "❓ <b>Некорректный выбор объекта</b>\n\n"
        "Пожалуйста, используй кнопки для выбора объекта для удаления.\n"
        "Или нажми 'Отменить' для возврата в меню управления объектами.",
        parse_mode="HTML"
    )


@router.message(StateFilter(ObjectManagementStates.waiting_for_delete_confirmation))
async def handle_unexpected_delete_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении удаления объекта"""
    await message.answer(
        "❓ <b>Некорректное подтверждение</b>\n\n"
        "Пожалуйста, используй кнопки для подтверждения или отмены удаления объекта.\n"
        "Или нажми 'Отменить' для возврата в меню управления объектами.",
        parse_mode="HTML"
    )


@router.message(StateFilter(UserActivationStates.waiting_for_user_selection))
async def handle_unexpected_user_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе пользователя для активации"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserActivationStates.waiting_for_role_selection))
async def handle_unexpected_role_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе роли"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserActivationStates.waiting_for_group_selection))
async def handle_unexpected_group_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе группы"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserActivationStates.waiting_for_internship_object_selection))
async def handle_unexpected_internship_object_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе объекта стажировки"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserActivationStates.waiting_for_work_object_selection))
async def handle_unexpected_work_object_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе объекта работы"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserActivationStates.waiting_for_activation_confirmation))
async def handle_unexpected_activation_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении активации"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_user_number))
async def handle_unexpected_user_number_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе номера пользователя"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_new_full_name))
async def handle_unexpected_new_full_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе нового ФИО"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_new_phone))
async def handle_unexpected_new_phone_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе нового телефона"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_new_role))
async def handle_unexpected_new_role_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе новой роли"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_new_group))
async def handle_unexpected_new_group_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе новой группы"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_new_internship_object))
async def handle_unexpected_new_internship_object_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе нового объекта стажировки"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_new_work_object))
async def handle_unexpected_new_work_object_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе нового объекта работы"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_change_confirmation))
async def handle_unexpected_change_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении изменений"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_filter_selection))
async def handle_unexpected_filter_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе фильтра пользователей"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.waiting_for_user_selection))
async def handle_unexpected_user_edit_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе пользователя из списка"""
    await send_fallback_message(message, state)
@router.message(StateFilter(UserEditStates.viewing_user_info))
async def handle_unexpected_viewing_user_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при просмотре информации о пользователе"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.main_menu))
async def handle_unexpected_learning_path_main_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в главном меню траекторий"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.waiting_for_trajectory_name))
async def handle_unexpected_trajectory_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе названия траектории"""
    # Дополнительная информация для пользователя
    await message.answer(
        "❓ <b>Некорректное название траектории</b>\n\n"
        "Пожалуйста, введи корректное название для траектории обучения.\n\n"
        "Требования:\n"
        "• Минимум 3 символа\n"
        "• Максимум 100 символов\n"
        "• Только буквы, цифры, пробелы и основные знаки препинания\n\n"
        "Примеры хороших названий:\n"
        "• Разработчик\n"
        "• Менеджер проектов\n"
        "• Специалист по продажам\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.waiting_for_stage_name))
async def handle_unexpected_stage_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе названия этапа"""
    await message.answer(
        "❓ <b>Некорректное название этапа</b>\n\n"
        "Пожалуйста, введи корректное название для этапа траектории.\n\n"
        "Примеры хороших названий этапов:\n"
        "• День 1 теория\n"
        "• Основы практики\n"
        "• Продвинутый уровень\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.waiting_for_session_name))
async def handle_unexpected_session_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе названия сессии"""
    await message.answer(
        "❓ <b>Некорректное название сессии</b>\n\n"
        "Пожалуйста, введи корректное название для сессии.\n\n"
        "Примеры хороших названий сессий:\n"
        "• Общая информация\n"
        "• Правила безопасности\n"
        "• Работа с клиентами\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.waiting_for_test_selection))
async def handle_unexpected_test_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе тестов"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.creating_test_name))
async def handle_unexpected_test_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании названия теста"""
    await message.answer(
        "❓ <b>Некорректное название теста</b>\n\n"
        "Пожалуйста, введи корректное название для теста.\n\n"
        "Примеры хороших названий:\n"
        "• Основы работы с клиентами\n"
        "• Техника безопасности\n"
        "• Знание продукции\n\n"
        "Для отмены создания теста используй кнопку 'Отменить' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.creating_test_materials_choice))
async def handle_unexpected_test_materials_choice_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе добавления материалов"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.creating_test_materials))
async def handle_unexpected_test_materials_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении материалов"""
    await message.answer(
        "❓ <b>Некорректные материалы</b>\n\n"
        "Пожалуйста, отправь:\n"
        "• Ссылку на материалы (например: https://example.com/materials)\n"
        "• Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
        "• Изображения: JPG, PNG, GIF, WEBP\n"
        "• Или нажми кнопку 'Пропустить'\n\n"
        "Для отмены создания теста используй кнопку 'Отменить' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.creating_test_description))
async def handle_unexpected_test_description_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении описания теста"""
    await message.answer(
        "❓ <b>Некорректное описание</b>\n\n"
        "Пожалуйста, введи краткое описание теста или нажми кнопку 'Пропустить'.\n\n"
        "Описание должно помочь стажерам понять:\n"
        "• О чем этот тест\n"
        "• Какие знания проверяются\n"
        "• Что ожидается от стажера\n\n"
        "Для отмены создания теста используй кнопку 'Отменить' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.creating_test_question_type))
async def handle_unexpected_test_question_type_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе типа вопроса"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.creating_test_question_text))
async def handle_unexpected_test_question_text_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе текста вопроса"""
    await message.answer(
        "❓ <b>Некорректный текст вопроса</b>\n\n"
        "Пожалуйста, введи корректный текст вопроса.\n\n"
        "Требования:\n"
        "• Текст не может быть пустым\n"
        "• Вопрос должен быть понятным и конкретным\n"
        "• Избегай слишком сложных формулировок\n\n"
        "Для отмены создания теста используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.creating_test_question_options))
async def handle_unexpected_test_question_options_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе вариантов ответа"""
    await message.answer(
        "❓ <b>Некорректный вариант</b>\n\n"
        "Пожалуйста, введи корректный вариант ответа.\n\n"
        "Требования:\n"
        "• Вариант не может быть пустым\n"
        "• Избегай дубликатов вариантов\n"
        "• После добавления минимум 2 вариантов нажми 'Завершить'\n\n"
        "Для отмены создания теста используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.creating_test_question_answer))
async def handle_unexpected_test_question_answer_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе ответа на вопрос"""
    await message.answer(
        "❓ <b>Некорректный ответ</b>\n\n"
        "Пожалуйста, введи корректный правильный ответ на вопрос.\n\n"
        "Требования:\n"
        "• Ответ не может быть пустым\n"
        "• Введи точную фразу, которая будет считаться правильной\n"
        "• Учти, что сравнение будет строгим\n\n"
        "Для отмены создания теста используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.creating_test_question_points))
async def handle_unexpected_test_question_points_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе баллов за вопрос"""
    await message.answer(
        "❓ <b>Некорректное количество баллов</b>\n\n"
        "Пожалуйста, введи корректное число баллов.\n\n"
        "Требования:\n"
        "• Положительное число\n"
        "• Можно использовать дробные числа (например: 1.5)\n"
        "• Число должно быть больше 0\n\n"
        "Примеры: 1, 2, 1.5, 0.5\n\n"
        "Для отмены создания теста используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.creating_test_more_questions))
async def handle_unexpected_test_more_questions_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе добавления дополнительных вопросов"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.creating_test_threshold))
async def handle_unexpected_test_threshold_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе проходного балла"""
    await message.answer(
        "❓ <b>Некорректный проходной балл</b>\n\n"
        "Пожалуйста, введи корректный проходной балл.\n\n"
        "Требования:\n"
        "• Число от 0.5 до максимального балла теста\n"
        "• Можно использовать дробные числа\n"
        "• Число должно быть разумным для прохождения\n\n"
        "Для отмены создания теста используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.adding_session_to_stage))
async def handle_unexpected_session_management_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при управлении сессиями"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.adding_stage_to_trajectory))
async def handle_unexpected_stage_management_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при управлении этапами"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.waiting_for_attestation_selection))
async def handle_unexpected_attestation_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе аттестации"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.waiting_for_attestation_confirmation))
async def handle_unexpected_attestation_confirmation_input(message: Message, state: FSMContext):
    """Fallback для состояния подтверждения аттестации (пункт 49 ТЗ)"""
    await message.answer(
        "⚠️ <b>Пожалуйста, используй кнопки!</b>\n\n"
        "📋 Доступные действия:\n"
        "• ✅Да - подтвердить добавление аттестации\n"
        "• 🚫Отменить - вернуться к выбору аттестации\n\n"
        "❓ Нажмите на соответствующую кнопку ниже.",
        parse_mode="HTML"
    )


@router.message(StateFilter(LearningPathStates.waiting_for_group_selection))
async def handle_unexpected_group_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе группы для траектории"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.waiting_for_final_save_confirmation))
async def handle_unexpected_final_save_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при финальном подтверждении сохранения (пункт 55 ТЗ)"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.waiting_for_trajectory_save_confirmation))
async def handle_unexpected_trajectory_save_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении сохранения траектории"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.waiting_for_trajectory_selection))
async def handle_unexpected_trajectory_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе траектории для редактирования"""
    await send_fallback_message(message, state)
@router.message(StateFilter(LearningPathStates.editing_trajectory))
async def handle_unexpected_trajectory_editing_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании траектории"""
    await send_fallback_message(message, state)
@router.message(StateFilter(AttestationStates.main_menu))
async def handle_unexpected_attestation_main_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в главном меню аттестаций"""
    await send_fallback_message(message, state)
@router.message(StateFilter(AttestationStates.waiting_for_attestation_name))
async def handle_unexpected_attestation_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе названия аттестации"""
    await message.answer(
        "❓ <b>Некорректное название аттестации</b>\n\n"
        "Пожалуйста, введи корректное название для аттестации.\n\n"
        "Примеры хороших названий:\n"
        "• Аттестация Стажеров\n"
        "• Аттестация Специалистов\n"
        "• Финальная Аттестация\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
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
        parse_mode="HTML"
    )


@router.message(StateFilter(AttestationStates.waiting_for_more_questions))
async def handle_unexpected_attestation_more_questions_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении дополнительных вопросов к аттестации"""
    await send_fallback_message(message, state)
@router.message(StateFilter(AttestationStates.waiting_for_passing_score))
async def handle_unexpected_attestation_passing_score_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе проходного балла аттестации"""
    await message.answer(
        "❓ <b>Некорректный проходной балл</b>\n\n"
        "Пожалуйста, введи корректный проходной балл для аттестации.\n\n"
        "Требования:\n"
        "• Число от 0.5 до максимального балла аттестации\n"
        "• Можно использовать дробные числа\n"
        "• Балл должен быть достижимым для стажеров\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML"
    )


@router.message(StateFilter(AttestationStates.waiting_for_attestation_selection))
async def handle_unexpected_attestation_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе аттестации"""
    await send_fallback_message(message, state)
@router.message(StateFilter(AttestationStates.editing_attestation))
async def handle_unexpected_attestation_editing_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании аттестации"""
    await send_fallback_message(message, state)
@router.message(StateFilter(AttestationStates.waiting_for_delete_confirmation))
async def handle_unexpected_attestation_delete_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении удаления аттестации"""
    await send_fallback_message(message, state)
@router.message(StateFilter(BroadcastStates.selecting_test))
async def handle_unexpected_broadcast_test_input(message: Message, state: FSMContext):
    """Обработчик неожиданного ввода при выборе теста для рассылки"""
    await send_fallback_message(message, state)
@router.message(StateFilter(BroadcastStates.selecting_groups))
async def handle_unexpected_broadcast_groups_input(message: Message, state: FSMContext):
    """Обработчик неожиданного ввода при выборе групп для рассылки"""
    await send_fallback_message(message, state)

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ УПРАВЛЕНИЯ КОМПАНИЕЙ
# =================================

@router.message(StateFilter(CompanyManagementStates.waiting_for_company_name_edit))
async def handle_unexpected_company_name_edit_input(message: Message, state: FSMContext):
    """Обработчик неожиданного ввода при редактировании названия компании (для не-текстовых сообщений)"""
    await message.answer(
        "❌ <b>Ожидается текстовое сообщение</b>\n\n"
        "Пожалуйста, введи новое название для компании текстом.\n"
        "Название должно содержать от 3 до 100 символов.",
        parse_mode="HTML"
    )

@router.message(StateFilter(CompanyManagementStates.waiting_for_company_description_edit))
async def handle_unexpected_company_description_edit_input(message: Message, state: FSMContext):
    """Обработчик неожиданного ввода при редактировании описания компании (для не-текстовых сообщений)"""
    await message.answer(
        "❌ <b>Ожидается текстовое сообщение</b>\n\n"
        "Пожалуйста, введи новое описание для компании текстом.\n"
        "Описание не должно превышать 500 символов.",
        parse_mode="HTML"
    )

@router.message(F.text)
async def handle_unexpected_input_with_state(message: Message, state: FSMContext, session: AsyncSession):
    """Универсальный обработчик для неожиданного ввода в любых состояниях"""
    # Проверяем, зарегистрирован ли пользователь
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        # Если пользователь не зарегистрирован, показываем выбор: создать или присоединиться к компании
        from keyboards.keyboards import get_company_selection_keyboard
        await message.answer(
            "Привет! Добро пожаловать в чат-бот.\n\n"
            "🏢 Выбери действие:",
            reply_markup=get_company_selection_keyboard()
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
            reply_markup=get_fallback_keyboard()
        )
        
        log_user_action(
            message.from_user.id, 
            message.from_user.username, 
            "unexpected_input", 
            {"state": current_state, "input": message.text[:100]}
        )
    else:
        # Если пользователь не в состоянии FSM
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
        reply_markup=get_fallback_keyboard()
    )
    
    await callback.answer("👀 Команда не распознана", show_alert=True)
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "unexpected_callback", 
        {"state": current_state, "data": callback.data}
    )


# =================================
# FALLBACK HANDLERS ДЛЯ TASK 7: АТТЕСТАЦИЯ СТАЖЕРОВ
# =================================

@router.message(StateFilter(AttestationAssignmentStates.selecting_manager_for_attestation))
async def handle_unexpected_manager_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе руководителя для аттестации"""
    await send_fallback_message(message, state)


@router.message(StateFilter(AttestationAssignmentStates.confirming_attestation_assignment))
async def handle_unexpected_attestation_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении назначения аттестации"""
    await send_fallback_message(message, state)


# =================================
# FALLBACK HANDLERS ДЛЯ РЕКРУТЕРСКОГО ОТКРЫТИЯ АТТЕСТАЦИИ
# =================================

@router.message(StateFilter(RecruiterAttestationStates.selecting_manager))
async def handle_unexpected_recruiter_manager_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе руководителя рекрутером"""
    await send_fallback_message(message, state)


@router.message(StateFilter(RecruiterAttestationStates.confirming_assignment))
async def handle_unexpected_recruiter_confirmation(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении назначения аттестации рекрутером"""
    await send_fallback_message(message, state)
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
        parse_mode="HTML"
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
        parse_mode="HTML"
    )


@router.message(StateFilter(ManagerAttestationStates.confirming_schedule))
async def handle_unexpected_schedule_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении расписания"""
    await send_fallback_message(message, state)
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
        parse_mode="HTML"
    )


@router.message(StateFilter(ManagerAttestationStates.confirming_result))
async def handle_unexpected_result_confirmation_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении результатов аттестации"""
    await send_fallback_message(message, state)
@router.message(StateFilter(TraineeTrajectoryStates.selecting_stage))
async def handle_unexpected_stage_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе этапа траектории"""
    await send_fallback_message(message, state)
@router.message(StateFilter(TraineeTrajectoryStates.selecting_session))
async def handle_unexpected_session_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе сессии"""
    await send_fallback_message(message, state)
@router.message(StateFilter(TraineeTrajectoryStates.selecting_test))
async def handle_unexpected_test_selection_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе теста"""
    await send_fallback_message(message, state)
@router.message(StateFilter(TraineeTrajectoryStates.viewing_materials))
async def handle_unexpected_materials_viewing_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при просмотре материалов"""
    await send_fallback_message(message, state)
@router.message(StateFilter(TraineeTrajectoryStates.taking_test))
async def handle_unexpected_test_taking_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода во время прохождения теста"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.main_menu))
async def handle_unexpected_kb_main_menu_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в главном меню базы знаний"""
    await send_fallback_message(message, state)
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
            parse_mode="HTML"
        )
    else:
        # Это обрабатывается в основном handler'е
        pass


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
            parse_mode="HTML"
        )
    else:
        # Это обрабатывается в основном handler'е
        pass


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
            parse_mode="HTML"
        )
    else:
        # Это обрабатывается в основном handler'е
        pass


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_description))
async def handle_unexpected_material_description_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении описания материала"""
    if not message.text:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Описание материала должно быть текстом.\n\n"
            "📝 <b>Как правильно:</b>\n"
            "• Введи описание текстом\n"
            "• Или нажми \"⏩Пропустить\" для продолжения без описания\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML"
        )
    else:
        # Это обрабатывается в основном handler'е
        pass


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_photos))
async def handle_unexpected_material_photos_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении фотографий к материалу"""
    if not message.photo and not message.media_group_id:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Ожидаются фотографии для материала.\n\n"
            "🖼️ <b>Как правильно:</b>\n"
            "• Отправь фотографию или несколько фотографий\n"
            "• Или нажми \"⏩Пропустить\" для продолжения без фото\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML"
        )
    else:
        # Это обрабатывается в основном handler'е
        pass


@router.message(StateFilter(KnowledgeBaseStates.folder_created_add_material))
async def handle_unexpected_folder_created_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода после создания папки"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.confirming_material_save))
async def handle_unexpected_material_save_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении сохранения материала"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.viewing_folder))
async def handle_unexpected_folder_viewing_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при просмотре папки"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.viewing_material))
async def handle_unexpected_material_viewing_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при просмотре материала"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.selecting_access_groups))
async def handle_unexpected_access_groups_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе групп доступа"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.waiting_for_new_folder_name))
async def handle_unexpected_new_folder_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при переименовании папки"""
    if not message.text:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Новое название папки должно быть текстом.\n\n"
            "📝 <b>Требования:</b>\n"
            "• Только текст (без файлов, изображений)\n"
            "• От 3 до 50 символов\n"
            "• Уникальное название\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML"
        )
    else:
        # Это обрабатывается в основном handler'е
        pass


@router.message(StateFilter(KnowledgeBaseStates.confirming_folder_rename))
async def handle_unexpected_folder_rename_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении переименования папки"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.confirming_folder_deletion))
async def handle_unexpected_folder_deletion_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении удаления папки"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.confirming_material_deletion))
async def handle_unexpected_material_deletion_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении удаления материала"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.employee_browsing))
async def handle_unexpected_employee_browsing_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при просмотре базы знаний сотрудником"""
    await send_fallback_message(message, state)
@router.message(StateFilter(KnowledgeBaseStates.employee_viewing_folder))
async def handle_unexpected_employee_folder_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при просмотре папки сотрудником"""
    await send_fallback_message(message, state)

@router.message(StateFilter(KnowledgeBaseStates.employee_viewing_material))
async def handle_unexpected_employee_material_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при просмотре материала сотрудником"""
    await send_fallback_message(message, state)


# =================================
# ОБРАБОТЧИКИ ДЛЯ FALLBACK КНОПОК
# =================================

@router.callback_query(F.data == "fallback_back")
async def handle_fallback_back(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад' в fallback сообщениях"""
    # Получаем текущее состояние
    current_state = await state.get_state()
    
    if current_state:
        # Очищаем состояние для возврата к предыдущему действию
        await state.clear()
        await callback.answer("Возврат к предыдущему действию")
    else:
        # Если нет состояния, просто отвечаем
        await callback.answer("Нет предыдущего действия для возврата")
