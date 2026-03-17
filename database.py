import sqlite3

DB_NAME = "members.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            first_name TEXT,
            username TEXT,
            is_bot INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)

    conn.commit()
    conn.close()


def add_member(chat_id, user_id, first_name, username, is_bot):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO members (chat_id, user_id, first_name, username, is_bot)
        VALUES (?, ?, ?, ?, ?)
    """, (chat_id, user_id, first_name, username, int(is_bot)))

    conn.commit()
    conn.close()


def remove_member(chat_id, user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM members WHERE chat_id = ? AND user_id = ?
    """, (chat_id, user_id))

    conn.commit()
    conn.close()


def get_members(chat_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, first_name, username, is_bot
        FROM members
        WHERE chat_id = ? AND is_bot = 0
        ORDER BY first_name COLLATE NOCASE
    """, (chat_id,))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "user_id": row[0],
            "first_name": row[1] or "Kullanıcı",
            "username": row[2] or "",
            "is_bot": bool(row[3]),
        }
        for row in rows
    ]


def get_member_count(chat_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM members
        WHERE chat_id = ? AND is_bot = 0
    """, (chat_id,))

    count = cur.fetchone()[0]
    conn.close()
    return count
