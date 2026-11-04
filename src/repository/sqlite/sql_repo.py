import sqlite3
import time
from datetime import datetime

from domain import Student


class SqlRepository:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name  TEXT NOT NULL,
                school     TEXT NOT NULL,
                class      TEXT NOT NULL,
                balance    INTEGER DEFAULT 0,
                level      TEXT DEFAULT 'Нуб',
                xp         INTEGER DEFAULT 0,
                xp_next    INTEGER DEFAULT 100
            );

            CREATE TABLE IF NOT EXISTS task_reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                task_id     INTEGER NOT NULL,
                task_name   TEXT NOT NULL,
                report_type TEXT NOT NULL,
                report_text TEXT,
                report_file TEXT,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT NOT NULL,
                reviewed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                item_name   TEXT NOT NULL,
                price       INTEGER NOT NULL,
                created_at  TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def get_student_by_id(self, user_id: int) -> Student:
        cur = self.conn.execute("SELECT * FROM users WHERE user_id = ?", (int(user_id),))
        row = cur.fetchone()
        if row is None:
            return None
        return Student(
            user_id=row["user_id"], first_name=row["first_name"],
            last_name=row["last_name"], school=row["school"],
            class_name=row["class"], balance=row["balance"],
            level=row["level"], xp=row["xp"], xp_next=row["xp_next"],
        )

    def save_student(self, user: Student):
        self.conn.execute('''
            INSERT INTO users (user_id, first_name, last_name, school, class, balance, level, xp, xp_next)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                school     = excluded.school,
                class      = excluded.class,
                balance    = excluded.balance,
                level      = excluded.level,
                xp         = excluded.xp,
                xp_next    = excluded.xp_next
        ''', (
            int(user.user_id), user.first_name, user.last_name,
            user.school, user.class_name,
            user.balance, user.level,
            user.xp, user.xp_next,
        ))
        self.conn.commit()

    def update_balance(self, user_id, delta):
        self.conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?",
                          (delta, int(user_id)))
        self.conn.commit()

    def update_progress(self, user_id, add_xp: int, add_balance: int = 0):
        user = self.get_student_by_id(user_id)
        if not user:
            return
        xp = user.xp + add_xp
        balance = user.balance + add_balance
        level, xp, xp_next = self._calc_level(xp)
        self.conn.execute(
            "UPDATE users SET xp=?, balance=?, level=?, xp_next=? WHERE user_id=?",
            (xp, balance, level, xp_next, int(user_id))
        )
        self.conn.commit()

    @staticmethod
    def _calc_level(xp):
        if xp < 100:
            return "Нуб", xp, 100
        if xp < 1000:
            return "Про", xp, 1000
        return "Хакер", xp, 5000

    def create_report(self, user_id, task_id, task_name, report_type, report_text=None, report_file=None):
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute('''
            INSERT INTO task_reports (user_id, task_id, task_name, report_type, report_text, report_file, status, created_at)
            VALUES (?,?,?,?,?,?, 'pending', ?)
        ''', (int(user_id), task_id, task_name, report_type, report_text, report_file, now))
        self.conn.commit()
        return cur.lastrowid

    def get_report(self, report_id):
        cur = self.conn.execute("SELECT * FROM task_reports WHERE id = ?", (int(report_id),))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_pending_reports(self):
        cur = self.conn.execute("SELECT * FROM task_reports WHERE status='pending' ORDER BY id DESC")
        return [dict(r) for r in cur.fetchall()]

    def get_report_history(self, limit=50):
        cur = self.conn.execute(
            "SELECT * FROM task_reports WHERE status != 'pending' ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return [dict(r) for r in cur.fetchall()]

    def set_report_status(self, report_id, status: str):
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute("UPDATE task_reports SET status=?, reviewed_at=? WHERE id=?",
                          (status, now, int(report_id)))
        self.conn.commit()

    def has_recent_rejected(self, user_id, task_id, cooldown=300):
        cur = self.conn.execute(
            "SELECT reviewed_at FROM task_reports WHERE user_id=? AND task_id=? AND status='rejected' "
            "ORDER BY id DESC LIMIT 1", (int(user_id), task_id)
        )
        row = cur.fetchone()
        if not row or not row["reviewed_at"]:
            return False, 0
        ts = datetime.fromisoformat(row["reviewed_at"]).timestamp()
        elapsed = time.time() - ts
        return elapsed < cooldown, int(cooldown - elapsed)

    def has_pending_for(self, user_id, task_id):
        cur = self.conn.execute(
            "SELECT 1 FROM task_reports WHERE user_id=? AND task_id=? AND status='pending' LIMIT 1",
            (int(user_id), task_id)
        )
        return cur.fetchone() is not None

    def add_purchase(self, user_id, item_name, price):
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO purchases (user_id, item_name, price, created_at) VALUES (?,?,?,?)",
            (int(user_id), item_name, price, now)
        )
        self.conn.commit()
