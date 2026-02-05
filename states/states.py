from aiogram.fsm.state import StatesGroup, State

class AuthStates(StatesGroup):
    """Состояния для процесса авторизации"""
    waiting_for_auth = State()
 
class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""
    waiting_for_full_name = State()
    waiting_for_phone = State()
    waiting_for_role = State()
    waiting_for_admin_token = State()
    waiting_for_admin_role_selection = State()

class AdminStates(StatesGroup):
    """Состояния для административной панели"""
    waiting_for_user_selection = State()
    waiting_for_user_action = State()
    waiting_for_role_change = State()
    waiting_for_confirmation = State()

    waiting_for_role_selection = State()
    waiting_for_permission_action = State()
    waiting_for_permission_selection = State()
    waiting_for_permission_confirmation = State()

class TestCreationStates(StatesGroup):
    """Состояния для создания тестов"""
    waiting_for_test_name = State()
    waiting_for_materials = State()
    waiting_for_description = State()
    
    # Цикл добавления вопросов
    waiting_for_question_type = State()
    waiting_for_question_text = State()
    
    # Пошаговое добавление вариантов
    waiting_for_option = State()
    
    waiting_for_answer = State()
    waiting_for_points = State()
    waiting_for_more_questions = State()
    
    # Финальные настройки
    waiting_for_threshold = State()
    waiting_for_stage_selection = State()
    waiting_for_final_confirmation = State()
    
    # Редактирование
    waiting_for_edit_action = State()
    waiting_for_new_test_name = State()
    waiting_for_new_test_description = State()
    waiting_for_new_threshold = State()
    waiting_for_new_stage = State()
    waiting_for_new_attempts = State()
    waiting_for_new_materials = State()
    
    waiting_for_question_selection = State()
    waiting_for_question_action = State()
    waiting_for_question_edit = State()
    waiting_for_answer_edit = State()
    waiting_for_points_edit = State()

class TestTakingStates(StatesGroup):
    """Состояния для прохождения тестов"""
    waiting_for_test_selection = State()
    waiting_for_test_start = State()
    taking_test = State()
    waiting_for_answer = State()
    test_completed = State()

class MentorshipStates(StatesGroup):
    """Состояния для работы с наставничеством"""
    waiting_for_trainee_selection = State()
    waiting_for_mentor_selection = State()
    waiting_for_assignment_confirmation = State()
    waiting_for_trainee_action = State()
    waiting_for_test_assignment = State()
    waiting_for_test_selection_for_trainee = State()
    selecting_trajectory = State()  # Выбор траектории для стажера
    confirming_trajectory_assignment = State()  # Подтверждение назначения траектории
    selecting_manager = State()  # Выбор руководителя для стажера
    confirming_manager_assignment = State()  # Подтверждение назначения руководителя


class ManagerAttestationStates(StatesGroup):
    """Состояния для проведения аттестаций руководителями (Task 7)"""
    waiting_for_date = State()  # Ввод новой даты аттестации
    waiting_for_time = State()  # Ввод нового времени аттестации
    confirming_schedule = State()  # Подтверждение нового расписания
    waiting_for_score = State()  # Ввод балла за вопрос аттестации
    confirming_result = State()  # Подтверждение результатов

class TraineeManagementStates(StatesGroup):
    """Состояния для управления стажерами"""
    waiting_for_trainee_selection = State()
    waiting_for_trainee_action = State()
    waiting_for_test_access_grant = State()

class GroupManagementStates(StatesGroup):
    """Состояния для управления группами пользователей"""
    # Создание группы
    waiting_for_group_name = State()
    
    # Изменение группы
    waiting_for_group_selection = State()
    waiting_for_new_group_name = State()
    waiting_for_rename_confirmation = State()
    
    # Удаление группы
    waiting_for_delete_group_selection = State()
    waiting_for_delete_confirmation = State()


class ObjectManagementStates(StatesGroup):
    """Состояния для управления объектами"""
    # Создание объекта
    waiting_for_object_name = State()
    
    # Изменение объекта
    waiting_for_object_selection = State()
    waiting_for_new_object_name = State()
    waiting_for_object_rename_confirmation = State()
    
    # Удаление объекта
    waiting_for_delete_object_selection = State()
    waiting_for_delete_confirmation = State()


class UserActivationStates(StatesGroup):
    """Состояния для активации новых пользователей рекрутером"""
    # Выбор пользователя для активации
    waiting_for_user_selection = State()
    
    # Поиск пользователей
    waiting_for_search_query = State()
    
    # Workflow назначения параметров
    waiting_for_role_selection = State()
    waiting_for_group_selection = State()
    waiting_for_internship_object_selection = State()
    waiting_for_work_object_selection = State()
    
    # Подтверждение активации
    waiting_for_activation_confirmation = State()


class UserEditStates(StatesGroup):
    """Состояния для редактирования данных пользователей рекрутером"""
    # Фильтрация пользователей
    waiting_for_filter_selection = State()
    waiting_for_user_selection = State()
    viewing_user_info = State()
    
    # Поиск пользователей
    waiting_for_search_query = State()
    
    # Старый способ (для совместимости)
    waiting_for_user_number = State()
    
    # Редактирование различных полей
    waiting_for_new_full_name = State()
    waiting_for_new_phone = State()
    waiting_for_new_role = State()
    waiting_for_new_group = State()
    waiting_for_new_internship_object = State()
    waiting_for_new_work_object = State()
    
    # Подтверждение изменений
    waiting_for_change_confirmation = State()


class LearningPathStates(StatesGroup):
    """Состояния для создания и редактирования траекторий обучения"""
    # Основное меню траекторий
    main_menu = State()
    
    # Создание траектории
    waiting_for_trajectory_name = State()
    waiting_for_stage_name = State()
    waiting_for_session_name = State()
    waiting_for_test_selection = State()
    
    # Создание нового теста в процессе создания траектории
    creating_test_name = State()
    creating_test_materials_choice = State()
    creating_test_materials = State()
    creating_test_description = State()
    creating_test_question_type = State()
    creating_test_question_text = State()
    creating_test_question_options = State()
    creating_test_question_answer = State()
    creating_test_question_points = State()
    creating_test_more_questions = State()
    creating_test_threshold = State()
    
    # Управление этапами и сессиями
    adding_session_to_stage = State()
    adding_stage_to_trajectory = State()
    
    # Финальные шаги траектории
    waiting_for_attestation_selection = State()
    waiting_for_attestation_confirmation = State()  # ПУНКТ 49 ТЗ: подтверждение аттестации
    waiting_for_group_selection = State()
    waiting_for_trajectory_save_confirmation = State()
    waiting_for_final_save_confirmation = State()  # Новое состояние для пункта 55 ТЗ
    
    # Редактирование существующих траекторий
    waiting_for_trajectory_selection = State()
    editing_trajectory = State()
    
    # ===== РЕДАКТОР ТРАЕКТОРИЙ =====
    # Основное меню редактора
    editor_main_menu = State()
    
    # Редактирование основной информации траектории
    editing_trajectory_name = State()
    selecting_group_for_trajectory = State()
    selecting_attestation_for_trajectory = State()
    removing_attestation_confirmation = State()
    
    # Управление этапами в редакторе
    selecting_stage_for_edit = State()
    editing_stage = State()
    editing_stage_name = State()
    creating_stage_in_editor = State()
    creating_stage_name = State()
    creating_stage_description = State()
    deleting_stage_confirmation = State()
    
    # Управление сессиями в редакторе
    selecting_session_for_edit = State()
    editing_session = State()
    editing_session_name = State()
    editing_session_description = State()
    creating_session_in_editor = State()
    creating_session_name = State()
    creating_session_description = State()
    deleting_session_confirmation = State()
    
    # Управление тестами в сессии
    managing_session_tests = State()
    selecting_test_to_add = State()
    removing_test_confirmation = State()
    
    # Удаление траекторий
    trajectory_deletion = State()


class AttestationStates(StatesGroup):
    """Состояния для создания и редактирования аттестаций"""
    # Основное меню аттестаций
    main_menu = State()
    
    # Создание аттестации
    waiting_for_attestation_creation_start = State()  # ПУНКТ 6-7 ТЗ
    waiting_for_attestation_name = State()
    waiting_for_attestation_question = State()
    waiting_for_more_questions = State()
    waiting_for_passing_score = State()
    
    # Редактирование аттестаций
    waiting_for_attestation_selection = State()
    editing_attestation = State()
    
    # Удаление аттестации
    waiting_for_delete_confirmation = State()


class MentorAssignmentStates(StatesGroup):
    """Состояния для назначения наставников стажерам"""
    selecting_trainee = State()  # Выбор стажера
    selecting_mentor = State()   # Выбор наставника
    confirming_assignment = State()  # Подтверждение назначения


class TraineeTrajectoryStates(StatesGroup):
    """Состояния для прохождения траекторий стажерами (Task 6)"""
    selecting_stage = State()     # Выбор этапа траектории
    selecting_session = State()   # Выбор сессии в этапе
    selecting_test = State()      # Выбор теста в сессии
    viewing_materials = State()   # Просмотр материалов теста
    taking_test = State()        # Прохождение теста


class AttestationAssignmentStates(StatesGroup):
    """Состояния для назначения аттестации стажерам наставником (Task 7)"""
    selecting_manager_for_attestation = State()  # Выбор руководителя для аттестации
    confirming_attestation_assignment = State()  # Подтверждение назначения аттестации


class RecruiterAttestationStates(StatesGroup):
    """Состояния для открытия аттестации стажеру рекрутером (без прохождения этапов)"""
    selecting_manager = State()  # Выбор руководителя для аттестации
    confirming_assignment = State()  # Подтверждение назначения аттестации


class BroadcastStates(StatesGroup):
    """Состояния для массовой рассылки тестов по группам (Task 8)"""
    waiting_for_script = State()  # Ввод текста рассылки
    waiting_for_photos = State()  # Загрузка фото
    selecting_material = State()  # Выбор материала из базы знаний
    selecting_test = State()  # Выбор теста для рассылки (опционально)
    selecting_roles = State()  # Выбор ролей для рассылки
    selecting_groups = State()  # Выбор групп для рассылки


class KnowledgeBaseStates(StatesGroup):
    """Состояния для управления базой знаний (Task 9)"""
    # Основное меню базы знаний (рекрутер)
    main_menu = State()
    
    # Создание папки (9-1)
    waiting_for_folder_name = State()
    folder_created_add_material = State()
    
    # Добавление материала в папку
    waiting_for_material_name = State()
    waiting_for_material_content = State()  # файл или ссылка
    waiting_for_material_description = State()
    waiting_for_material_photos = State()  # Необязательные фотографии
    confirming_material_save = State()
    
    # Просмотр папки (9-2)
    viewing_folder = State()
    viewing_material = State()
    
    # Изменение доступа к папке (9-3)
    selecting_access_groups = State()
    
    # Изменение названия папки (9-4)
    waiting_for_new_folder_name = State()
    confirming_folder_rename = State()
    
    # Удаление папки (9-5)
    confirming_folder_deletion = State()
    
    # Удаление материала
    confirming_material_deletion = State()
    
    # Просмотр базы знаний (для сотрудников)
    employee_browsing = State()
    employee_viewing_folder = State()
    employee_viewing_material = State()


class CompanyCreationStates(StatesGroup):
    """Состояния для создания компании"""
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_invite_code = State()
    waiting_for_full_name = State()
    waiting_for_phone = State()


class CompanyJoinStates(StatesGroup):
    """Состояния для присоединения к компании"""
    waiting_for_invite_code = State()
    waiting_for_registration_type = State()  # Выбор типа регистрации (normal/with_code)
    waiting_for_full_name = State()
    waiting_for_phone = State()
    waiting_for_role_selection = State()


class CompanyManagementStates(StatesGroup):
    """Состояния для управления компанией (для рекрутеров)"""
    waiting_for_company_name_edit = State()
    waiting_for_company_description_edit = State()