from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Table, Text, Float, Index, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()


user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)

user_groups = Table(
    'user_groups',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id'), primary_key=True)
)

# Ассоциативная таблица для связи many-to-many между пользователями и объектами
user_objects = Table(
    'user_objects',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('object_id', Integer, ForeignKey('objects.id'), primary_key=True)
)

class User(Base):
    """Модель пользователя"""

    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)
    registration_date = Column(DateTime, default=datetime.now)
    role_assigned_date = Column(DateTime, default=datetime.now)  # Дата назначения текущей роли
    is_active = Column(Boolean, default=True)
    is_activated = Column(Boolean, default=False)  # Активация рекрутером
    internship_object_id = Column(Integer, ForeignKey('objects.id'), nullable=True)  # Объект стажировки
    work_object_id = Column(Integer, ForeignKey('objects.id'), nullable=True)  # Объект работы
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания пользователя
    
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    groups = relationship("Group", secondary=user_groups, back_populates="users")
    objects = relationship("Object", secondary=user_objects, back_populates="users")
    company = relationship("Company", foreign_keys=[company_id], back_populates="users")
    
    # Связи для объектов стажировки и работы
    internship_object = relationship("Object", foreign_keys=[internship_object_id])
    work_object = relationship("Object", foreign_keys=[work_object_id])
    
    # Связи для наставничества
    mentoring_relationships = relationship("Mentorship", foreign_keys="Mentorship.mentor_id", back_populates="mentor")
    trainee_relationships = relationship("Mentorship", foreign_keys="Mentorship.trainee_id", back_populates="trainee")

    # Связи для траекторий обучения
    assigned_learning_paths = relationship("TraineeLearningPath", foreign_keys="TraineeLearningPath.trainee_id", back_populates="trainee")

    # Связи для тестов
    created_tests = relationship("Test", back_populates="creator")
    test_results = relationship("TestResult", back_populates="user")
    
    __table_args__ = (
        Index('idx_user_tg_id_active', 'tg_id', 'is_active'),
        Index('idx_user_is_active', 'is_active'),
        Index('idx_user_phone', 'phone_number'),
        Index('idx_user_company', 'company_id'),
        Index('idx_user_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, tg_id={self.tg_id}, username={self.username})>"

class Role(Base):
    """Модель роли"""

    __tablename__ = 'roles'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")
    
    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id'), primary_key=True)
)

class Permission(Base):
    """Модель прав доступа"""
    
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission(id={self.id}, name={self.name})>"


class Group(Base):
    """Модель групп пользователей"""
    
    __tablename__ = 'groups'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Было: nullable=False
    created_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания группы
    
    # Связи
    users = relationship("User", secondary=user_groups, back_populates="groups")
    created_by = relationship("User", foreign_keys=[created_by_id])
    company = relationship("Company")
    
    __table_args__ = (
        Index('idx_group_is_active', 'is_active'),
        Index('idx_group_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Group(id={self.id}, name={self.name})>"


class Object(Base):
    """Модель объектов"""
    
    __tablename__ = 'objects'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Было: nullable=False
    created_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания объекта
    
    # Связи
    users = relationship("User", secondary=user_objects, back_populates="objects")
    created_by = relationship("User", foreign_keys=[created_by_id])
    company = relationship("Company")
    
    __table_args__ = (
        Index('idx_object_is_active', 'is_active'),
        Index('idx_object_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Object(id={self.id}, name={self.name})>"


# Ассоциативная таблица для связи many-to-many между сессиями и тестами
session_tests = Table(
    'session_tests',
    Base.metadata,
    Column('session_id', Integer, ForeignKey('learning_sessions.id'), primary_key=True),
    Column('test_id', Integer, ForeignKey('tests.id'), primary_key=True),
    Column('order_number', Integer, nullable=False, default=1)  # Порядок теста в сессии
)


class InternshipStage(Base):
    """Модель этапов стажировки"""
    
    __tablename__ = 'internship_stages'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order_number = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now)
    
    # Связи
    tests = relationship("Test", back_populates="stage")
    
    def __repr__(self):
        return f"<InternshipStage(id={self.id}, name={self.name}, order={self.order_number})>"


class Test(Base):
    """Модель тестов"""
    
    __tablename__ = 'tests'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    threshold_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False, default=0)
    material_link = Column(String, nullable=True)
    material_file_path = Column(String, nullable=True)
    material_type = Column(String, nullable=True)  # 'photo' или 'document'
    stage_id = Column(Integer, ForeignKey('internship_stages.id'), nullable=True)
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Было: nullable=False
    created_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания теста
    
    # Расширенные настройки
    shuffle_questions = Column(Boolean, default=False)
    max_attempts = Column(Integer, default=0) # 0 - бесконечно
    
    # Связи
    stage = relationship("InternshipStage", back_populates="tests")
    creator = relationship("User", back_populates="created_tests")
    questions = relationship("TestQuestion", back_populates="test", cascade="all, delete-orphan")
    results = relationship("TestResult", back_populates="test")
    sessions = relationship("LearningSession", secondary=session_tests, back_populates="tests")  # Связь с сессиями траекторий
    company = relationship("Company")
    
    __table_args__ = (
        Index('idx_test_is_active', 'is_active'),
        Index('idx_test_creator', 'creator_id'),
        Index('idx_test_stage', 'stage_id'),
        Index('idx_test_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Test(id={self.id}, name={self.name}, threshold={self.threshold_score})>"


class TestQuestion(Base):
    """Модель вопросов теста"""
    
    __tablename__ = 'test_questions'
    
    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_type = Column(String, nullable=False, default='text')  # text, single_choice, multiple_choice, yes_no, number
    question_text = Column(Text, nullable=False)
    options = Column(JSONB, nullable=True)
    correct_answer = Column(String, nullable=False) # Для multi_choice - JSON-строка
    points = Column(Float, nullable=False, default=1)
    penalty_points = Column(Float, nullable=False, default=0) # Штраф за неправильный ответ
    created_date = Column(DateTime, default=datetime.now)
    
    # Связи
    test = relationship("Test", back_populates="questions")
    
    def __repr__(self):
        return f"<TestQuestion(id={self.id}, test_id={self.test_id}, number={self.question_number})>"


class TestResult(Base):
    """Модель результатов прохождения тестов"""
    
    __tablename__ = 'test_results'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    score = Column(Float, nullable=False)
    max_possible_score = Column(Float, nullable=False)
    is_passed = Column(Boolean, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    answers = Column(Text, nullable=True)  # JSON строка с ответами пользователя
    answers_details = Column(JSONB, nullable=True) # Детальная информация по ответам (время, правильность)
    wrong_answers = Column(JSONB, nullable=True) # Сохранение неверных ответов
    created_date = Column(DateTime, default=datetime.now)
    
    # Связи
    user = relationship("User", back_populates="test_results")
    test = relationship("Test", back_populates="results")
    
    __table_args__ = (
        Index('idx_testresult_user', 'user_id'),
        Index('idx_testresult_test', 'test_id'),
        Index('idx_testresult_user_test', 'user_id', 'test_id'),
    )
    
    def __repr__(self):
        return f"<TestResult(id={self.id}, user_id={self.user_id}, test_id={self.test_id}, score={self.score})>"


class Mentorship(Base):
    """Модель наставничества (связь стажер-наставник)"""
    
    __tablename__ = 'mentorships'
    
    id = Column(Integer, primary_key=True)
    mentor_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    trainee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Кто назначил (рекрутер)
    assigned_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания наставничества
    
    # Связи
    mentor = relationship("User", foreign_keys=[mentor_id], back_populates="mentoring_relationships")
    trainee = relationship("User", foreign_keys=[trainee_id], back_populates="trainee_relationships")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    company = relationship("Company")

    __table_args__ = (
        Index('idx_mentorship_mentor_active', 'mentor_id', 'is_active'),
        Index('idx_mentorship_trainee_active', 'trainee_id', 'is_active'),
        Index('idx_mentorship_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Mentorship(id={self.id}, mentor_id={self.mentor_id}, trainee_id={self.trainee_id})>"


class TraineeTestAccess(Base):
    """Модель доступа стажеров к тестам"""
    
    __tablename__ = 'trainee_test_access'
    
    id = Column(Integer, primary_key=True)
    trainee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    granted_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Наставник, который открыл доступ
    granted_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания доступа
    
    # Связи
    trainee = relationship("User", foreign_keys=[trainee_id])
    test = relationship("Test")
    granted_by = relationship("User", foreign_keys=[granted_by_id])
    company = relationship("Company")
    
    __table_args__ = (
        Index('idx_trainee_test_access_trainee', 'trainee_id'),
        Index('idx_trainee_test_access_test', 'test_id'),
        Index('idx_trainee_test_access_active', 'is_active'),
        Index('idx_trainee_test_access_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<TraineeTestAccess(id={self.id}, trainee_id={self.trainee_id}, test_id={self.test_id})>"


class LearningPath(Base):
    """Модель траектории обучения"""
    
    __tablename__ = 'learning_paths'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название траектории (например "Разработчик")
    description = Column(Text, nullable=True)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=False)  # Группа, для которой предназначена
    attestation_id = Column(Integer, ForeignKey('attestations.id'), nullable=True)  # Аттестация траектории
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Рекрутер-создатель, было: nullable=False
    created_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания траектории
    
    # Связи
    group = relationship("Group")
    attestation = relationship("Attestation", back_populates="learning_path")
    created_by = relationship("User")
    stages = relationship("LearningStage", back_populates="learning_path", cascade="all, delete-orphan", order_by="LearningStage.order_number")
    assigned_trainees = relationship("TraineeLearningPath", back_populates="learning_path", cascade="all, delete-orphan")
    company = relationship("Company")
    
    __table_args__ = (
        Index('idx_learning_path_is_active', 'is_active'),
        Index('idx_learning_path_group', 'group_id'),
        Index('idx_learning_path_attestation', 'attestation_id'),
        Index('idx_learning_path_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<LearningPath(id={self.id}, name={self.name}, group_id={self.group_id})>"


class LearningStage(Base):
    """Модель этапа траектории обучения"""
    
    __tablename__ = 'learning_stages'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название этапа (например "День 1 теория")
    description = Column(Text, nullable=True)
    learning_path_id = Column(Integer, ForeignKey('learning_paths.id'), nullable=False)
    order_number = Column(Integer, nullable=False)  # Порядок этапа в траектории
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now)
    
    # Связи
    learning_path = relationship("LearningPath", back_populates="stages")
    sessions = relationship("LearningSession", back_populates="stage", cascade="all, delete-orphan", order_by="LearningSession.order_number")
    
    def __repr__(self):
        return f"<LearningStage(id={self.id}, name={self.name}, order={self.order_number})>"


class LearningSession(Base):
    """Модель сессии обучения в рамках этапа"""
    
    __tablename__ = 'learning_sessions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название сессии (например "Общая информация")
    description = Column(Text, nullable=True)
    stage_id = Column(Integer, ForeignKey('learning_stages.id'), nullable=False)
    order_number = Column(Integer, nullable=False)  # Порядок сессии в этапе
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now)
    
    # Связи
    stage = relationship("LearningStage", back_populates="sessions")
    tests = relationship("Test", secondary=session_tests, back_populates="sessions", order_by=session_tests.c.order_number)
    
    def __repr__(self):
        return f"<LearningSession(id={self.id}, name={self.name}, order={self.order_number})>"


class Attestation(Base):
    """Модель аттестации - опросный тест для руководителя"""
    
    __tablename__ = 'attestations'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название аттестации
    description = Column(Text, nullable=True)
    passing_score = Column(Float, nullable=False)  # Проходной балл
    max_score = Column(Float, nullable=False, default=0)  # Максимальный балл (сумма всех вопросов)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Рекрутер-создатель, было: nullable=False
    created_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания аттестации
    
    # Связи
    created_by = relationship("User")
    questions = relationship("AttestationQuestion", back_populates="attestation", cascade="all, delete-orphan", order_by="AttestationQuestion.question_number")
    learning_path = relationship("LearningPath", back_populates="attestation", uselist=False)
    company = relationship("Company")
    
    __table_args__ = (
        Index('idx_attestation_is_active', 'is_active'),
        Index('idx_attestation_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Attestation(id={self.id}, name={self.name}, passing_score={self.passing_score})>"


class AttestationQuestion(Base):
    """Модель вопроса аттестации"""

    __tablename__ = 'attestation_questions'

    id = Column(Integer, primary_key=True)
    attestation_id = Column(Integer, ForeignKey('attestations.id'), nullable=False)
    question_number = Column(Integer, nullable=False)  # Порядковый номер вопроса
    question_text = Column(Text, nullable=False)  # Текст вопроса с критериями оценки
    max_points = Column(Float, nullable=False)  # Максимальный балл за вопрос
    created_date = Column(DateTime, default=datetime.now)

    # Связи
    attestation = relationship("Attestation", back_populates="questions")

    def __repr__(self):
        return f"<AttestationQuestion(id={self.id}, attestation_id={self.attestation_id}, number={self.question_number})>"


class AttestationResult(Base):
    """Результаты аттестации стажера руководителем"""

    __tablename__ = 'attestation_results'

    id = Column(Integer, primary_key=True)
    trainee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    attestation_id = Column(Integer, ForeignKey('attestations.id'), nullable=False)
    manager_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Руководитель
    total_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    is_passed = Column(Boolean, nullable=False)  # Прошел ли аттестацию по баллам
    manager_decision = Column(Boolean, nullable=True)  # Решение руководителя: переводить ли в сотрудники
    manager_comment = Column(Text, nullable=True)  # Комментарий руководителя
    completed_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)

    # Связи
    trainee = relationship("User", foreign_keys=[trainee_id])
    attestation = relationship("Attestation")
    manager = relationship("User", foreign_keys=[manager_id])

    __table_args__ = (
        Index('idx_attestation_result_trainee', 'trainee_id'),
        Index('idx_attestation_result_attestation', 'attestation_id'),
    )

    def __repr__(self):
        return f"<AttestationResult(id={self.id}, trainee_id={self.trainee_id}, attestation_id={self.attestation_id}, score={self.total_score}/{self.max_score}, passed={self.is_passed}, decision={self.manager_decision})>"


class TraineeManager(Base):
    """Связь стажер-руководитель для аттестации"""

    __tablename__ = 'trainee_managers'

    id = Column(Integer, primary_key=True)
    trainee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    manager_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Руководитель
    assigned_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Наставник, который назначил
    assigned_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)

    # Связи
    trainee = relationship("User", foreign_keys=[trainee_id])
    manager = relationship("User", foreign_keys=[manager_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])

    def __repr__(self):
        return f"<TraineeManager(id={self.id}, trainee_id={self.trainee_id}, manager_id={self.manager_id})>"


class TraineeAttestation(Base):
    """Назначение аттестации стажеру наставником с датой и временем"""

    __tablename__ = 'trainee_attestations'

    id = Column(Integer, primary_key=True)
    trainee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    manager_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Руководитель для аттестации
    attestation_id = Column(Integer, ForeignKey('attestations.id'), nullable=False)  # Какая аттестация
    assigned_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Наставник, который назначил
    assigned_date = Column(DateTime, default=datetime.now)  # Когда назначена
    scheduled_date = Column(String, nullable=True)  # Дата аттестации (строка как в ТЗ "28.08.2025")
    scheduled_time = Column(String, nullable=True)  # Время аттестации (строка как в ТЗ "12:00")
    status = Column(String, nullable=False, default='assigned')  # assigned, in_progress, completed, failed
    is_active = Column(Boolean, default=True)

    # Связи
    trainee = relationship("User", foreign_keys=[trainee_id])
    manager = relationship("User", foreign_keys=[manager_id])
    attestation = relationship("Attestation")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])

    __table_args__ = (
        Index('idx_trainee_attestation_trainee', 'trainee_id'),
        Index('idx_trainee_attestation_manager', 'manager_id'),
        Index('idx_trainee_attestation_attestation', 'attestation_id'),
        Index('idx_trainee_attestation_active', 'is_active'),
        Index('idx_trainee_attestation_trainee_active', 'trainee_id', 'is_active'),
    )

    def __repr__(self):
        return f"<TraineeAttestation(id={self.id}, trainee_id={self.trainee_id}, manager_id={self.manager_id}, attestation_id={self.attestation_id}, status={self.status})>"


class AttestationQuestionResult(Base):
    """Результат ответа на конкретный вопрос аттестации"""

    __tablename__ = 'attestation_question_results'

    id = Column(Integer, primary_key=True)
    attestation_result_id = Column(Integer, ForeignKey('attestation_results.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('attestation_questions.id'), nullable=False)
    points_awarded = Column(Float, nullable=False)  # Баллы, которые поставил руководитель
    max_points = Column(Float, nullable=False)  # Максимальные баллы за вопрос
    created_date = Column(DateTime, default=datetime.now)

    # Связи
    attestation_result = relationship("AttestationResult")
    question = relationship("AttestationQuestion")

    def __repr__(self):
        return f"<AttestationQuestionResult(id={self.id}, question_id={self.question_id}, points={self.points_awarded}/{self.max_points})>"


class TraineeLearningPath(Base):
    """Модель назначения траектории стажеру"""

    __tablename__ = 'trainee_learning_paths'

    id = Column(Integer, primary_key=True)
    trainee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    learning_path_id = Column(Integer, ForeignKey('learning_paths.id'), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Наставник, который назначил
    assigned_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    attestation_completed = Column(Boolean, default=False)  # Прошел ли стажер аттестацию

    # Связи
    trainee = relationship("User", foreign_keys=[trainee_id], back_populates="assigned_learning_paths")
    learning_path = relationship("LearningPath", back_populates="assigned_trainees")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    stage_progress = relationship("TraineeStageProgress", back_populates="trainee_path", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_trainee_learning_path_trainee', 'trainee_id'),
        Index('idx_trainee_learning_path_path', 'learning_path_id'),
        Index('idx_trainee_learning_path_active', 'is_active'),
    )

    def __repr__(self):
        return f"<TraineeLearningPath(id={self.id}, trainee_id={self.trainee_id}, learning_path_id={self.learning_path_id})>"


class TraineeStageProgress(Base):
    """Модель прогресса стажера по этапам траектории"""

    __tablename__ = 'trainee_stage_progress'

    id = Column(Integer, primary_key=True)
    trainee_path_id = Column(Integer, ForeignKey('trainee_learning_paths.id'), nullable=False)
    stage_id = Column(Integer, ForeignKey('learning_stages.id'), nullable=False)
    is_opened = Column(Boolean, default=False)  # Открыт ли этап стажеру
    is_completed = Column(Boolean, default=False)  # Пройден ли этап полностью
    opened_date = Column(DateTime, nullable=True)  # Когда открыт
    completed_date = Column(DateTime, nullable=True)  # Когда пройден

    # Связи
    trainee_path = relationship("TraineeLearningPath", back_populates="stage_progress")
    stage = relationship("LearningStage")
    session_progress = relationship("TraineeSessionProgress", back_populates="stage_progress", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TraineeStageProgress(id={self.id}, stage_id={self.stage_id}, is_opened={self.is_opened}, is_completed={self.is_completed})>"


class TraineeSessionProgress(Base):
    """Модель прогресса стажера по сессиям этапа"""

    __tablename__ = 'trainee_session_progress'

    id = Column(Integer, primary_key=True)
    stage_progress_id = Column(Integer, ForeignKey('trainee_stage_progress.id'), nullable=False)
    session_id = Column(Integer, ForeignKey('learning_sessions.id'), nullable=False)
    is_opened = Column(Boolean, default=False)  # Доступна ли сессия
    is_completed = Column(Boolean, default=False)  # Пройдена ли сессия
    opened_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)

    # Связи
    stage_progress = relationship("TraineeStageProgress", back_populates="session_progress")
    session = relationship("LearningSession")

    def __repr__(self):
        return f"<TraineeSessionProgress(id={self.id}, session_id={self.session_id}, is_opened={self.is_opened}, is_completed={self.is_completed})>"


# =====================================================================
# МОДЕЛИ ДЛЯ БАЗЫ ЗНАНИЙ (Task 9)
# =====================================================================

# Ассоциативная таблица для ограничения доступа групп к папкам базы знаний
folder_group_access = Table(
    'folder_group_access',
    Base.metadata,
    Column('folder_id', Integer, ForeignKey('knowledge_folders.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id'), primary_key=True)
)


class KnowledgeFolder(Base):
    """Модель папки базы знаний"""
    
    __tablename__ = 'knowledge_folders'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название папки
    description = Column(Text, nullable=True)  # Описание папки
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Рекрутер-создатель, было: nullable=False
    created_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True, index=True)  # Компания папки
    
    # Связи
    created_by = relationship("User", foreign_keys=[created_by_id])
    materials = relationship("KnowledgeMaterial", back_populates="folder", cascade="all, delete-orphan", order_by="KnowledgeMaterial.order_number")
    accessible_groups = relationship("Group", secondary=folder_group_access)  # Группы с доступом к папке
    company = relationship("Company")
    
    __table_args__ = (
        Index('idx_knowledge_folder_is_active', 'is_active'),
        Index('idx_knowledge_folder_company_active', 'company_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<KnowledgeFolder(id={self.id}, name={self.name})>"


class KnowledgeMaterial(Base):
    """Модель материала в папке базы знаний"""

    __tablename__ = 'knowledge_materials'

    id = Column(Integer, primary_key=True)
    folder_id = Column(Integer, ForeignKey('knowledge_folders.id'), nullable=False)
    name = Column(String, nullable=False)  # Название материала
    description = Column(Text, nullable=True)  # Описание материала для пользователя
    material_type = Column(String, nullable=False, default='link')  # 'pdf' or 'link'
    content = Column(String, nullable=False)  # Путь к файлу или URL ссылки
    photos = Column(JSONB, nullable=True)  # Список file_id фотографий (опционально)
    order_number = Column(Integer, nullable=False, default=1)  # Порядок материала в папке
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Рекрутер-создатель, было: nullable=False
    created_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)

    # Связи
    folder = relationship("KnowledgeFolder", back_populates="materials")
    created_by = relationship("User", foreign_keys=[created_by_id])
    
    __table_args__ = (
        Index('idx_knowledge_material_folder', 'folder_id'),
        Index('idx_knowledge_material_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<KnowledgeMaterial(id={self.id}, name={self.name}, type={self.material_type})>"


# =====================================================================
# МОДЕЛЬ ДЛЯ УПРАВЛЕНИЯ КОМПАНИЯМИ И ПОДПИСКАМИ
# =====================================================================

class Company(Base):
    """Модель компании с управлением подписками"""
    
    __tablename__ = 'companies'
    
    # Основные поля
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)  # max 500 символов (валидация на уровне приложения)
    invite_code = Column(String(50), unique=True, nullable=False, index=True)
    
    # Подписка
    subscribe = Column(Boolean, default=True, nullable=False, index=True)
    start_date = Column(DateTime, nullable=False, default=datetime.now)
    finish_date = Column(DateTime, nullable=False)  # Дата окончания подписки
    trial = Column(Boolean, default=True, nullable=False)
    
    # Пользователи
    members = Column(Integer, default=1, nullable=False)  # Текущее количество
    members_limit = Column(Integer, default=15, nullable=False)  # Максимальное количество
    
    # Метаданные
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Первый пользователь (Рекрутер)
    created_date = Column(DateTime, default=datetime.now, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Связи (будут определены после добавления company_id в User)
    created_by = relationship("User", foreign_keys=[created_by_id], post_update=True)
    users = relationship("User", foreign_keys="User.company_id", back_populates="company")
    
    # Индексы и ограничения
    __table_args__ = (
        Index('idx_company_subscribe_active', 'subscribe', 'is_active'),
        Index('idx_company_finish_date', 'finish_date'),
        Index('idx_company_invite_code', 'invite_code'),
        CheckConstraint('members_limit >= members', name='chk_members_limit'),
        CheckConstraint('finish_date >= start_date', name='chk_finish_date'),
        CheckConstraint('NOT (subscribe = FALSE AND trial = TRUE)', name='chk_subscribe_trial'),
    )
    
    def __repr__(self):
        return f"<Company(id={self.id}, name={self.name}, subscribe={self.subscribe}, members={self.members}/{self.members_limit})>" 