from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart,Command
from aiogram.fsm.state import State,StatesGroup #Состояние
from aiogram.fsm.context import FSMContext #Состояние

from database.requests import (fetch_user_by_login, fetch_assigned_tasks,fetch_user_by_subordinate, insert_task,
                               fetch_insert_task_assignee, fetch_update_task)
import app.keydoards as kb
import datetime
import asyncio


router = Router()


class Register(StatesGroup):
    login= State()
    password=State()
    select_subordinate = State()


class Task (StatesGroup):
    entering_task = State()
    entering_deadline = State()


class TaskEditing(StatesGroup):
    new_text = State()
    new_deadline = State()


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
            await state.update_data(user_id=user.UserID)
            await message.answer("Вход успешный", reply_markup=kb.Supervisor)
            await state.set_state("LoggedIn")
        else:
            await message.answer("Неверный пароль. Попробуйте ещё раз.")
    else:
        await message.answer("Пользователь не найден. Попробуйте ещё раз.")
        await state.clear()


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


@router.message(F.text == "Выбрать подчиненного")
async def subordinate(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        await message.answer("Ошибка: пользователь не авторизован. Пожалуйста, перезапустите /start")
        return

    rows = await fetch_user_by_subordinate(user_id)

    if rows:
        result_text = ":\n"
        available_ids = []
        for row in rows:
            result_text += (
                f"ID: {row.UserID}\n"
                f"Имя: {row.Fio}\n"
                f"Тип: {row.Type}\n\n"
            )
            available_ids.append(str(row.UserID))
        result_text += "Введите ID выбранного подчинённого:"
        await message.answer(result_text)
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
    await message.answer("Введите дедлайн в формате YYYY-MM-DD:")
    await state.set_state(Task.entering_deadline)


@router.message(Task.entering_deadline)
async def process_deadline(message: Message, state: FSMContext):
    deadline_text = message.text.strip()
    try:
        deadline_date = datetime.datetime.strptime(deadline_text, "%Y-%m-%d")
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
        f"✅ Задание сохранено:\n📌 {task_text}\n📅 Дедлайн: {deadline_date.date()}\nTaskID: {task_id}\nAssignmentID: {assignment_id}"
    )

    @router.callback_query(F.data == "Edit_task")
    async def edit_task_callback(callback: CallbackQuery, state: FSMContext):
        await callback.message.answer("Введите новый текст задания:")
        await state.set_state(TaskEditing.new_text)
        await callback.answer()

    @router.message(TaskEditing.new_text)
    async def process_edit_task(message: Message, state: FSMContext):
        new_text = message.text.strip()
        await message.answer(f"Задание успешно обновлено на:\n{new_text}")


@router.callback_query(F.data == "Edit_task")
async def edit_task_callback(callback: CallbackQuery, state: FSMContext):
    # Проверяем, что в состоянии сохранён идентификатор задачи
    data = await state.get_data()
    task_id = data.get("task_id")
    if not task_id:
        await callback.message.answer("Ошибка: не найден идентификатор задачи для редактирования.")
        await callback.answer()
        return
    await callback.message.answer("Введите новый текст задания:")
    await state.set_state(TaskEditing.new_text)
    await callback.answer()


@router.message(TaskEditing.new_text)
async def process_new_text(message: Message, state: FSMContext):
    new_text = message.text.strip()
    if not new_text:
        await message.answer("Текст не может быть пустым. Введите новый текст задания:")
        return
    await state.update_data(new_text=new_text)
    await message.answer("Введите новый дедлайн в формате YYYY-MM-DD:")
    await state.set_state(TaskEditing.new_deadline)


@router.message(TaskEditing.new_deadline)
async def process_new_deadline(message: Message, state: FSMContext):
    new_deadline_text = message.text.strip()
    try:
        new_deadline = datetime.datetime.strptime(new_deadline_text, "%Y-%m-%d")
        if new_deadline.date() < datetime.date.today():
            await message.answer("Дедлайн не может быть в прошлом. Введите корректный дедлайн:")
            return
    except ValueError:
        await message.answer("Неверный формат даты. Введите дату в формате YYYY-MM-DD:")
        return

    data = await state.get_data()
    new_text = data.get("new_text")
    task_id = data.get("task_id")
    if not task_id:
        await message.answer("Ошибка: не найден идентификатор задачи для редактирования.")
        await state.clear()
        return

    # Обновляем задачу в базе данных
    await fetch_update_task(task_id, new_text, new_deadline)

    await message.answer(
        f"Задание обновлено:\nНовый текст: {new_text}\nНовый дедлайн: {new_deadline.date()}"
    )