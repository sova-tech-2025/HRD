from aiogram.filters import StateFilter

from states.states import (
    AdminStates,
    AttestationAssignmentStates,
    AttestationStates,
    AuthStates,
    BroadcastStates,
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
