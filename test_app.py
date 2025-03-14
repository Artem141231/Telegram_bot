import unittest
import datetime
import asyncio
import bcrypt
from mock import MagicMock, patch
from app.handlers import verify_password_async
from database.requests import update_last_notification_sent_interval


class TestSecurityFunctions(unittest.TestCase):
    def test_verify_password_correct(self):
        """Проверяет, что функция verify_password возвращает True для корректного пароля."""
        password = "pass1"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.assertTrue(verify_password_async("pass1", hashed))

    def test_verify_password_incorrect(self):
        """Проверяет, что функция verify_password возвращает False для неверного пароля."""
        password = "pass1"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.assertFalse(verify_password_async("wrongpass", hashed))

    def test_callback_data_parsing(self):
        """Проверяет корректность разбора callback_data с датой и временем."""
        # Пример callback_data, где формат даты и времени: "DD-MM-YYYY HH:MM"
        callback_data = "confirm_supervisor:2007:3:13-12-2027 15:30"
        # Используем maxsplit=3, чтобы гарантировать, что строка разбивается на 4 части
        parts = callback_data.split(":", 3)
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "confirm_supervisor")
        self.assertEqual(parts[1], "2007")
        self.assertEqual(parts[2], "3")
        self.assertEqual(parts[3], "13-12-2027 15:30")

    def test_notification_message_formatting(self):
        """Проверяет форматирование строки уведомления для редактирования задания."""
        # Симулируем данные для задания
        supervisor_name = "Ivanov Ivan Ivanovich"
        supervisor_job = "Director"
        task_text = "Update client database"
        start_of_term = datetime.datetime(2025, 3, 10, 12, 0)
        current_deadline = datetime.datetime(2025, 3, 11, 12, 0)
        requested_deadline = datetime.datetime(2025, 3, 11, 15, 30)

        message_text = (
            f"👤 Подчинённый: TestSubordinate (TestJob)\n"
            f"📌 Задание: {task_text}\n"
            f"📅 Дата выдачи: {start_of_term.strftime('%d-%m-%Y %H:%M')}\n"
            f"⏳ Текущий дедлайн: {current_deadline.strftime('%d-%m-%Y %H:%M')}\n"
            f"⏳ Запрошенный новый дедлайн: {requested_deadline.strftime('%d-%m-%Y %H:%M')}\n\n"
            "Пожалуйста, подтвердите запрос."
        )

        self.assertIn("Update client database", message_text)
        self.assertIn("10-03-2025 12:00", message_text)
        self.assertIn("11-03-2025 12:00", message_text)
        self.assertIn("11-03-2025 15:30", message_text)

    def test_update_last_notification_sent_interval(self):
        """Проверяет, что функция update_last_notification_sent_interval правильно вызывает EXEC-хранимую процедуру."""
        # Импортируем функцию, которую будем тестировать
        from database.requests import update_last_notification_sent_interval

        # Создаем фиктивный курсор и соединение
        dummy_cursor = MagicMock()
        dummy_conn = MagicMock()
        dummy_conn.cursor.return_value = dummy_cursor

        # Патчим функцию get_connection, чтобы она возвращала наше фиктивное соединение
        with patch("database.requests.get_connection", return_value=dummy_conn):
            now = datetime.datetime.now()
            update_last_notification_sent_interval(2007, "24", now)
            dummy_cursor.execute.assert_called_with(
                "EXEC update_last_notification_sent_interval ?, ?, ?", 2007, "24", now
            )
            dummy_conn.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
