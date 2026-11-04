from abc import ABC, abstractmethod
from typing import Any

from domain import Student


class RepositoryInterface(ABC):
    @abstractmethod
    def get_student_by_id(self, user_id: int) -> Student | None:
        ...

    @abstractmethod
    def save_student(self, student: Student) -> None:
        ...

    @abstractmethod
    def update_balance(self, user_id: int, delta: int) -> None:
        ...

    @abstractmethod
    def update_progress(
        self,
        user_id: int,
        add_xp: int,
        add_balance: int = 0,
    ) -> None:
        ...

    @abstractmethod
    def create_report(
        self,
        user_id: int,
        task_id: int,
        task_name: str,
        report_type: str,
        report_text: str | None = None,
        report_file: str | None = None,
    ) -> int:
        ...

    @abstractmethod
    def get_report(self, report_id: int) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def get_pending_reports(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_report_history(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def set_report_status(self, report_id: int, status: str) -> None:
        ...

    @abstractmethod
    def has_recent_rejected(
        self,
        user_id: int,
        task_id: int,
        cooldown: int = 300,
    ) -> tuple[bool, int]:
        ...

    @abstractmethod
    def has_pending_for(self, user_id: int, task_id: int) -> bool:
        ...

    @abstractmethod
    def add_purchase(
        self,
        user_id: int,
        item_name: str,
        price: int,
    ) -> int:
        ...
