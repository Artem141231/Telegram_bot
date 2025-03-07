from bot import bot

from database.requests import fetch_telegram_id_by_user_id, fetch_subordinate_info,fetch_task_details
import app.keydoards as kb
import datetime


async def notify_creator_task_completed(creator_user_id: int, task_text: str, subordinate_user_id: int):
    telegram_id = await fetch_telegram_id_by_user_id(creator_user_id)
    if not telegram_id:
        print(f"❌ Ошибка: Telegram ID не найден для UserID {creator_user_id}")
        return

    subordinate_info = await fetch_subordinate_info(subordinate_user_id)
    if not subordinate_info:
        subordinate_text = "неизвестный сотрудник"
    else:
        subordinate_text = f"{subordinate_info['FullName']} ({subordinate_info['JobTitle']})"

    message = (
        f"✅ Ваше задание '{task_text}' было выполнено.\n\n"
        f"👤 Исполнитель: {subordinate_text}"
    )
    await bot.send_message(telegram_id, message)


async def notify_supervisor_of_postponement(supervisor_user_id: int, subordinate_user_id: int, task_id: int,
                                            requested_deadline: datetime.datetime):
    # Получаем реальный Telegram ID руководителя
    telegram_id = await fetch_telegram_id_by_user_id(supervisor_user_id)
    if not telegram_id:
        print(f"❌ Ошибка: Telegram ID не найден для UserID {supervisor_user_id}")
        return

    # Получаем информацию о подчинённом
    subordinate_info = await fetch_subordinate_info(subordinate_user_id)
    if subordinate_info:
        subordinate_name = subordinate_info.get("FullName", f"ID {subordinate_user_id}")
        subordinate_job = subordinate_info.get("JobTitle", "неизвестно")
    else:
        subordinate_name = f"ID {subordinate_user_id}"
        subordinate_job = "неизвестно"

    # Получаем детали задания
    task_details = await fetch_task_details(task_id)
    if not task_details:
        print("❌ Ошибка: не удалось получить детали задания.")
        return

    # Предполагается, что fetch_task_details возвращает кортеж в следующем порядке:
    # (TaskID, CreatorID, Text, StartOfTerm, Deadline)
    task_text = task_details[2]
    start_of_term = task_details[3]
    current_deadline = task_details[4]

    # Формируем сообщение с дополнительной информацией
    message_text = (
        f"Подчинённый: {subordinate_name} ({subordinate_job})\n"
        f"Задание: {task_text}\n"
        f"Дата выдачи: {start_of_term.strftime('%d-%m-%Y %H:%M')}\n"
        f"Текущий дедлайн: {current_deadline.strftime('%d-%m-%Y')}\n"
        f"Запрошенный новый дедлайн: {requested_deadline.strftime('%d-%m-%Y')}\n\n"
        "Пожалуйста, подтвердите запрос."
    )

    # Отправляем сообщение с inline-клавиатурой для подтверждения запроса
    await bot.send_message(
        telegram_id,
        message_text,
        reply_markup=kb.supervisor_postponement_keyboard(task_id, subordinate_user_id, requested_deadline)
    )

