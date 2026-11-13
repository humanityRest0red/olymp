from datetime import datetime
import json
import os
import time

from domain import Purchase, Student, TaskReport

class JsonRepository:
    def __init__(self, path):
        self.path = path
        self._ensure_file()

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

    def get_user(self, user_id) -> Student | None:
        data = self._read()
        u = data["users"].get(str(user_id))
        if u:
            u['class_name'] = u.pop('class', '')
            return Student(**u)
        return None

    def save_user(self, user: Student):
        data = self._read()
        u_dict = asdict(user)
        u_dict['class'] = u_dict.pop('class_name')
        data["users"][str(user.user_id)] = u_dict
        self._write(data)

    def update_user(self, user: Student):
        self.save_user(user)

    def get_top_balance(self, limit=10) -> list[Student]:
        data = self._read()
        users = []
        for u in data["users"].values():
            d = u.copy()
            d['class_name'] = d.pop('class', '')
            users.append(Student(**d))
        users.sort(key=lambda x: x.balance, reverse=True)
        return users[:limit]

    def get_top_tasks(self, limit=10) -> list[tuple]:
        data = self._read()
        counts = {}
        for r in data["task_reports"]:
            if r["status"] == "approved":
                counts[r["user_id"]] = counts.get(r["user_id"], 0) + 1

        result = []
        for uid, count in counts.items():
            u = data["users"].get(str(uid))
            if u:
                d = u.copy()
                d['class_name'] = d.pop('class', '')
                result.append((Student(**d), count))

        result.sort(key=lambda x: x[1], reverse=True)
        return result[:limit]

    def create_report(self, report: TaskReport) -> int:
        data = self._read()
        report.id = self._next_id(data, "report_id")
        data["task_reports"].append(asdict(report))
        self._write(data)
        return report.id

    def get_report(self, report_id) -> TaskReport | None:
        data = self._read()
        for r in data["task_reports"]:
            if r["id"] == int(report_id):
                return TaskReport(**r)
        return None

    def get_pending_reports(self) -> list[TaskReport]:
        data = self._read()
        return [TaskReport(**r) for r in data["task_reports"] if r["status"] == "pending"][::-1]

    def get_report_history(self, limit=50) -> list[TaskReport]:
        data = self._read()
        hist = [TaskReport(**r) for r in data["task_reports"] if r["status"] != "pending"]
        return hist[::-1][:limit]

    def set_report_status(self, report_id, status: str) -> None:
        data = self._read()
        for r in data["task_reports"]:
            if r["id"] == int(report_id):
                r["status"] = status
                r["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
                break
        self._write(data)

    def has_recent_rejected(self, user_id, task_id, cooldown=300) -> (bool, int):
        data = self._read()
        latest = None
        for r in data["task_reports"]:
            if (r["user_id"] == int(user_id) and r["task_id"] == task_id
                    and r["status"] == "rejected" and r.get("reviewed_at")):
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
            if r["user_id"] == int(user_id) and r["task_id"] == task_id and r["status"] == "pending":
                return True
        return False

    def add_purchase(self, purchase: Purchase):
        data = self._read()
        purchase.id = self._next_id(data, "purchase_id")
        data["purchases"].append(asdict(purchase))
        self._write(data)