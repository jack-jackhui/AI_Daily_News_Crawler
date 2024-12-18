import os
import logging
import requests
from dotenv import load_dotenv

# 🛠️ Load environment variables from .env file
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)


def send_to_wechat(message):
    """Send a message to a WeChat group via the /send_message API endpoint"""
    try:
        wechat_api_url = os.getenv("WECHAT_BOT_URL", "http://localhost:5000/send_message")  # Get API URL from .env
        wechat_api_key = os.getenv("WECHAT_API_KEY", "default_secure_key")  # Get API key from .env
        group_name = os.getenv("WECHAT_GROUP_NAME", "AI Chat Test Group")  # Get WeChat group name from .env

        if not wechat_api_url or not wechat_api_key or not group_name:
            logger.error("❌ Missing required environment variables: WECHAT_API_URL, WECHAT_API_KEY, or WECHAT_GROUP_NAME.")
            return

        logger.info(f"🌐 Sending message to WeChat group '{group_name}' via API...")

        headers = {
            "Authorization": f"Bearer {wechat_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "group_name": group_name,
            "message": message
        }

        response = requests.post(wechat_api_url, headers=headers, json=data)
        if response.status_code == 200:
            logger.info(f"✅ Successfully sent message to WeChat group '{group_name}'")
        else:
            logger.error(f"❌ Failed to send message to WeChat. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        logger.error(f"❌ Error occurred while sending message to WeChat: {str(e)}")
