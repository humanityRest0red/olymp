from dataclasses import dataclass


@dataclass
class Purchase:
    user_id: int
    item_name: str
    price: float
    id: int | None = None
    created_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat(timespec="seconds")
