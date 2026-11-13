class SqlRepository:
    def __init__(self, path: str = SQL_PATH):
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
                xp_next    INTEGER DEFAULT 100,
                username   TEXT
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
        # Миграция для старых баз (добавление username)
        try:
            self.conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def get_user(self, user_id) -> Student | None:
        cur = self.conn.execute("SELECT * FROM users WHERE user_id = ?", (int(user_id),))
        row = cur.fetchone()
        if row:
            d = dict(row)
            d['class_name'] = d.pop('class')
            return Student(**d)
        return None

    def save_user(self, user: Student):
        self.conn.execute('''
            INSERT INTO users (user_id, first_name, last_name, school, class, balance, level, xp, xp_next, username)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                school     = excluded.school,
                class      = excluded.class,
                balance    = excluded.balance,
                level      = excluded.level,
                xp         = excluded.xp,
                xp_next    = excluded.xp_next,
                username   = excluded.username
        ''', (
            user.user_id, user.first_name, user.last_name,
            user.school, user.class_name, user.balance,
            user.level, user.xp, user.xp_next, user.username
        ))
        self.conn.commit()

    def update_user(self, user: Student):
        self.save_user(user)

    def get_top_balance(self, limit=10) -> List[Student]:
        cur = self.conn.execute("SELECT * FROM users ORDER BY balance DESC LIMIT ?", (limit,))
        res = []
        for r in cur.fetchall():
            d = dict(r)
            d['class_name'] = d.pop('class')
            res.append(Student(**d))
        return res

    def get_top_tasks(self, limit=10) -> List[tuple]:
        cur = self.conn.execute("""
            SELECT u.*, COUNT(tr.id) as completed_tasks 
            FROM users u 
            JOIN task_reports tr ON u.user_id = tr.user_id 
            WHERE tr.status = 'approved' 
            GROUP BY u.user_id 
            ORDER BY completed_tasks DESC 
            LIMIT ?
        """, (limit,))
        res = []
        for r in cur.fetchall():
            d = dict(r)
            d['class_name'] = d.pop('class')
            count = d.pop('completed_tasks')
            res.append((Student(**d), count))
        return res

    def create_report(self, report: TaskReport) -> int:
        cur = self.conn.execute('''
            INSERT INTO task_reports (user_id, task_id, task_name, report_type, report_text, report_file, status, created_at, reviewed_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            report.user_id, report.task_id, report.task_name,
            report.report_type, report.report_text, report.report_file,
            report.status, report.created_at, report.reviewed_at
        ))
        self.conn.commit()
        return cur.lastrowid

    def get_report(self, report_id) -> TaskReport | None:
        cur = self.conn.execute("SELECT * FROM task_reports WHERE id = ?", (int(report_id),))
        row = cur.fetchone()
        return TaskReport(**dict(row)) if row else None

    def get_pending_reports(self) -> List[TaskReport]:
        cur = self.conn.execute("SELECT * FROM task_reports WHERE status='pending' ORDER BY id DESC")
        return [TaskReport(**dict(r)) for r in cur.fetchall()]

    def get_report_history(self, limit=50) -> List[TaskReport]:
        cur = self.conn.execute(
            "SELECT * FROM task_reports WHERE status != 'pending' ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return [TaskReport(**dict(r)) for r in cur.fetchall()]

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

    def add_purchase(self, purchase: Purchase):
        self.conn.execute(
            "INSERT INTO purchases (user_id, item_name, price, created_at) VALUES (?,?,?,?)",
            (purchase.user_id, purchase.item_name, purchase.price, purchase.created_at)
        )
        self.conn.commit()