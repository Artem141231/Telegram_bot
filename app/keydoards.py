from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove)


from aiogram.utils.keyboard import InlineKeyboardBuilder
import datetime


start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="/start")]],
    resize_keyboard=True,
    one_time_keyboard=True
)
cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Отмена", callback_data="cancel_operation")]
])


def remove_keyboard():
    return ReplyKeyboardRemove()


SeniorExecKeyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Посмотреть назначенные задачи")],
                                     [KeyboardButton(text="Выбрать подчинённого")]],
                           resize_keyboard=True,
                           input_field_placeholder="Выберите пункт меню")


MiddleManagerKeyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Посмотреть назначенные задачи")],
                                     [KeyboardButton(text="Выбрать подчинённого")],
                                    [KeyboardButton(text="Выбрать задание")]],
                           resize_keyboard=True,
                           input_field_placeholder="Выберите пункт меню")


Select_subordinate = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Удалить существующие задания",callback_data="Delete_task")],
    [InlineKeyboardButton(text="Добавить новое задание",callback_data="Add_task")],
    [InlineKeyboardButton(text="Редактировать задание",callback_data="Edit_task")],
    [InlineKeyboardButton(text="Сформировать отчёт",callback_data="Generate_report")]]) # Еще_не_реализовал


SubordinateKeyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Посмотреть назначенные задачи")],
                                     [KeyboardButton(text="Выбрать задание")]],
                           resize_keyboard=True,
                           input_field_placeholder="Выберите пункт меню")


Select_task = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Продлить дедлайн",callback_data="Extend_deadline")],
    [InlineKeyboardButton(text="Подтвердить выполнение задания", callback_data="Confirm_execution_task")],
    [InlineKeyboardButton(text="Отмена", callback_data="cancel_operation")]])


delete_confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да", callback_data="confirm_delete")],
    [InlineKeyboardButton(text="Нет", callback_data="cancel_delete")]
])


Yes_or_not_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да", callback_data="confirm")],
    [InlineKeyboardButton(text="Нет", callback_data="cancel")]
])


def supervisor_postponement_keyboard(task_id: int, subordinate_id: int, requested_deadline: datetime.datetime):
    deadline_str = requested_deadline.strftime("%d-%m-%Y")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"confirm_supervisor:{task_id}:{subordinate_id}:{deadline_str}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"cancel_supervisor:{task_id}:{subordinate_id}"
            )
        ]
    ])