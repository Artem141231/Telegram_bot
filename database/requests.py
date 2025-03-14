import asyncio
import pyodbc
import datetime


CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=Diploma;"
    "Trusted_Connection=yes;"
)

def get_connection():
    return pyodbc.connect(CONNECTION_STRING)


def query_type_by_id(type_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT [Status] FROM dbo.[Type] WHERE TypeID = ?", type_id)
        row = cursor.fetchone()
        return row.Status if row else None
    finally:
        conn.close()


def query_user_by_login(login:str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dbo.Users WHERE Login = ?", login)
        row = cursor.fetchone()
        return row
    finally:
        conn.close()


def query_assigned_tasks(user_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            Creator.Fio AS CreatorFio,
            CreatorType.Type AS CreatorRole,
            Assignee.Fio AS AssigneeFio,
            AssigneeType.Type AS AssigneeRole,
            t.Text AS TaskText,
            t.StartOfTerm,
            t.Deadline
        FROM dbo.Task t
        JOIN dbo.Users AS Creator 
            ON t.CreatorID = Creator.UserID
        JOIN dbo.Type AS CreatorType 
            ON Creator.TypeID = CreatorType.TypeID
        JOIN dbo.Task_Assignees ta 
            ON t.TaskID = ta.TaskID
        JOIN dbo.Users AS Assignee 
            ON ta.UserID = Assignee.UserID
        JOIN dbo.Type AS AssigneeType 
            ON Assignee.TypeID = AssigneeType.TypeID
        WHERE (t.CreatorID = ? OR ta.UserID = ?)
          AND ta.Status = 'В процессе'
        """
        cursor.execute(query, user_id, user_id)
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def query_user_by_subordinate(user_id: int, current_role: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT U.UserID, U.Fio, T.Type, T.[Status] AS UserStatus
            FROM dbo.Users U
            JOIN dbo.Type T ON U.TypeID = T.TypeID
            WHERE U.UserID <> ?
        """
        # Фильтруем в зависимости от роли текущего пользователя:
        if current_role == 'Senior Executive':
            # Senior Executive не может назначать Senior Executive
            query += " AND T.[Status] <> 'Senior Executive'"
        elif current_role == 'Middle Manager':
            # Middle Manager не может назначать Senior Executive и Middle Manager
            query += " AND T.[Status] NOT IN ('Senior Executive', 'Middle Manager')"
        # Если текущая роль — Subordinate, можно либо вообще не разрешать назначение, либо вернуть пустой список
        cursor.execute(query, user_id)
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def insert_task(creator_id: int, text: str, start_of_term: datetime.datetime, deadline: datetime.datetime):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO dbo.Task (CreatorID, Text, StartOfTerm, Deadline, CreatedAt, UpdatedAt)
            VALUES (?, ?, ?, ?, GETDATE(), GETDATE())
        """
        cursor.execute(query, creator_id, text, start_of_term, deadline)
        conn.commit()
        cursor.execute("SELECT @@IDENTITY")
        task_id = cursor.fetchone()[0]
        return task_id
    finally:
        conn.close()


def insert_task_assignee(task_id: int, user_id: int, status: str = "New"):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO dbo.Task_Assignees 
            (TaskID, UserID, Status, AssignedAt, UpdatedAt, PostponementOfDeadline, PostponementStatus)
            VALUES (?, ?, ?, GETDATE(), GETDATE(), NULL, NULL)
        """
        cursor.execute(query, task_id, user_id, status)
        conn.commit()
        # Получаем ID вставленной записи
        cursor.execute("SELECT @@IDENTITY")
        assignment_id = cursor.fetchone()[0]
        return assignment_id
    finally:
        conn.close()


def update_task(task_id: int, new_text: str, new_deadline: datetime.datetime):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE dbo.Task
            SET Text = ?, Deadline = ?, UpdatedAt = GETDATE()
            WHERE TaskID = ?
        """
        cursor.execute(query, new_text, new_deadline, task_id)
        conn.commit()
    finally:
        conn.close()


def update_task_for_deadline(task_id: int, new_deadline: datetime.datetime):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
               UPDATE dbo.Task
               SET Deadline = ?, UpdatedAt = GETDATE()
               WHERE TaskID = ?
           """
        cursor.execute(query, new_deadline, task_id)
        conn.commit()
    finally:
        conn.close()




def query_assigned_tasks_enumeration(subordinate_id: int, creator_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            t.TaskID,
            t.Text AS TaskText,
            t.StartOfTerm,
            t.Deadline,
            Creator.Fio AS CreatorFio,
            ta.Status AS TaskStatus
        FROM dbo.Task t
        JOIN dbo.Task_Assignees ta ON t.TaskID = ta.TaskID
        JOIN dbo.Users AS Creator ON t.CreatorID = Creator.UserID
        WHERE ta.UserID = ? 
          AND t.CreatorID = ? 
          AND ta.Status <> 'Выполнено'
        """
        cursor.execute(query, subordinate_id, creator_id)
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def query_assigned_tasks_enumeration_for_subordinates(subordinate_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            t.TaskID,
            t.Text AS TaskText,
            t.StartOfTerm,
            t.Deadline,
            Creator.Fio AS CreatorFio,
            ta.Status AS TaskStatus
        FROM dbo.Task t
        JOIN dbo.Task_Assignees ta 
            ON t.TaskID = ta.TaskID
        JOIN dbo.Users AS Creator 
            ON t.CreatorID = Creator.UserID
        WHERE ta.UserID = ? AND ta.Status <> 'Выполнено'
        """
        cursor.execute(query, subordinate_id)
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()



def delete_task_assignee(task_id: int, subordinate_id: int):
    """
    Удаляет запись из таблицы Task_Assignees по заданным TaskID и UserID (подчинённого).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            DELETE FROM dbo.Task_Assignees
            WHERE TaskID = ? AND UserID = ?
        """
        cursor.execute(query, task_id, subordinate_id)
        conn.commit()
    finally:
        conn.close()


def delete_task(task_id: int):
    """
    Удаляет запись из таблицы Task по заданному TaskID.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            DELETE FROM dbo.Task
            WHERE TaskID = ?
        """
        cursor.execute(query, task_id)
        conn.commit()
    finally:
        conn.close()


def update_task_postponement(task_id: int, subordinate_id: int, new_deadline: datetime.datetime, status: str):
    """
    Обновляет поля PostponementOfDeadline и PostponementStatus в таблице Task_Assignees
    для записи с заданными TaskID и UserID.
    Поле UpdatedAt устанавливается в текущее время.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE dbo.Task_Assignees
            SET PostponementOfDeadline = ?, PostponementStatus = ?, UpdatedAt = GETDATE()
            WHERE TaskID = ? AND UserID = ?
        """
        cursor.execute(query, new_deadline, status, task_id, subordinate_id)
        conn.commit()
    finally:
        conn.close()


def query_task_details(task_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT TaskID, CreatorID, Text, StartOfTerm, Deadline
            FROM dbo.Task
            WHERE TaskID = ?
        """
        cursor.execute(query, task_id)
        row = cursor.fetchone()
        return row
    finally:
        conn.close()


def update_task_status(task_id: int, user_id: int, new_status: str):
    """
    Обновляет статус задания в таблице Task_Assignees для записи с заданными TaskID и UserID.
    Поле UpdatedAt устанавливается в текущее время.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE dbo.Task_Assignees
            SET Status = ?, UpdatedAt = GETDATE()
            WHERE TaskID = ? AND UserID = ?
        """
        cursor.execute(query, new_status, task_id, user_id)
        conn.commit()
    finally:
        conn.close()


def update_telegram_id(user_id: int, telegram_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE dbo.Users
            SET telegram_id = ?
            WHERE UserID = ?
        """
        cursor.execute(query, telegram_id, user_id)
        conn.commit()
    finally:
        conn.close()


async def fetch_telegram_id_by_user_id(user_id: int):
    def db_query(user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id FROM dbo.Users WHERE UserID = ?", user_id)
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    return await asyncio.to_thread(db_query, user_id)


async def fetch_subordinate_info(user_id: int):
    def db_query(user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.Fio, t.Type
            FROM dbo.Users u
            JOIN dbo.Type t ON u.TypeID = t.TypeID
            WHERE u.UserID = ?
        """, user_id)
        row = cursor.fetchone()
        conn.close()
        return {"FullName": row[0], "JobTitle": row[1]} if row else None

    return await asyncio.to_thread(db_query, user_id)


def get_tasks_with_deadline_in_range(target_start, target_end):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT t.TaskID, t.Text, t.Deadline, t.LastNotificationSent24, t.LastNotificationSent12, t.LastNotificationSent1, 
                   ta.UserID AS AssigneeID
            FROM dbo.Task t
            JOIN dbo.Task_Assignees ta ON t.TaskID = ta.TaskID
            WHERE t.Deadline BETWEEN ? AND ?
        """
        cursor.execute(query, target_start, target_end)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()



def update_last_notification_sent(task_id: int, now):
    """Вызывает хранимую процедуру для обновления LastNotificationSent"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("EXEC update_last_notification_sent ?, ?", task_id, now)
    conn.commit()

    cursor.close()
    conn.close()


def update_last_notification_sent_interval(task_id: int, interval: str, now: datetime.datetime):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("EXEC update_last_notification_sent_interval ?, ?, ?", task_id, interval, now)
    conn.commit()
    cursor.close()
    conn.close()


def get_overdue_tasks():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT t.TaskID, ta.UserID AS AssigneeID
            FROM dbo.Task t
            JOIN dbo.Task_Assignees ta ON t.TaskID = ta.TaskID
            WHERE t.Deadline < GETDATE() AND ta.Status = 'В процессе'
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def mark_task_overdue(task_id: int, assignee_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
            UPDATE dbo.Task_Assignees
            SET Status = 'Просрочено', UpdatedAt = GETDATE()
            WHERE TaskID = ? AND UserID = ?
        """
    cursor.execute(query, task_id, assignee_id)
    conn.commit()
    cursor.close()
    conn.close()


def get_report_for_subordinates(creator_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT 
                u.UserID, 
                u.Fio,
                t.Type AS Position,
                SUM(CASE WHEN ta.Status = 'Выполнено' THEN 1 ELSE 0 END) AS Completed,
                SUM(CASE WHEN ta.Status = 'Просрочено' THEN 1 ELSE 0 END) AS Overdue,
                SUM(CASE WHEN ta.PostponementOfDeadline IS NOT NULL THEN 1 ELSE 0 END) AS RequestedPostponement
            FROM dbo.Task_Assignees ta
            JOIN dbo.Task tsk ON ta.TaskID = tsk.TaskID
            JOIN dbo.Users u ON ta.UserID = u.UserID
            JOIN dbo.Type t ON u.TypeID = t.TypeID
            WHERE tsk.CreatorID = ?
            GROUP BY u.UserID, u.Fio, t.Type
        """
        cursor.execute(query, creator_id)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


async def fetch_report_for_subordinates(creator_id: int):
    return await asyncio.to_thread(get_report_for_subordinates, creator_id)


async def fetch_mark_task_overdue(task_id: int, assignee_id: int):
    await asyncio.to_thread(mark_task_overdue, task_id, assignee_id)



async def fetch_overdue_tasks():
    return await asyncio.to_thread(get_overdue_tasks)


async def fetch_update_last_notification_sent_interval(task_id: int, interval: str, now: datetime.datetime):
    await asyncio.to_thread(update_last_notification_sent_interval, task_id, interval, now)


async def fetch_update_telegram_id(user_id: int, telegram_id: int):
    return await asyncio.to_thread(update_telegram_id, user_id, telegram_id)


async def fetch_update_task_status(task_id: int, user_id: int, new_status: str):
    return await asyncio.to_thread(update_task_status, task_id, user_id, new_status)


async def fetch_task_details(task_id: int):
    return await asyncio.to_thread(query_task_details, task_id)


async def fetch_update_task_postponement(task_id: int, subordinate_id: int, new_deadline: datetime.datetime, status: str):
    return await asyncio.to_thread(update_task_postponement, task_id, subordinate_id, new_deadline, status)


async def fetch_delete_task(task_id: int):
    return await asyncio.to_thread(delete_task, task_id)


async def fetch_delete_task_assignee(task_id: int, subordinate_id: int):
    return await asyncio.to_thread(delete_task_assignee, task_id, subordinate_id)


async def fetch_update_task(task_id: int, new_text: str, new_deadline: datetime.datetime):
    await asyncio.to_thread(update_task, task_id, new_text, new_deadline)


async def fetch_update_task_for_deadline(task_id: int, new_deadline: datetime.datetime):
    return await asyncio.to_thread(update_task_for_deadline, task_id, new_deadline)


async def fetch_insert_task_assignee(task_id: int, user_id: int, status: str = "New"):
    return await asyncio.to_thread(insert_task_assignee, task_id, user_id, status)


async def fetch_user_by_login(login: str):
    return await asyncio.to_thread(query_user_by_login, login)


async def fetch_assigned_tasks(user_id: int):
    return await asyncio.to_thread(query_assigned_tasks, user_id)


async def fetch_user_by_subordinate(user_id: int, current_role: str):
    return await asyncio.to_thread(query_user_by_subordinate, user_id, current_role)


async def fetch_assigned_tasks_enumeration(subordinate_id: int, creator_id: int):
    return await asyncio.to_thread(query_assigned_tasks_enumeration, subordinate_id, creator_id)


async def fetch_assigned_tasks_enumeration_for_subordinates(subordinate_id: int):
    return await asyncio.to_thread(query_assigned_tasks_enumeration_for_subordinates, subordinate_id)


async def fetch_type_by_id(type_id: int):
    return await asyncio.to_thread(query_type_by_id, type_id)