# outputs/telegram_sender.py
import os
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class TelegramBot:
    """Telegram bot for sending messages asynchronously."""
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    async def send_message(self, message: str):
        """Sends a message to the configured chat ID asynchronously."""
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown")
            print(f"Message sent to Telegram successfully: {message[:50]}...")
        except Exception as e:
            print(f"Failed to send message to Telegram: {e}")

# Global instance for ease of use
telegram_bot = TelegramBot(token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID)

async def send_to_telegram(text: str):
    """Wrapper function for sending messages via the Telegram bot."""
    await telegram_bot.send_message(text)