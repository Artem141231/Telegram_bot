import asyncio
from aiogram import Dispatcher
from app.handlers import router
from bot import bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.notifications import check_tasks_for_notifications,check_overdue_tasks


async def main():
    scheduler = AsyncIOScheduler()
    # Запускаем проверку уведомлений каждые 5 минуту
    scheduler.add_job(check_tasks_for_notifications, 'interval', minutes=5)
    # Запускаем проверку просроченных заданий каждый час
    scheduler.add_job(check_overdue_tasks, 'interval', hours=1)
    scheduler.start()

    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")