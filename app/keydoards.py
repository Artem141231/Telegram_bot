from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove)

start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="/start")]],
    resize_keyboard=True,
    one_time_keyboard=True
)


def remove_keyboard():
    return ReplyKeyboardRemove()


Supervisor = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Посмотреть назначенные задачи")],
                                     [KeyboardButton(text="Выбрать подчиненного")]],
                           resize_keyboard=True,
                           input_field_placeholder="Выберите пункт меню")


Select_subordinate = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Удалить существующие задания",callback_data="Delete_task")],
    [InlineKeyboardButton(text="Добавить новое задание",callback_data="Add_task")],
    [InlineKeyboardButton(text="Редактировать задание",callback_data="Edit_task")],
    [InlineKeyboardButton(text="Сформировать отчёт",callback_data="Generate_report")]])