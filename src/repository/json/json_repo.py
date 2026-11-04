import time
from datetime import datetime
import json
import os

from domain import Student

class JsonRepository:
    """Хранилище всех данных в hackatonusers.json."""

    def __init__(self, path: str = "hackatonusers.json"):
        self.path = path
        self._ensure_file()

    # ---------- служебное ----------
    def _ensure_file(self):
        if not os.path.exists(self.path):
            self._write({
                "users": {},
                "task_reports": [],
                "purchases": [],
                "counters": {"report_id": 0, "purchase_id": 0},
            })

    def _read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {}
        # гарантируем структуру
        data.setdefault("users", {})
        data.setdefault("task_reports", [])
        data.setdefault("purchases", [])
        data.setdefault("counters", {"report_id": 0, "purchase_id": 0})
        return data

    def _write(self, data: dict):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _next_id(self, data: dict, key: str) -> int:
        data["counters"][key] = data["counters"].get(key, 0) + 1
        return data["counters"][key]

    # ---------- users ----------
    def get_student_by_id(self, user_id):
        data = self._read()["users"].get(str(user_id))
        if not data:
            return None
        return Student(
            user_id=int(data["user_id"]),
            first_name=data["first_name"],
            last_name=data["last_name"],
            school=data["school"],
            class_name=data["class"],
            balance=data.get("balance", 0),
            level=data.get("level", "Нуб"),
            xp=data.get("xp", 0),
            xp_next=data.get("xp_next", 100),
        )

    def save_student(self, user: Student):
        data = self._read()
        data["users"][str(user.user_id)] = {
            "user_id": user.user_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "school": user.school,
            "class": user.class_name,
            "balance": user.balance,
            "level": user.level,
            "xp": user.xp,
            "xp_next": user.xp_next,
        }
        self._write(data)

    def update_balance(self, user_id, delta):
        user = self.get_student_by_id(user_id)
        if user is not None:
            user.change_balance(delta)
            self.save_student(user)

    def update_progress(self, user_id, add_xp: int, add_balance: int = 0):
        user = self.get_student_by_id(user_id)
        if user is not None:
            user.add_progress(add_xp, add_balance)
            self.save_student(user)

    # ---------- task_reports ----------
    def create_report(self, user_id, task_id, task_name, report_type,
                      report_text=None, report_file=None):
        data = self._read()
        rid = self._next_id(data, "report_id")
        data["task_reports"].append({
            "id": rid,
            "user_id": int(user_id),
            "task_id": task_id,
            "task_name": task_name,
            "report_type": report_type,
            "report_text": report_text,
            "report_file": report_file,
            "status": "pending",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "reviewed_at": None,
        })
        self._write(data)
        return rid

    def get_report(self, report_id):
        data = self._read()
        for r in data["task_reports"]:
            if r["id"] == int(report_id):
                return r
        return None

    def get_pending_reports(self):
        data = self._read()
        return [r for r in data["task_reports"] if r["status"] == "pending"][::-1]

    def get_report_history(self, limit=50):
        data = self._read()
        hist = [r for r in data["task_reports"] if r["status"] != "pending"]
        return hist[::-1][:limit]

    def set_report_status(self, report_id, status: str):
        data = self._read()
        for r in data["task_reports"]:
            if r["id"] == int(report_id):
                r["status"] = status
                r["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
                break
        self._write(data)

    def has_recent_rejected(self, user_id, task_id, cooldown=300):
        data = self._read()
        latest = None
        for r in data["task_reports"]:
            if (r["user_id"] == int(user_id)
                    and r["task_id"] == task_id
                    and r["status"] == "rejected"
                    and r.get("reviewed_at")):
                if latest is None or r["reviewed_at"] > latest["reviewed_at"]:
                    latest = r
        if not latest:
            return False, 0
        ts = datetime.fromisoformat(latest["reviewed_at"]).timestamp()
        elapsed = time.time() - ts
        return elapsed < cooldown, int(cooldown - elapsed)

    def has_pending_for(self, user_id, task_id):
        data = self._read()
        for r in data["task_reports"]:
            if (r["user_id"] == int(user_id)
                    and r["task_id"] == task_id
                    and r["status"] == "pending"):
                return True
        return False

    # ---------- purchases ----------
    def add_purchase(self, user_id, item_name, price):
        data = self._read()
        pid = self._next_id(data, "purchase_id")
        data["purchases"].append({
            "id": pid,
            "user_id": int(user_id),
            "item_name": item_name,
            "price": price,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
        self._write(data)
