
import configparser
from dataclasses import dataclass


@dataclass
class MaxConfig:
    token: str
    admin_user_id: int
    admin_username: str


@dataclass
class Config:
    max: MaxConfig
    json_filepath: str
    sqlite_filepath: str


def read_config(path: str) -> Config:
    parser = configparser.ConfigParser()

    if not parser.read(path, encoding="utf-8"):
        raise FileNotFoundError(
            f"Не удалось прочитать конфиг: {path}"
        )

    return Config(
        max=MaxConfig(
            token=parser["max"]["token"],
            admin_user_id=parser.getint(
                "max", "admin_user_id"
            ),
            admin_username=parser.get(
                "max",
                "admin_username",
                fallback="администратор"
            ),
        ),
        json_filepath=parser["files"]["json_filepath"],
        sqlite_filepath=parser["files"]["sqlite_filepath"],
    )
