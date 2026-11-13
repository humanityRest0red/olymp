
import logging

from bot.max import MaxBotApi
from repository.json import JsonRepository
from config import read_config


def main():
    logging.basicConfig(level=logging.INFO)

    config = read_config("config.ini")
    repo = JsonRepository(config.json_filepath)

    bot = MaxBotApi(
        config.max.token,
        config.max.admin_user_id,
        config.max.admin_username,
        repo,
    )

    bot.run()


if __name__ == "__main__":
    main()
