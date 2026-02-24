"""
Тесты для check_test_access: воспроизведение и проверка фикса бага,
при котором check_test_access запрещал легитимный доступ стажерам и сотрудникам.

Баги:
1. Стажер: если TraineeTestAccess существует, но этап закрыт → доступ запрещался
2. Сотрудник: доступ проверялся через роль создателя ("Рекрутер"), а не через TraineeTestAccess

Фикс (коммит f5ed666 / cc499f4):
1. Стажер: TraineeTestAccess существует и активен → сразу return True
2. Сотрудник: проверяем TraineeTestAccess вместо роли создателя
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_role(name: str) -> MagicMock:
    """Создать мок роли с заданным именем."""
    role = MagicMock()
    role.name = name
    return role


def make_execute_result(scalar_value=None, first_value=None):
    """Создать мок результата session.execute()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_value
    result.first.return_value = first_value
    return result


# ==========================================================================
# Дефект 1: Стажер — закрытый этап блокирует доступ к пройденным тестам
# ==========================================================================


class TestTraineeAccessWithTraineeTestAccess:
    """Стажер с активным TraineeTestAccess должен получать доступ
    независимо от состояния этапа (открыт/закрыт)."""

    @pytest.mark.asyncio
    async def test_trainee_access_granted_when_access_record_exists(self):
        """
        Баг: стажер 568 имеет TraineeTestAccess(test_id=16, is_active=True),
        но этап 9 закрыт наставником → check_test_access возвращает False.

        Старый код: access найден → проверяет trajectory → этап закрыт →
        тест в траектории → granted_by_id is None → return False (БАГ).

        Фикс: если TraineeTestAccess существует → сразу return True.
        """
        from database.db import check_test_access

        session = AsyncMock()

        access_mock = MagicMock()
        access_mock.company_id = 1
        access_mock.granted_by_id = None  # НЕ через рассылку → старый код запрещает

        trainee_path_mock = MagicMock()
        trainee_path_mock.id = 100

        # Порядок execute вызовов в СТАРОМ коде:
        # 1. TraineeTestAccess → найден (access_mock)
        # 2. TraineeLearningPath → найден (trainee_path_mock)
        # 3. trajectory test с is_opened=True → не найден (этап закрыт)
        # 4. trajectory test без is_opened → найден (тест в траектории)
        # Старый код: granted_by_id is None → return False
        #
        # В НОВОМ коде используется только вызов 1 → return True
        session.execute = AsyncMock(side_effect=[
            make_execute_result(scalar_value=access_mock),       # TraineeTestAccess
            make_execute_result(scalar_value=trainee_path_mock), # TraineeLearningPath
            make_execute_result(first_value=None),               # trajectory (open stage) → нет
            make_execute_result(first_value=(16,)),              # trajectory (all) → есть
        ])

        with patch('database.db.get_user_roles', return_value=[make_role("Стажер")]):
            result = await check_test_access(session, user_id=568, test_id=16, company_id=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_trainee_access_with_null_company_and_valid_test(self):
        """
        TraineeTestAccess с company_id=NULL (старая запись) —
        доступ разрешён если тест принадлежит компании стажера.
        """
        from database.db import check_test_access

        session = AsyncMock()

        access_mock = MagicMock()
        access_mock.company_id = None  # NULL → нужна проверка через get_test_by_id

        session.execute.return_value = make_execute_result(scalar_value=access_mock)

        test_mock = MagicMock()
        test_mock.company_id = 1

        with (
            patch('database.db.get_user_roles', return_value=[make_role("Стажер")]),
            patch('database.db.get_test_by_id', return_value=test_mock),
        ):
            result = await check_test_access(session, user_id=568, test_id=16, company_id=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_trainee_denied_with_null_company_wrong_test(self):
        """
        TraineeTestAccess с company_id=NULL, но тест НЕ принадлежит компании →
        доступ запрещён (безопасность мультитенантности).
        """
        from database.db import check_test_access

        session = AsyncMock()

        access_mock = MagicMock()
        access_mock.company_id = None

        session.execute.return_value = make_execute_result(scalar_value=access_mock)

        test_mock = MagicMock()
        test_mock.company_id = 999  # другая компания

        with (
            patch('database.db.get_user_roles', return_value=[make_role("Стажер")]),
            patch('database.db.get_test_by_id', return_value=test_mock),
        ):
            result = await check_test_access(session, user_id=568, test_id=16, company_id=1)

        assert result is False


# ==========================================================================
# Дефект 2: Сотрудник — проверка по роли создателя вместо TraineeTestAccess
# ==========================================================================


class TestEmployeeAccess:
    """Сотрудник с активным TraineeTestAccess должен получать доступ
    независимо от роли создателя теста."""

    @pytest.mark.asyncio
    async def test_employee_access_to_non_recruiter_test(self):
        """
        Баг: сотрудник 441 имеет TraineeTestAccess(test_id=12),
        тест создан НЕ рекрутером → check_test_access возвращает False.

        Старый код: get_user_roles(creator) → ["Наставник"] →
        "Рекрутер" not in ["Наставник"] → return False (БАГ).

        Фикс: проверяем TraineeTestAccess вместо роли создателя.
        """
        from database.db import check_test_access

        session = AsyncMock()

        test_mock = MagicMock()
        test_mock.company_id = 1
        test_mock.creator_id = 999  # создатель — наставник, не рекрутер

        access_mock = MagicMock()
        access_mock.company_id = 1
        session.execute.return_value = make_execute_result(scalar_value=access_mock)

        creator_mock = MagicMock()
        creator_mock.id = 999
        creator_mock.company_id = 1

        # get_user_roles вызывается дважды в старом коде:
        # 1. get_user_roles(session, 441) → ["Сотрудник"]
        # 2. get_user_roles(session, 999) → ["Наставник"] (старый код проверял роль создателя)
        # В новом коде вызывается только раз (для определения роли пользователя)
        async def roles_side_effect(session, uid):
            if uid == 441:
                return [make_role("Сотрудник")]
            elif uid == 999:
                return [make_role("Наставник")]  # НЕ Рекрутер → старый код запрещает
            return []

        with (
            patch('database.db.get_user_roles', side_effect=roles_side_effect),
            patch('database.db.get_test_by_id', return_value=test_mock),
            patch('database.db.get_user_by_id', return_value=creator_mock),
        ):
            result = await check_test_access(session, user_id=441, test_id=12, company_id=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_employee_denied_without_access_record(self):
        """Сотрудник без TraineeTestAccess → доступ запрещён."""
        from database.db import check_test_access

        session = AsyncMock()

        test_mock = MagicMock()
        test_mock.company_id = 1

        session.execute.return_value = make_execute_result(scalar_value=None)

        with (
            patch('database.db.get_user_roles', return_value=[make_role("Сотрудник")]),
            patch('database.db.get_test_by_id', return_value=test_mock),
        ):
            result = await check_test_access(session, user_id=441, test_id=99, company_id=1)

        assert result is False

    @pytest.mark.asyncio
    async def test_employee_denied_cross_company_test(self):
        """Сотрудник не может получить доступ к тесту другой компании."""
        from database.db import check_test_access

        session = AsyncMock()

        test_mock = MagicMock()
        test_mock.company_id = 999  # другая компания

        with (
            patch('database.db.get_user_roles', return_value=[make_role("Сотрудник")]),
            patch('database.db.get_test_by_id', return_value=test_mock),
        ):
            result = await check_test_access(session, user_id=441, test_id=12, company_id=1)

        assert result is False

    @pytest.mark.asyncio
    async def test_employee_denied_nonexistent_test(self):
        """Сотрудник не может получить доступ к несуществующему тесту."""
        from database.db import check_test_access

        session = AsyncMock()

        with (
            patch('database.db.get_user_roles', return_value=[make_role("Сотрудник")]),
            patch('database.db.get_test_by_id', return_value=None),
        ):
            result = await check_test_access(session, user_id=441, test_id=999, company_id=1)

        assert result is False


# ==========================================================================
# Стажер: fallback на структуру траектории
# ==========================================================================


class TestTraineeFallbackToTrajectory:
    """Если TraineeTestAccess не найден, стажер может получить доступ
    через открытый этап траектории (fallback)."""

    @pytest.mark.asyncio
    async def test_trainee_access_via_open_stage_fallback(self):
        """
        TraineeTestAccess не найден, но тест в открытом этапе траектории →
        доступ разрешён через fallback.
        """
        from database.db import check_test_access

        session = AsyncMock()

        # Вызов 1: TraineeTestAccess → не найден
        no_access = make_execute_result(scalar_value=None)
        # Вызов 2: TraineeLearningPath → найден
        trainee_path_mock = MagicMock()
        trainee_path_mock.id = 100
        has_path = make_execute_result(scalar_value=trainee_path_mock)
        # Вызов 3: тест в открытом этапе → найден
        has_test = make_execute_result(first_value=(16,))

        session.execute = AsyncMock(side_effect=[no_access, has_path, has_test])

        with patch('database.db.get_user_roles', return_value=[make_role("Стажер")]):
            result = await check_test_access(session, user_id=568, test_id=16, company_id=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_trainee_denied_no_access_and_closed_stage(self):
        """
        TraineeTestAccess не найден, тест НЕ в открытом этапе → доступ запрещён.
        """
        from database.db import check_test_access

        session = AsyncMock()

        no_access = make_execute_result(scalar_value=None)
        trainee_path_mock = MagicMock()
        trainee_path_mock.id = 100
        has_path = make_execute_result(scalar_value=trainee_path_mock)
        no_test = make_execute_result(first_value=None)

        session.execute = AsyncMock(side_effect=[no_access, has_path, no_test])

        with patch('database.db.get_user_roles', return_value=[make_role("Стажер")]):
            result = await check_test_access(session, user_id=568, test_id=16, company_id=1)

        assert result is False

    @pytest.mark.asyncio
    async def test_trainee_denied_no_access_and_no_trajectory(self):
        """
        TraineeTestAccess не найден, стажер не назначен на траекторию → доступ запрещён.
        """
        from database.db import check_test_access

        session = AsyncMock()

        no_access = make_execute_result(scalar_value=None)
        no_path = make_execute_result(scalar_value=None)

        session.execute = AsyncMock(side_effect=[no_access, no_path])

        with patch('database.db.get_user_roles', return_value=[make_role("Стажер")]):
            result = await check_test_access(session, user_id=568, test_id=16, company_id=1)

        assert result is False


# ==========================================================================
# Другие роли (Рекрутер, Руководитель, Наставник) — проверка компании
# ==========================================================================


class TestOtherRolesAccess:
    """Рекрутеры, руководители и наставники получают доступ через проверку компании."""

    @pytest.mark.asyncio
    async def test_recruiter_access_same_company(self):
        """Рекрутер получает доступ к тесту своей компании."""
        from database.db import check_test_access

        session = AsyncMock()

        test_mock = MagicMock()
        test_mock.company_id = 1

        with (
            patch('database.db.get_user_roles', return_value=[make_role("Рекрутер")]),
            patch('database.db.get_test_by_id', return_value=test_mock),
        ):
            result = await check_test_access(session, user_id=100, test_id=1, company_id=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_mentor_denied_cross_company(self):
        """Наставник не может получить доступ к тесту другой компании."""
        from database.db import check_test_access

        session = AsyncMock()

        test_mock = MagicMock()
        test_mock.company_id = 999

        with (
            patch('database.db.get_user_roles', return_value=[make_role("Наставник")]),
            patch('database.db.get_test_by_id', return_value=test_mock),
        ):
            result = await check_test_access(session, user_id=200, test_id=1, company_id=1)

        assert result is False


# ==========================================================================
# Граничные случаи
# ==========================================================================


class TestEdgeCases:
    """Граничные случаи для check_test_access."""

    @pytest.mark.asyncio
    async def test_trainee_denied_when_no_company_id(self):
        """Стажер без company_id → доступ запрещён (безопасность)."""
        from database.db import check_test_access

        session = AsyncMock()

        with (
            patch('database.db.get_user_roles', return_value=[make_role("Стажер")]),
            patch('database.db.get_user_by_id', return_value=MagicMock(company_id=None)),
        ):
            result = await check_test_access(session, user_id=568, test_id=16, company_id=None)

        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        """Исключение в check_test_access → возвращает False (безопасный дефолт)."""
        from database.db import check_test_access

        session = AsyncMock()

        with patch('database.db.get_user_roles', side_effect=Exception("DB error")):
            result = await check_test_access(session, user_id=1, test_id=1, company_id=1)

        assert result is False
