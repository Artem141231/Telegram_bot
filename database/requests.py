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
        WHERE t.CreatorID = ? OR ta.UserID = ?
        """
        cursor.execute(query, user_id, user_id)
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def query_user_by_subordinate(user_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Users.UserID, Users.Fio, Type.Type "
            "FROM Users JOIN Type ON Users.TypeID = Type.TypeID "
            "WHERE Users.UserID != ?",
            (user_id,)
        )
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
    """
    Вставляет запись в таблицу Task_Assignees.
    status — статус задачи для подчинённого, по умолчанию "New".
    Поля AssignedAt и UpdatedAt устанавливаются в текущее время.
    PostponementOfDeadline и PostponementStatus оставляем NULL.
    Возвращает сгенерированный AssignmentID.
    """
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


async def fetch_update_task(task_id: int, new_text: str, new_deadline: datetime.datetime):
    await asyncio.to_thread(update_task, task_id, new_text, new_deadline)


async def fetch_insert_task_assignee(task_id: int, user_id: int, status: str = "New"):
    return await asyncio.to_thread(insert_task_assignee, task_id, user_id, status)


async def fetch_user_by_login(login: str):
    return await asyncio.to_thread(query_user_by_login, login)


async def fetch_assigned_tasks(user_id: int):
    return await asyncio.to_thread(query_assigned_tasks, user_id)


async def fetch_user_by_subordinate(user_id: int):
    return await asyncio.to_thread(query_user_by_subordinate, user_id)
