import configparser
from dataclasses import dataclass


@dataclass
class Telegram:
    token: str
    admin_chat_id: int
    admin_username: str


@dataclass
class Config:
    telegram: Telegram
    json_filepath: str
    sqlite_filepath: str


def read_config(path: str) -> Config:
    parser = configparser.ConfigParser()

    if not parser.read(path, encoding="utf-8"):
        raise FileNotFoundError(f"Не удалось прочитать конфиг: {path}")

    telegram = Telegram(
        token=parser["telegram"]["token"],
        admin_chat_id=parser.getint("telegram", "admin_chat_id"),
        admin_username=parser["telegram"]["admin_username"],
    )

    return Config(
        telegram=telegram,
        json_filepath=parser["files"]["json_filepath"],
        sqlite_filepath=parser["files"]["sqlite_filepath"],
    )
