from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from states.filters import POINTS_FILTER
from states.states import TestCreationStates, TestTakingStates
from utils.messages.fallback import send_fallback_message

router = Router()


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
