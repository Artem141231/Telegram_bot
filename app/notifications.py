from bot import bot
import asyncio
from database.requests import fetch_telegram_id_by_user_id, fetch_subordinate_info,fetch_task_details
import app.keydoards as kb
import datetime
from database.requests import (get_tasks_with_deadline_in_range, fetch_update_last_notification_sent_interval,
                               fetch_overdue_tasks, fetch_mark_task_overdue)
from apscheduler.schedulers.asyncio import AsyncIOScheduler


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


    task_text = task_details[2]
    start_of_term = task_details[3]
    current_deadline = task_details[4]

    # Формируем сообщение с дополнительной информацией
    message_text = (
        f"👤 Подчинённый: {subordinate_name} ({subordinate_job})\n"
        f"📌 Задание: {task_text}\n"
        f"📅 Дата выдачи: {start_of_term.strftime('%d-%m-%Y %H:%M')}\n"
        f"⏳ Текущий дедлайн: {current_deadline.strftime('%d-%m-%Y %H:%M')}\n"
        f"⏳ Запрошенный новый дедлайн: {requested_deadline.strftime('%d-%m-%Y %H:%M')}\n\n"
        "Пожалуйста, подтвердите запрос."
    )

    # Отправляем сообщение с inline-клавиатурой для подтверждения запроса
    await bot.send_message(
        telegram_id,
        message_text,
        reply_markup=kb.supervisor_postponement_keyboard(task_id, subordinate_user_id, requested_deadline)
    )


async def notify_subordinate_of_new_task(supervisor_user_id: int, task_id: int, subordinate_user_id: int):
    # Получаем Telegram ID подчинённого
    telegram_id = await fetch_telegram_id_by_user_id(subordinate_user_id)
    if not telegram_id:
        print(f"❌ Ошибка: Telegram ID не найден для UserID {subordinate_user_id}")
        return

    # Получаем информацию о руководителе (предполагается, что fetch_subordinate_info возвращает FIO и JobTitle)
    supervisor_info = await fetch_subordinate_info(supervisor_user_id)
    if supervisor_info:
        supervisor_name = supervisor_info.get("FullName", f"ID {supervisor_user_id}")
        supervisor_job = supervisor_info.get("JobTitle", "неизвестно")
    else:
        supervisor_name = f"ID {supervisor_user_id}"
        supervisor_job = "неизвестно"

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

    message_text = (
        f"👤 Руководитель: {supervisor_name} ({supervisor_job})\n"
        f"📌 Задание: {task_text}\n"
        f"📅 Дата выдачи: {start_of_term.strftime('%d-%m-%Y %H:%M')}\n"
        f"⏳ Дедлайн: {current_deadline.strftime('%d-%m-%Y %H:%M')}"
    )

    await bot.send_message(telegram_id, message_text)


async def notify_subordinate_of_edited_task(supervisor_user_id: int, task_id: int, subordinate_user_id: int):
    """
    Отправляет уведомление подчинённому о том, что задание было отредактировано руководителем.
    Уведомление содержит:
      - ФИО и должность руководителя,
      - Текст задания,
      - Дату выдачи,
      - Текущий (новый) дедлайн.
    """
    # Получаем Telegram chat_id подчинённого
    telegram_id = await fetch_telegram_id_by_user_id(subordinate_user_id)
    if not telegram_id:
        print(f"❌ Ошибка: Telegram ID не найден для UserID {subordinate_user_id}")
        return

    # Получаем информацию о руководителе (предполагается, что fetch_subordinate_info возвращает данные в виде словаря)
    supervisor_info = await fetch_subordinate_info(supervisor_user_id)
    if supervisor_info:
        supervisor_name = supervisor_info.get("FullName", f"ID {supervisor_user_id}")
        supervisor_job = supervisor_info.get("JobTitle", "неизвестно")
    else:
        supervisor_name = f"ID {supervisor_user_id}"
        supervisor_job = "неизвестно"

    # Получаем детали задания; предположим, что fetch_task_details возвращает кортеж:
    # (TaskID, CreatorID, Text, StartOfTerm, Deadline)
    task_details = await fetch_task_details(task_id)
    if not task_details:
        print("❌ Ошибка: не удалось получить детали задания.")
        return

    task_text = task_details[2]
    start_of_term = task_details[3]
    current_deadline = task_details[4]

    message_text = (
        f"👤 Руководитель: {supervisor_name} ({supervisor_job})\n"
        f"📌 Отредактированное задание: {task_text}\n"
        f"📅 Дата выдачи: {start_of_term.strftime('%d-%m-%Y %H:%M')}\n"
        f"⏳ Новый дедлайн: {current_deadline.strftime('%d-%m-%Y %H:%M')}"
    )

    await bot.send_message(telegram_id, message_text)


async def notify_subordinate_of_deleted_task(supervisor_user_id: int, task_id: int, subordinate_user_id: int):
    """
    Отправляет уведомление подчинённому о том, что задание было удалено руководителем.
    Уведомление содержит:
      - ФИО и должность руководителя,
      - Текст задания,
      - Дату выдачи,
      - Текущий дедлайн.
    """
    # Получаем Telegram chat_id подчинённого
    telegram_id = await fetch_telegram_id_by_user_id(subordinate_user_id)
    if not telegram_id:
        print(f"❌ Ошибка: Telegram ID не найден для UserID {subordinate_user_id}")
        return

    # Получаем информацию о руководителе (используем fetch_subordinate_info, предполагая, что он возвращает словарь с "FullName" и "JobTitle")
    supervisor_info = await fetch_subordinate_info(supervisor_user_id)
    if supervisor_info:
        supervisor_name = supervisor_info.get("FullName", f"ID {supervisor_user_id}")
        supervisor_job = supervisor_info.get("JobTitle", "неизвестно")
    else:
        supervisor_name = f"ID {supervisor_user_id}"
        supervisor_job = "неизвестно"

    # Получаем детали задания (предполагается, что fetch_task_details возвращает кортеж:
    # (TaskID, CreatorID, Text, StartOfTerm, Deadline))
    task_details = await fetch_task_details(task_id)
    if not task_details:
        print("❌ Ошибка: не удалось получить детали задания.")
        return

    task_text = task_details[2]
    start_of_term = task_details[3]
    current_deadline = task_details[4]

    message_text = (
        f"👤 Руководитель: {supervisor_name} ({supervisor_job})\n"
        f"📌 Задание: {task_text} было удалено.\n"
        f"📅 Дата выдачи: {start_of_term.strftime('%d-%m-%Y %H:%M')}\n"
        f"⏳ Дедлайн: {current_deadline.strftime('%d-%m-%Y')}"
    )

    await bot.send_message(telegram_id, message_text)


async def notify_subordinate_of_postponement_result(supervisor_user_id: int, subordinate_user_id: int, task_id: int, result: str, requested_deadline: datetime.datetime = None):
    """
    Отправляет уведомление подчинённому о том, что его запрос на перенос дедлайна был обработан.
    result: "approved" или "rejected"
    Если result == "approved", также передается requested_deadline.
    """
    telegram_id = await fetch_telegram_id_by_user_id(subordinate_user_id)
    if not telegram_id:
        print(f"❌ Ошибка: Telegram ID не найден для UserID {subordinate_user_id}")
        return

    # Получаем информацию о руководителе
    supervisor_info = await fetch_subordinate_info(supervisor_user_id)
    if supervisor_info:
        supervisor_name = supervisor_info.get("FullName", f"ID {supervisor_user_id}")
        supervisor_job = supervisor_info.get("JobTitle", "неизвестно")
    else:
        supervisor_name = f"ID {supervisor_user_id}"
        supervisor_job = "неизвестно"

    # Получаем детали задания
    task_details = await fetch_task_details(task_id)
    if not task_details:
        print("❌ Ошибка: не удалось получить детали задания.")
        return

    task_text = task_details[2]

    if result.lower() == "approved":
        message_text = (
            f"✅ Ваш запрос на перенос дедлайна для задания '{task_text}' был одобрен руководителем "
            f"{supervisor_name} ({supervisor_job}).\n"
            f"Новый дедлайн: {requested_deadline.strftime('%d-%m-%Y %H:%M')}."
        )
    else:
        message_text = (
            f"❌ Ваш запрос на перенос дедлайна для задания '{task_text}' был отклонён руководителем "
            f"{supervisor_name} ({supervisor_job})."
        )

    await bot.send_message(telegram_id, message_text)


async def check_tasks_for_notifications():
    now = datetime.datetime.now()
    intervals = [
        {"hours": 24, "label": "24 часа", "field": "LastNotificationSent24", "cooldown": datetime.timedelta(hours=24)},
        {"hours": 12, "label": "12 часов", "field": "LastNotificationSent12", "cooldown": datetime.timedelta(hours=12)},
        {"hours": 1, "label": "1 час", "field": "LastNotificationSent1", "cooldown": datetime.timedelta(hours=1)}
    ]
    tolerance = datetime.timedelta(minutes=5)

    for interval in intervals:
        target_time = now + datetime.timedelta(hours=interval["hours"])
        target_start = target_time - tolerance
        target_end = target_time + tolerance
        # print(
        #    f"Проверяем задания с дедлайном между {target_start} и {target_end} для уведомления за {interval['label']}")

        tasks = await asyncio.to_thread(get_tasks_with_deadline_in_range, target_start, target_end)
        # print(f"Найдено заданий: {len(tasks)}")

        for task in tasks:
            # Проверяем, отправлялось ли уведомление для данного интервала.
            last_sent = task.get(interval["field"])
            # Если уведомление уже отправлено и с него прошло меньше cooldown, пропускаем.
            if last_sent and (now - last_sent) < interval["cooldown"]:
                #     print(f"🔹 Уведомление уже отправлено для задачи {task['TaskID']} за {interval['label']}, пропускаем.")
                continue

            telegram_id = await fetch_telegram_id_by_user_id(task["AssigneeID"])
            if not telegram_id:
                print(f"❌ Telegram ID не найден для UserID {task['AssigneeID']}")
                continue

            message_text = (
                f"📌 Напоминание: задание '{task['Text']}' заканчивается через {interval['label']}.\n"
                f"⏳ Дедлайн: {task['Deadline'].strftime('%d-%m-%Y %H:%M')}."
            )
            await bot.send_message(telegram_id, message_text)
            #print(f"✅ Уведомление отправлено для задачи {task['TaskID']} за {interval['label']}")

            # Обновляем флаг уведомления для этого интервала
            # interval["label"].split()[0] вернёт "24", "12" или "1"
            await fetch_update_last_notification_sent_interval(task["TaskID"], interval["label"].split()[0], now)


async def check_overdue_tasks():
    print(f"Проверка просроченных заданий: {datetime.datetime.now()}")
    tasks = await fetch_overdue_tasks()
    print(f"Найдено просроченных заданий: {len(tasks)}")
    for task in tasks:
        await fetch_mark_task_overdue(task["TaskID"], task["AssigneeID"])
        print(f"Задание {task['TaskID']} для сотрудника {task['AssigneeID']} отмечено как Просрочено.")

