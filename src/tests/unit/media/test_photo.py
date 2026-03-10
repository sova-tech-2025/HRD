"""Тесты для utils/media/photo.py — резолв источника фото для меню."""

from unittest.mock import MagicMock, patch

from aiogram.types import FSInputFile


class TestResolvePhoto:
    """Тесты для _resolve_photo — приоритет file_id > url > path > None."""

    def test_file_id_has_highest_priority(self):
        from bot.utils.media.photo import _resolve_photo

        result = _resolve_photo(file_id="AgACAgIAA", path="/some/path.jpg", url="https://example.com/img.jpg")
        assert result == "AgACAgIAA"

    def test_url_used_when_no_file_id(self):
        from bot.utils.media.photo import _resolve_photo

        result = _resolve_photo(file_id=None, path="/some/path.jpg", url="https://example.com/img.jpg")
        assert result == "https://example.com/img.jpg"

    def test_path_used_when_no_file_id_and_no_url(self):
        from bot.utils.media.photo import _resolve_photo

        with patch("bot.utils.media.photo.FSInputFile") as mock_fs:
            mock_fs.return_value = MagicMock(spec=FSInputFile)
            result = _resolve_photo(file_id=None, path="/some/path.jpg")
            mock_fs.assert_called_once_with("/some/path.jpg")
            assert result == mock_fs.return_value

    def test_returns_none_when_all_empty(self):
        from bot.utils.media.photo import _resolve_photo

        result = _resolve_photo(file_id=None, path=None, url=None)
        assert result is None

    def test_returns_none_when_empty_strings(self):
        from bot.utils.media.photo import _resolve_photo

        result = _resolve_photo(file_id="", path="", url="")
        assert result is None

    def test_path_error_returns_none(self):
        from bot.utils.media.photo import _resolve_photo

        with patch("bot.utils.media.photo.FSInputFile", side_effect=Exception("file not found")):
            result = _resolve_photo(file_id=None, path="/bad/path.jpg")
            assert result is None


class TestMenuPhotoFunctions:
    """Тесты для get_mentor_menu_photo, get_trainee_menu_photo, get_main_menu_photo."""

    def test_mentor_photo_uses_mentor_config(self):
        from bot.utils.media.photo import get_mentor_menu_photo

        with (
            patch("bot.utils.media.photo.MENTOR_MENU_IMAGE_FILE_ID", "mentor_file_id"),
            patch("bot.utils.media.photo.MENTOR_MENU_IMAGE_PATH", "/mentor.jpg"),
        ):
            assert get_mentor_menu_photo() == "mentor_file_id"

    def test_mentor_photo_falls_back_to_path(self):
        from bot.utils.media.photo import get_mentor_menu_photo

        with (
            patch("bot.utils.media.photo.MENTOR_MENU_IMAGE_FILE_ID", ""),
            patch("bot.utils.media.photo.MENTOR_MENU_IMAGE_PATH", "/mentor.jpg"),
            patch("bot.utils.media.photo.FSInputFile") as mock_fs,
        ):
            mock_fs.return_value = MagicMock(spec=FSInputFile)
            result = get_mentor_menu_photo()
            mock_fs.assert_called_once_with("/mentor.jpg")

    def test_mentor_photo_returns_none_when_not_configured(self):
        from bot.utils.media.photo import get_mentor_menu_photo

        with (
            patch("bot.utils.media.photo.MENTOR_MENU_IMAGE_FILE_ID", ""),
            patch("bot.utils.media.photo.MENTOR_MENU_IMAGE_PATH", ""),
        ):
            assert get_mentor_menu_photo() is None

    def test_trainee_photo_uses_trainee_config(self):
        from bot.utils.media.photo import get_trainee_menu_photo

        with (
            patch("bot.utils.media.photo.TRAINEE_MENU_IMAGE_FILE_ID", "trainee_file_id"),
            patch("bot.utils.media.photo.TRAINEE_MENU_IMAGE_PATH", "/trainee.jpg"),
        ):
            assert get_trainee_menu_photo() == "trainee_file_id"

    def test_trainee_photo_returns_none_when_not_configured(self):
        from bot.utils.media.photo import get_trainee_menu_photo

        with (
            patch("bot.utils.media.photo.TRAINEE_MENU_IMAGE_FILE_ID", ""),
            patch("bot.utils.media.photo.TRAINEE_MENU_IMAGE_PATH", ""),
        ):
            assert get_trainee_menu_photo() is None

    def test_main_menu_photo_uses_file_id(self):
        from bot.utils.media.photo import get_main_menu_photo

        with (
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_FILE_ID", "main_file_id"),
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_PATH", ""),
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_URL", ""),
        ):
            assert get_main_menu_photo() == "main_file_id"

    def test_main_menu_photo_falls_back_to_url(self):
        from bot.utils.media.photo import get_main_menu_photo

        with (
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_FILE_ID", ""),
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_URL", "https://example.com/main.jpg"),
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_PATH", "/main.jpg"),
        ):
            assert get_main_menu_photo() == "https://example.com/main.jpg"

    def test_main_menu_photo_falls_back_to_path(self):
        from bot.utils.media.photo import get_main_menu_photo

        with (
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_FILE_ID", ""),
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_URL", ""),
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_PATH", "/main.jpg"),
            patch("bot.utils.media.photo.FSInputFile") as mock_fs,
        ):
            mock_fs.return_value = MagicMock(spec=FSInputFile)
            result = get_main_menu_photo()
            mock_fs.assert_called_once_with("/main.jpg")

    def test_main_menu_photo_returns_none_when_not_configured(self):
        from bot.utils.media.photo import get_main_menu_photo

        with (
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_FILE_ID", ""),
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_URL", ""),
            patch("bot.utils.media.photo.MAIN_MENU_IMAGE_PATH", ""),
        ):
            assert get_main_menu_photo() is None
