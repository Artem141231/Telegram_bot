from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart,Command
from aiogram.fsm.state import State,StatesGroup #Состояние
from aiogram.fsm.context import FSMContext #Состояние

from database.requests import (fetch_user_by_login, fetch_assigned_tasks,fetch_user_by_subordinate, insert_task,
                               fetch_insert_task_assignee, fetch_update_task,fetch_assigned_tasks_enumeration,
                               fetch_delete_task_assignee,fetch_delete_task, fetch_type_by_id,
                               fetch_update_task_postponement,fetch_task_details,
                               fetch_update_task_status,fetch_update_telegram_id,
                               fetch_assigned_tasks_enumeration_for_subordinates, fetch_update_task_for_deadline)

from app.notifications import notify_creator_task_completed, notify_supervisor_of_postponement
import app.keydoards as kb
import datetime
import asyncio


router = Router()


class Register(StatesGroup):
    login = State()
    password = State()
    select_subordinate = State()


class Task (StatesGroup):
    entering_task = State()
    entering_deadline = State()


# Новые состояния для редактирования задачи
class TaskEditing(StatesGroup):
    choose_task = State()    # выбор TaskID из перечня
    new_text = State()       # ввод нового текста задания
    new_deadline = State()   # ввод нового дедлайна


class TaskDeletion(StatesGroup):
    choose_task = State()   # выбор TaskID для удаления
    confirm = State()       # подтверждение удаления


class SubordinateSelectTask(StatesGroup):
    choose_task = State()


class TaskPostponement(StatesGroup):
    entering_new_deadline = State()   # ввод новой даты переноса
    confirming_request = State()       # подтверждение запроса


@router.message(CommandStart())
async def Start_Authorization(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Введите логин")
    await state.set_state(Register.login)


@router.message(Register.login)
async def authorization_login(message: Message, state: FSMContext):
    login = message.text
    user = await fetch_user_by_login(login)
    if user:
        await state.update_data(login=login, user_id=user.UserID)
        await state.set_state(Register.password)
        await message.answer("Введите пароль")
    else:
        await message.answer("Пользователь не найден. Попробуйте ещё раз.")


@router.message(Register.password)
async def authorization_password(message: Message, state: FSMContext):
    data = await state.get_data()
    login = data.get("login")
    provided_password = message.text
    user = await fetch_user_by_login(login)
    if user:
        if provided_password == user.Password:
            # Получаем актуальный Telegram ID
            current_telegram_id = message.from_user.id

            # Обновляем telegram_id, если он отличается
            if user.telegram_id != current_telegram_id:
                await fetch_update_telegram_id(user.UserID, current_telegram_id)

            # Получаем роль пользователя и продолжаем авторизацию
            user_type_id = user.TypeID
            role_status = await fetch_type_by_id(
                user_type_id)  # Например, "Senior Executive", "Middle Manager", "Subordinate"
            await state.update_data(user_id=user.UserID, role_status=role_status)

            if role_status == "Senior Executive":
                await message.answer("Вход успешный (Senior Executive)", reply_markup=kb.SeniorExecKeyboard)
            elif role_status == "Middle Manager":
                await message.answer("Вход успешный (Middle Manager)", reply_markup=kb.MiddleManagerKeyboard)
            elif role_status == "Subordinate":
                await message.answer("Вход успешный (Subordinate)", reply_markup=kb.SubordinateKeyboard)
            else:
                await message.answer("Вход успешный, но роль не распознана.", reply_markup=kb.start_keyboard)
            await state.set_state("LoggedIn")
        else:
            await message.answer("Неверный пароль. Попробуйте ещё раз.")
    else:
        await message.answer("Пользователь не найден. Попробуйте ещё раз.")
        await state.clear()


@router.callback_query(F.data == "cancel_operation")
async def cancel_operation_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role_status = data.get("role_status")

    if role_status == "Senior Executive":
        reply_kb = kb.SeniorExecKeyboard
        text = "Операция отменена. Возвращаемся в главное меню (Senior Executive)."
    elif role_status == "Middle Manager":
        reply_kb = kb.MiddleManagerKeyboard
        text = "Операция отменена. Возвращаемся в главное меню (Middle Manager)."
    elif role_status == "Subordinate":
        reply_kb = kb.SubordinateKeyboard
        text = "Операция отменена. Возвращаемся в главное меню (Subordinate)."
    else:
        reply_kb = kb.start_keyboard
        text = "Операция отменена. Роль не распознана, возвращаемся в главное меню."

    await state.set_state("LoggedIn")
    await callback.message.answer(text, reply_markup=reply_kb)
    await callback.answer()


@router.message(F.text == "Посмотреть назначенные задачи")
async def assigned_tasks(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        await message.answer("Ошибка: пользователь не авторизован. Пожалуйста, перезапустите /start")
        return
    tasks = await fetch_assigned_tasks(user_id)
    if tasks:
        result_text = ""
        for index, row in enumerate(tasks, start=1):
            result_text += (f"{index}. Задача: {row.TaskText}\n"
                            f"От: {row.CreatorFio} ({row.CreatorRole})\n"
                            f"Для: {row.AssigneeFio} ({row.AssigneeRole})\n"
                            f"Начало: {row.StartOfTerm}\n"
                            f"Дедлайн: {row.Deadline}\n\n")
        await message.answer(result_text)
    else:
        await message.answer("Нет назначенных задач.")


@router.message(F.text == "Выбрать подчинённого")
async def subordinate(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    current_role = data.get("role_status")
    if not user_id or not current_role:
        await message.answer("Ошибка: пользователь не авторизован. Пожалуйста, перезапустите /start")
        return

    rows = await fetch_user_by_subordinate(user_id, current_role)
    if rows:
        result_text = "Доступные подчинённые:\n\n"
        available_ids = []
        for row in rows:
            result_text += (
                f"ID: {row.UserID}\n"
                f"Имя: {row.Fio}\n"
                f"Тип: {row.Type}\n\n"
            )
            available_ids.append(str(row.UserID))
        result_text += "Введите ID выбранного подчинённого или нажмите «Отмена»:"
        await message.answer(result_text, reply_markup=kb.cancel_keyboard)
        await state.update_data(available_subordinate_ids=available_ids)
        await state.set_state(Register.select_subordinate)
    else:
        await message.answer("Нет доступных подчинённых")


@router.message(Register.select_subordinate)
async def handle_subordinate_selection(message: Message, state: FSMContext):
    subordinate_id = message.text.strip()
    data = await state.get_data()
    available_ids = data.get("available_subordinate_ids", [])
    if subordinate_id not in available_ids:
        await message.answer("Введённый ID недоступен. Пожалуйста, выберите ID из списка.")
        return
    await state.update_data(subordinate_id=subordinate_id)
    await message.answer("Выберите действие для выбранного подчинённого:", reply_markup=kb.Select_subordinate)
    await state.set_state("SubordinateAction")


@router.callback_query(F.data == "Add_task")
async def add_task_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите задание:")
    await state.set_state(Task.entering_task)  # Переход к состоянию ввода текста задания
    await callback.answer()


@router.callback_query(F.data == "Add_task")
async def add_task_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите задание:")
    await state.set_state(Task.entering_task)  # Переход в состояние ввода текста задания
    await callback.answer()


@router.message(Task.entering_task)
async def process_task(message: Message, state: FSMContext):
    task_text = message.text.strip()
    if not task_text:
        await message.answer("Задание не может быть пустым. Введите ещё раз:")
        return
    await state.update_data(task_text=task_text)
    await message.answer("Введите дедлайн в формате DD-MM-YYYY:")
    await state.set_state(Task.entering_deadline)


@router.message(Task.entering_deadline)
async def process_deadline(message: Message, state: FSMContext):
    deadline_text = message.text.strip()
    try:
        deadline_date = datetime.datetime.strptime(deadline_text, "%d-%m-%Y")
        if deadline_date.date() < datetime.date.today():
            await message.answer("Дата не может быть в прошлом. Введите корректный дедлайн:")
            return
    except ValueError:
        await message.answer("Неверный формат даты. Введите в формате YYYY-MM-DD:")
        return
    data = await state.get_data()
    task_text = data.get("task_text")
    creator_id = data.get("user_id")  # Идентификатор руководителя (создателя задачи)
    subordinate_id = data.get("subordinate_id")  # Идентификатор выбранного подчинённого

    if not creator_id or not subordinate_id:
        await message.answer("Ошибка: недостаточно данных авторизации. Пожалуйста, перезапустите /start")
        return
    start_of_term = datetime.datetime.now()
    task_id = await asyncio.to_thread(insert_task, creator_id, task_text, start_of_term, deadline_date)
    assignment_id = await fetch_insert_task_assignee(task_id, subordinate_id, "В процессе")
    await message.answer(
        f"✅ Задание сохранено:\n📌 {task_text}\n📅 Дедлайн: {deadline_date.date()}\nTaskID: {task_id}\nAssignmentID: "
        f"{assignment_id}"
    )


@router.callback_query(F.data == "Edit_task")
async def edit_task_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subordinate_id = data.get("subordinate_id")
    creator_id = data.get("user_id")  # текущий менеджер
    if not subordinate_id or not creator_id:
        await callback.message.answer("Ошибка: подчинённый или текущий пользователь не определён. Пожалуйста, выберите подчинённого.")
        await callback.answer()
        return

    # Получаем список задач, назначенных выбранному подчинённому и созданных текущим менеджером
    tasks = await fetch_assigned_tasks_enumeration(int(subordinate_id), int(creator_id))
    if not tasks:
        await callback.message.answer("Нет заданий для редактирования у выбранного подчинённого.")
        await callback.answer()
        return

    result_text = "Доступные задачи для редактирования:\n\n"
    available_task_ids = []
    for row in tasks:
        result_text += (
            f"TaskID: {row.TaskID}\n"
            f"Текст: {row.TaskText}\n"
            f"Начало: {row.StartOfTerm}\n"
            f"Дедлайн: {row.Deadline}\n"
            f"Создатель: {row.CreatorFio}\n\n"
        )
        available_task_ids.append(str(row.TaskID))
    result_text += "Введите ID задачи, которую хотите редактировать:"
    await state.update_data(available_task_ids=available_task_ids)
    await callback.message.answer(result_text)
    await state.set_state(TaskEditing.choose_task)
    await callback.answer()



@router.message(TaskEditing.choose_task)
async def process_choose_task(message: Message, state: FSMContext):
    """
    Обрабатывает ввод TaskID, проверяет, что введённый ID есть в списке доступных,
    и сохраняет его для дальнейшего редактирования.
    """
    chosen_task_id = message.text.strip()
    data = await state.get_data()
    available_task_ids = data.get("available_task_ids", [])
    if chosen_task_id not in available_task_ids:
        await message.answer("Введённый TaskID недоступен. Пожалуйста, выберите ID из списка.")
        return
    await state.update_data(task_id=chosen_task_id)
    await message.answer("Введите новый текст задания:")
    await state.set_state(TaskEditing.new_text)


@router.message(TaskEditing.new_text)
async def process_new_text(message: Message, state: FSMContext):
    """
    Обрабатывает ввод нового текста задания.
    """
    new_text = message.text.strip()
    if not new_text:
        await message.answer("Текст не может быть пустым. Введите новый текст задания:")
        return
    await state.update_data(new_text=new_text)
    await message.answer("Введите новый дедлайн в формате DD-MM-YYYY:")
    await state.set_state(TaskEditing.new_deadline)


@router.message(TaskEditing.new_deadline)
async def process_new_deadline(message: Message, state: FSMContext):
    """
    Обрабатывает ввод нового дедлайна, проверяет корректность формата и обновляет запись в БД.
    """
    new_deadline_text = message.text.strip()
    try:
        new_deadline = datetime.datetime.strptime(new_deadline_text, "%d-%m-%Y")
        if new_deadline.date() < datetime.date.today():
            await message.answer("Дедлайн не может быть в прошлом. Введите корректный дедлайн:")
            return
    except ValueError:
        await message.answer("Неверный формат даты. Введите дату в формате DD-MM-YYYY:")
        return

    data = await state.get_data()
    new_text = data.get("new_text")
    task_id = data.get("task_id")
    if not task_id:
        await message.answer("Ошибка: не найден идентификатор задачи для редактирования.")
        await state.clear()
        return

    # Обновляем задачу в базе данных
    await fetch_update_task(int(task_id), new_text, new_deadline)

    await message.answer(
        f"Задание обновлено:\nНовый текст: {new_text}\nНовый дедлайн: {new_deadline.date()}"
    )


@router.callback_query(F.data == "Delete_task")
async def delete_task_callback(callback: CallbackQuery, state: FSMContext):
    """
    При нажатии кнопки "Delete_task" выводит список заданий для выбранного подчинённого,
    после чего просит ввести TaskID для удаления.
    """
    data = await state.get_data()
    subordinate_id = data.get("subordinate_id")
    creator_id = data.get("user_id")  # ID текущего пользователя (менеджера)
    if not subordinate_id or not creator_id:
        await callback.message.answer("Ошибка: подчинённый или текущий пользователь не выбран. Пожалуйста, "
                                      "выберите подчинённого.")
        await callback.answer()
        return

    # Получаем список заданий для выбранного подчинённого и текущего менеджера
    tasks = await fetch_assigned_tasks_enumeration(int(subordinate_id), int(creator_id))
    if not tasks:
        await callback.message.answer("Нет заданий для удаления у выбранного подчинённого.")
        await callback.answer()
        return

    result_text = "Доступные задания для удаления:\n\n"
    available_task_ids = []
    for row in tasks:
        result_text += (
            f"TaskID: {row.TaskID}\n"
            f"Текст: {row.TaskText}\n"
            f"Начало: {row.StartOfTerm}\n"
            f"Дедлайн: {row.Deadline}\n"
            f"Создатель: {row.CreatorFio}\n\n"
        )
        available_task_ids.append(str(row.TaskID))
    result_text += "Введите ID задачи, которую хотите удалить:"
    await state.update_data(available_task_ids=available_task_ids)
    await callback.message.answer(result_text)
    await state.set_state(TaskDeletion.choose_task)
    await callback.answer()


@router.message(TaskDeletion.choose_task)
async def process_delete_choice(message: Message, state: FSMContext):
    chosen_task_id = message.text.strip()
    data = await state.get_data()
    available_task_ids = data.get("available_task_ids", [])
    if chosen_task_id not in available_task_ids:
        await message.answer("Введённый TaskID недоступен. Пожалуйста, выберите ID из списка.")
        return
    await state.update_data(task_id=chosen_task_id)
    await message.answer("Подтвердите удаление задания, нажав кнопку ниже:", reply_markup=kb.delete_confirm_keyboard)
    await state.set_state(TaskDeletion.confirm)



@router.callback_query(F.data == "confirm_delete")
async def confirm_delete(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("task_id")
    subordinate_id = data.get("subordinate_id")
    if not task_id or not subordinate_id:
        await callback.message.answer("Ошибка: отсутствуют необходимые данные для удаления.")
        await state.clear()
        await callback.answer()
        return
    # Удаляем запись из Task_Assignees
    await fetch_delete_task_assignee(int(task_id), int(subordinate_id))
    # Удаляем задачу из таблицы Task
    await fetch_delete_task(int(task_id))
    await callback.message.answer(f"Задание с TaskID {task_id} успешно удалено.")
    await callback.answer()

@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Удаление отменено.")
    await callback.answer()





#-------------------------------------------------------------------------------------------------------


@router.message(F.text == "Выбрать задание")
async def choose_own_task(message: Message, state: FSMContext):
    """
    Подчинённый получает список заданий, назначенных ему, и вводит ID нужного задания.
    """
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        await message.answer("Ошибка: пользователь не авторизован. Пожалуйста, перезапустите /start")
        return

    # Получаем список заданий для данного подчинённого
    tasks = await fetch_assigned_tasks_enumeration_for_subordinates(int(user_id))
    if not tasks:
        await message.answer("У вас нет доступных заданий.")
        return

    result_text = "Ваши задания:\n\n"
    available_task_ids = []
    for row in tasks:
        result_text += (
            f"TaskID: {row.TaskID}\n"
            f"Текст: {row.TaskText}\n"
            f"Начало: {row.StartOfTerm}\n"
            f"Дедлайн: {row.Deadline}\n"
            f"Создатель: {row.CreatorFio}\n\n"
        )
        available_task_ids.append(str(row.TaskID))
    result_text += "Введите ID задачи, которую хотите выбрать:"
    await message.answer(result_text, reply_markup=kb.cancel_keyboard)
    await state.update_data(available_task_ids=available_task_ids)
    await state.set_state(SubordinateSelectTask.choose_task)


@router.message(SubordinateSelectTask.choose_task)
async def process_subordinate_task_choice(message: Message, state: FSMContext):
    """
    Проверяем введённый ID и сохраняем выбранное задание для дальнейших действий.
    """
    chosen_task_id = message.text.strip()
    data = await state.get_data()
    available_task_ids = data.get("available_task_ids", [])
    if chosen_task_id not in available_task_ids:
        await message.answer("Введённый TaskID недоступен. Пожалуйста, выберите из списка.")
        return
    await state.update_data(chosen_task_id=chosen_task_id)
    await message.answer(
        f"Вы выбрали задание с ID {chosen_task_id}.\n"
        "Чтобы запросить перенос дедлайна, нажмите кнопку ниже.",
        reply_markup=kb.Select_task
    )


@router.callback_query(F.data == "Extend_deadline")
async def request_postponement_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("chosen_task_id")
    if not task_id:
        await callback.message.answer("Ошибка: не выбран TaskID для запроса переноса.")
        await callback.answer()
        return
    await callback.message.answer(
        "Введите новую дату переноса дедлайна в формате DD-MM-YYYY:",
        reply_markup=kb.cancel_keyboard
    )
    await state.set_state(TaskPostponement.entering_new_deadline)
    await callback.answer()


@router.message(TaskPostponement.entering_new_deadline)
async def process_postponement_deadline(message: Message, state: FSMContext):
    new_deadline_text = message.text.strip()
    try:
        new_deadline = datetime.datetime.strptime(new_deadline_text, "%d-%m-%Y")
        if new_deadline.date() < datetime.date.today():
            await message.answer("Дата не может быть в прошлом. Введите корректную дату:")
            return
    except ValueError:
        await message.answer("Неверный формат даты. Введите дату в формате DD-MM-YYYY:")
        return
    await state.update_data(requested_deadline=new_deadline)
    await message.answer("Подтвердите запрос переноса дедлайна:", reply_markup=kb.Yes_or_not_keyboard)
    await state.set_state(TaskPostponement.confirming_request)


@router.message(TaskPostponement.entering_new_deadline)
async def process_postponement_deadline(message: Message, state: FSMContext):
    """
    Обрабатывает ввод новой даты, проверяет корректность и предлагает подтверждение.
    """
    new_deadline_text = message.text.strip()
    try:
        new_deadline = datetime.datetime.strptime(new_deadline_text, "%d-%m-%Y")
        if new_deadline.date() < datetime.date.today():
            await message.answer("Дата не может быть в прошлом. Введите корректную дату:")
            return
    except ValueError:
        await message.answer("Неверный формат даты. Введите дату в формате YYYY-MM-DD:")
        return

    await state.update_data(requested_deadline=new_deadline)
    await message.answer("Подтвердите запрос переноса дедлайна:", reply_markup=kb.Yes_or_not_keyboard)
    await state.set_state(TaskPostponement.confirming_request)


@router.callback_query(F.data.in_(["confirm", "cancel"]))
async def process_postponement_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    print(f"STATE DATA: {data}")
    task_id = data.get("chosen_task_id")
    subordinate_id = data.get("user_id")
    requested_deadline = data.get("requested_deadline")
    if not task_id or not subordinate_id or not requested_deadline:
        await callback.message.answer("Ошибка: недостаточно данных для запроса переноса.")
        await callback.answer()
        return

    if callback.data == "confirm":
        await fetch_update_task_postponement(int(task_id), int(subordinate_id), requested_deadline,
                                             "Ожидает подтверждения")
        await callback.message.answer("Запрос переноса дедлайна отправлен руководителю на подтверждение.")

        task_details = await fetch_task_details(int(task_id))
        if not task_details:
            await callback.message.answer("Ошибка: не удалось получить детали задания.")
            await state.reset_state(with_data=True)
            await callback.answer()
            return

        supervisor_id = task_details[1]  # Предполагаем, что CreatorID находится в task_details[1]
        from app.notifications import notify_supervisor_of_postponement
        await notify_supervisor_of_postponement(
            supervisor_id,
            int(subordinate_id),
            int(task_id),
            requested_deadline
        )
    else:
        await callback.message.answer("Запрос переноса дедлайна отменён.")

    await state.set_state("LoggedIn")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_supervisor"))
async def supervisor_confirm_postponement(callback: CallbackQuery):

    _, task_id, subordinate_id, deadline_str = callback.data.split(":")

    requested_deadline = datetime.datetime.strptime(deadline_str, "%d-%m-%Y")



    await fetch_update_task_for_deadline(int(task_id), requested_deadline)


    await fetch_update_task_postponement(int(task_id), int(subordinate_id), requested_deadline, "Одобрено")

    await callback.message.answer("✅ Запрос переноса дедлайна одобрен. Дедлайн задания обновлен.")
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_supervisor"))
async def supervisor_cancel_postponement(callback: CallbackQuery):
    _, task_id, subordinate_id = callback.data.split(":")

    await fetch_update_task_postponement(int(task_id), int(subordinate_id), None, "Отклонено")

    await callback.message.answer("❌ Запрос переноса дедлайна отклонён.")
    await callback.answer()




@router.callback_query(F.data == "Confirm_execution_task")
async def confirm_execution_task_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("chosen_task_id")  # выбранный TaskID, сохранённый в состоянии
    user_id = data.get("user_id")  # ID подчинённого, который подтверждает выполнение
    if not task_id or not user_id:
        await callback.message.answer("❌ Ошибка: недостаточно данных для подтверждения выполнения.")
        await callback.answer()
        return

    await fetch_update_task_status(int(task_id), int(user_id), "Выполнено")

    task_details = await fetch_task_details(int(task_id))
    if not task_details:
        await callback.message.answer("❌ Ошибка: не удалось получить детали задания.")
        await callback.answer()
        return

    # Обращаемся по индексам
    creator_id = task_details[1]
    task_text = task_details[2]

    await notify_creator_task_completed(creator_id, task_text, int(user_id))

    await callback.message.answer(f"✅ Задание (TaskID: {task_id}) успешно отмечено как выполненное!")
    await callback.answer()
