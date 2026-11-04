from dataclasses import dataclass


@dataclass
class Student:
    user_id: int
    first_name: str
    last_name: str
    school: str
    class_name: str
    balance: int = 0
    level: str = "Нуб"
    xp: int = 0
    xp_next: int = 100

    def change_balance(self, delta: int) -> None:
        self.balance += delta

    def add_progress(self, add_xp: int, add_balance: int) -> None:
        self.xp += add_xp
        self.balance += add_balance
        if self.xp < 100:
            self.level, self.xp_next = "Нуб", 100
        elif self.xp < 1000:
            self.level, self.xp_next = "Про", 1000
        else:
            self.level, self.xp_next = "Хакер", 5000
