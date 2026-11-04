from bot.bot_interface import BotInterface
from bot.telegram import TelebotApi
from repository.json import JsonRepository
from config import Config, read_config


def main():
    config_path ="config.ini"
    config = read_config(config_path)

    repo = JsonRepository(config.json_filepath)
    # repo = SqlRepository(config.sqlite_filepath)

    service: BotInterface = TelebotApi(
        config.telegram.token,
        config.telegram.admin_chat_id,
        config.telegram.admin_username,
        repo,
    )
    service.run()


if __name__ == "__main__":
    main()
