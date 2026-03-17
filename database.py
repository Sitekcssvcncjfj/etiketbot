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
            is_admin INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)

    conn.commit()
    conn.close()


def add_or_update_member(chat_id, user_id, first_name, username, is_bot, is_admin=0):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO members (chat_id, user_id, first_name, username, is_bot, is_admin)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET
            first_name=excluded.first_name,
            username=excluded.username,
            is_bot=excluded.is_bot,
            is_admin=excluded.is_admin
    """, (chat_id, user_id, first_name, username, int(is_bot), int(is_admin)))

    conn.commit()
    conn.close()


def remove_member(chat_id, user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM members WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))

    conn.commit()
    conn.close()


def clear_admin_flags(chat_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE members SET is_admin = 0 WHERE chat_id = ?", (chat_id,))

    conn.commit()
    conn.close()


def get_members(chat_id, include_bots=False):
    conn = get_connection()
    cur = conn.cursor()

    if include_bots:
        cur.execute("""
            SELECT user_id, first_name, username, is_bot, is_admin
            FROM members
            WHERE chat_id = ?
            ORDER BY first_name COLLATE NOCASE
        """, (chat_id,))
    else:
        cur.execute("""
            SELECT user_id, first_name, username, is_bot, is_admin
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
            "is_admin": bool(row[4]),
        }
        for row in rows
    ]


def get_admin_members(chat_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, first_name, username, is_bot, is_admin
        FROM members
        WHERE chat_id = ? AND is_bot = 0 AND is_admin = 1
        ORDER BY first_name COLLATE NOCASE
    """, (chat_id,))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "user_id": row[0],
            "first_name": row[1] or "Admin",
            "username": row[2] or "",
            "is_bot": bool(row[3]),
            "is_admin": bool(row[4]),
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


def search_members(chat_id, keyword):
    conn = get_connection()
    cur = conn.cursor()

    pattern = f"%{keyword.lower()}%"

    cur.execute("""
        SELECT user_id, first_name, username, is_bot, is_admin
        FROM members
        WHERE chat_id = ?
          AND is_bot = 0
          AND (
            LOWER(first_name) LIKE ?
            OR LOWER(username) LIKE ?
          )
        ORDER BY first_name COLLATE NOCASE
    """, (chat_id, pattern, pattern))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "user_id": row[0],
            "first_name": row[1] or "Kullanıcı",
            "username": row[2] or "",
            "is_bot": bool(row[3]),
            "is_admin": bool(row[4]),
        }
        for row in rows
    ]
