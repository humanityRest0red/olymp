from abc import ABC, abstractmethod

class BotInterface(ABC):
    def __init__(self, api_token: str):
        self.api_token = api_token

    def Run(self)-> None:
        pass

    @abstractmethod
    async def get_updates(self, updates) -> None:
        """Обрабатывает входящие обновления от платформы (Telegram, VK и т.д.)."""
        pass

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        """Отправляет сообщение пользователю."""
        pass
