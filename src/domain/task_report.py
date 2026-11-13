from dataclasses import dataclass

@dataclass
class TaskReport:
    user_id: int
    task_id: int
    task_name: str
    report_type: str
    report_text: str | None = None
    report_file: str | None = None
    id: int | None  = None
    status: str = "pending"
    created_at: str = None
    reviewed_at: str | None = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat(timespec="seconds")

