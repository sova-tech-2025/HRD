"""Утилиты для форматирования информации о траекториях обучения в редакторе"""

from typing import Optional, List
from database.models import LearningPath, LearningStage, LearningSession, Test, Group, Attestation


def format_trajectory_for_editor(learning_path: LearningPath) -> str:
    """
    Форматирование основной информации о траектории для редактора
    
    Args:
        learning_path: Объект траектории обучения
        
    Returns:
        Отформатированная строка с информацией о траектории
    """
    group_name = learning_path.group.name if learning_path.group else "Не указана"
    attestation_name = learning_path.attestation.name if learning_path.attestation else "Не назначена"
    
    text = (
        f"🗺️ <b>РЕДАКТОР ТРАЕКТОРИЙ</b> 🗺️\n\n"
        f"📝 <b>Название:</b> {learning_path.name}\n"
        f"🗂️ <b>Группа:</b> {group_name}\n"
        f"🔍 <b>Аттестация:</b> {attestation_name}\n"
    )
    
    return text


def format_trajectory_structure(learning_path: LearningPath, show_header: bool = True, 
                                editing_stage_id: Optional[int] = None, 
                                editing_session_id: Optional[int] = None) -> str:
    """
    Форматирование полной структуры траектории (этапы → сессии → тесты)
    
    Args:
        learning_path: Объект траектории обучения
        show_header: Показывать ли заголовок "РЕДАКТИРОВАНИЕ" и название траектории
        editing_stage_id: ID этапа, который редактируется (будет отмечен ✏️ вместо 🟢)
        editing_session_id: ID сессии, которая редактируется (будет отмечена ✏️ вместо 🟢)
        
    Returns:
        Отформатированная строка со структурой траектории
    """
    text = ""
    
    if show_header:
        text += (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            f"✏️<b>РЕДАКТИРОВАНИЕ</b>\n\n"
            f"🟢<b>Название траектории:</b> {learning_path.name}\n\n"
        )
    
    structure = ""
    
    if not learning_path.stages:
        structure = "📋 <b>Этапы не добавлены</b>\n"
    else:
        for stage in sorted(learning_path.stages, key=lambda s: s.order_number):
            # Определяем иконку для этапа
            stage_icon = "✏️" if (editing_stage_id and stage.id == editing_stage_id) else "🟢"
            structure += f"{stage_icon}<b>Этап {stage.order_number}:</b> {stage.name}\n"
            
            if stage.sessions:
                for session in sorted(stage.sessions, key=lambda s: s.order_number):
                    # Определяем иконку для сессии
                    session_icon = "✏️" if (editing_session_id and session.id == editing_session_id) else "🟢"
                    structure += f"{session_icon}<b>Сессия {session.order_number}:</b> {session.name}\n"
                    
                    # Получаем тесты сессии
                    if hasattr(session, 'tests') and session.tests:
                        tests_list = list(session.tests)
                        for i, test in enumerate(tests_list, 1):
                            structure += f"🟢<b>Тест {i}:</b> {test.name}\n"
    
    text += structure
    
    # Добавляем аттестацию и группу в конце
    if learning_path.attestation:
        text += f"\n🔍🟢<b>Аттестация:</b> {learning_path.attestation.name}\n"
    else:
        text += f"\n🔍🟢<b>Аттестация:</b> Не назначена\n"
    
    if learning_path.group:
        text += f"🗂️<b>Группа:</b> {learning_path.group.name}\n"
    else:
        text += f"🗂️<b>Группа:</b> Не указана\n"
    
    return text


def format_stage_for_editor(stage: LearningStage) -> str:
    """
    Форматирование информации об этапе для редактора
    
    Args:
        stage: Объект этапа обучения
        
    Returns:
        Отформатированная строка с информацией об этапе
    """
    description = stage.description if stage.description else "<i>Описание не указано</i>"
    
    text = (
        f"🟢 <b>ЭТАП {stage.order_number}</b>\n\n"
        f"📝 <b>Название:</b> {stage.name}\n"
        f"📄 <b>Описание:</b> {description}\n"
    )
    
    return text


def format_session_for_editor(session: LearningSession, tests: Optional[List[Test]] = None) -> str:
    """
    Форматирование информации о сессии для редактора
    
    Args:
        session: Объект сессии обучения
        tests: Список тестов сессии (опционально, если не передан - пытаемся получить из связи)
        
    Returns:
        Отформатированная строка с информацией о сессии
    """
    description = session.description if session.description else "<i>Описание не указано</i>"
    
    # Получаем список тестов сессии
    tests_info = ""
    if tests is not None:
        # Используем переданный список тестов
        session_tests = tests
    elif hasattr(session, 'tests') and session.tests:
        # Пытаемся получить из связи (если сессия загружена с tests)
        session_tests = list(session.tests)
    else:
        session_tests = []
    
    if session_tests:
        for i, test in enumerate(session_tests, 1):
            tests_info += f"   📝 <b>{i}.</b> {test.name}\n"
    else:
        tests_info = "   📋 <i>Тесты не добавлены</i>\n"
    
    text = (
        f"🟡 <b>СЕССИЯ {session.order_number}</b>\n\n"
        f"📝 <b>Название:</b> {session.name}\n"
        f"📄 <b>Описание:</b> {description}\n\n"
        f"📋 <b>Тесты в сессии:</b>\n{tests_info}"
    )
    
    return text


def format_stage_editor_view(learning_path: LearningPath, stage: LearningStage) -> str:
    """
    Форматирование экрана редактирования этапа с фокусом на этапе и его сессиях
    
    Args:
        learning_path: Объект траектории обучения
        stage: Объект этапа обучения
        
    Returns:
        Отформатированная строка для экрана редактирования этапа
    """
    text = (
        f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
        f"✏️<b>РЕДАКТИРОВАНИЕ</b>\n"
        f"➡️<b>ЭТАП ТРАЕКТОРИИ</b>\n\n"
        f"🟢<b>Название траектории:</b> {learning_path.name}\n\n"
    )
    
    # Показываем всю структуру траектории, но редактируемый этап отмечаем ✏️
    if not learning_path.stages:
        text += "📋 <b>Этапы не добавлены</b>\n"
    else:
        stages_list = sorted(learning_path.stages, key=lambda x: x.order_number)
        for s in stages_list:
            stage_icon = "✏️" if s.id == stage.id else "🟢"
            text += f"{stage_icon}<b>Этап {s.order_number}:</b> {s.name}\n"
            
            if s.sessions:
                for session in sorted(s.sessions, key=lambda x: x.order_number):
                    text += f"🟢<b>Сессия {session.order_number}:</b> {session.name}\n"
                    
                    if hasattr(session, 'tests') and session.tests:
                        tests_list = list(session.tests)
                        for i, test in enumerate(tests_list, 1):
                            text += f"🟢<b>Тест {i}:</b> {test.name}\n"
    
    # Добавляем аттестацию и группу в конце
    if learning_path.attestation:
        text += f"\n🔍🟢<b>Аттестация:</b> {learning_path.attestation.name}\n"
    else:
        text += f"\n🔍🟢<b>Аттестация:</b> Не назначена\n"
    
    if learning_path.group:
        text += f"🗂️<b>Группа:</b> {learning_path.group.name}\n"
    else:
        text += f"🗂️<b>Группа:</b> Не указана\n"
    
    return text


def format_session_tests_editor_view(learning_path: LearningPath, stage: LearningStage, 
                                     session: LearningSession, tests: Optional[List[Test]] = None) -> str:
    """
    Форматирование экрана управления тестами в сессии с фокусом на сессии и её тестах
    
    Args:
        learning_path: Объект траектории обучения
        stage: Объект этапа обучения
        session: Объект сессии обучения
        tests: Список тестов сессии (опционально, если не передан - пытаемся получить из связи)
        
    Returns:
        Отформатированная строка для экрана управления тестами в сессии
    """
    text = (
        f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
        f"✏️<b>РЕДАКТИРОВАНИЕ</b>\n"
        f"➡️<b>ЭТАП ТРАЕКТОРИИ</b>\n\n"
        f"🟢<b>Название траектории:</b> {learning_path.name}\n\n"
    )
    
    # Показываем всю структуру траектории, но редактируемую сессию отмечаем ✏️
    if not learning_path.stages:
        text += "📋 <b>Этапы не добавлены</b>\n"
    else:
        for s in sorted(learning_path.stages, key=lambda x: x.order_number):
            text += f"🟢<b>Этап {s.order_number}:</b> {s.name}\n"
            
            if s.sessions:
                for sess in sorted(s.sessions, key=lambda x: x.order_number):
                    session_icon = "✏️" if sess.id == session.id else "🟢"
                    text += f"{session_icon}<b>Сессия {sess.order_number}:</b> {sess.name}\n"
                    
                    # Для редактируемой сессии используем переданные тесты, для остальных - из связи
                    if sess.id == session.id:
                        session_tests = tests if tests is not None else (list(sess.tests) if hasattr(sess, 'tests') and sess.tests else [])
                    else:
                        session_tests = list(sess.tests) if hasattr(sess, 'tests') and sess.tests else []
                    
                    if session_tests:
                        for i, test in enumerate(session_tests, 1):
                            text += f"🟢<b>Тест {i}:</b> {test.name}\n"
    
    # Добавляем аттестацию и группу в конце
    if learning_path.attestation:
        text += f"\n🔍🟢<b>Аттестация:</b> {learning_path.attestation.name}\n"
    else:
        text += f"\n🔍🟢<b>Аттестация:</b> Не назначена\n"
    
    if learning_path.group:
        text += f"🗂️<b>Группа:</b> {learning_path.group.name}\n"
    else:
        text += f"🗂️<b>Группа:</b> Не указана\n"
    
    return text


def format_trajectory_structure_with_new_stage(learning_path: LearningPath, new_stage_number: int) -> str:
    """
    Форматирование структуры траектории с новым создаваемым этапом
    
    Args:
        learning_path: Объект траектории обучения
        new_stage_number: Порядковый номер нового этапа
        
    Returns:
        Отформатированная строка со структурой траектории, где новый этап показан как "🟡Этап X: отправь название"
    """
    text = (
        f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
        f"✏️<b>РЕДАКТИРОВАНИЕ</b>\n"
        f"➡️<b>ЭТАП ТРАЕКТОРИИ</b>\n\n"
        f"🟢<b>Название траектории:</b> {learning_path.name}\n\n"
    )
    
    # Показываем существующие этапы
    if learning_path.stages:
        for stage in sorted(learning_path.stages, key=lambda s: s.order_number):
            text += f"🟢<b>Этап {stage.order_number}:</b> {stage.name}\n"
            
            if stage.sessions:
                for session in sorted(stage.sessions, key=lambda s: s.order_number):
                    text += f"🟢<b>Сессия {session.order_number}:</b> {session.name}\n"
                    
                    if hasattr(session, 'tests') and session.tests:
                        tests_list = list(session.tests)
                        for i, test in enumerate(tests_list, 1):
                            text += f"🟢<b>Тест {i}:</b> {test.name}\n"
    
    # Показываем новый создаваемый этап
    text += f"\n🟡<b>Этап {new_stage_number}:</b> отправь название\n"
    
    # Добавляем аттестацию и группу в конце
    if learning_path.attestation:
        text += f"\n🔍🟢<b>Аттестация:</b> {learning_path.attestation.name}\n"
    else:
        text += f"\n🔍🟢<b>Аттестация:</b> Не назначена\n"
    
    if learning_path.group:
        text += f"🗂️<b>Группа:</b> {learning_path.group.name}\n"
    else:
        text += f"🗂️<b>Группа:</b> Не указана\n"
    
    return text

