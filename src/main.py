from processors.llm_reranker import re_rank_and_summarize_with_llm
from processors.formatter import format_summary
from outputs.telegram_sender import send_to_telegram
from outputs.local_storage import save_summary_to_file
from fetchers.rss_fetcher import fetch_rss_feeds
from config import SITES_CONFIG
import asyncio
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(__file__))


# 🛠️ Configure Logger for Console Output
logging.basicConfig(
    level=logging.INFO,  # Set log level to DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Log format
    handlers=[logging.StreamHandler()],  # Log to the console
)
# Set up logger
logger = logging.getLogger(__name__)


async def run_pipeline():
    try:
        logger.info("📡 Fetching articles from RSS feeds...")
        rss_feed_urls = SITES_CONFIG

        # Call fetch_rss_feeds to get the articles
        articles = fetch_rss_feeds(rss_feed_urls, max_to_rank=20)

        if not articles:
            logger.warning("❌ No articles were fetched. Exiting pipeline.")
            return

        # 3. Sending articles to LLM for re-ranking and summarization
        print("🔍 Sending articles to LLM for re-ranking and summarization...")
        re_ranked_and_summarized_articles = re_rank_and_summarize_with_llm(
            articles)

        # 4. Formating output
        logger.info("🎉 Formatting the summarized articles for display...")
        formatted_summary = format_summary(re_ranked_and_summarized_articles)

        # 4. Save the formatted summary to a local file
        logger.info("💾 Saving the summary to a local file...")
        summary_dir = os.path.join(os.path.dirname(__file__), "daily_summary")
        os.makedirs(summary_dir, exist_ok=True)
        file_name = f"{datetime.now().strftime('%Y-%m-%d')}_daily_summary.txt"
        file_path = os.path.join(summary_dir, file_name)

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(formatted_summary)

        logger.info(f"Summary saved successfully to {file_path}")

        # 5. Send the formatted summary to Telegram
        logger.info("📲 Sending the summary to Telegram...")
        await send_to_telegram(formatted_summary)
        logger.info("Summary sent to Telegram successfully.")

        logger.info("🎉 Pipeline complete.")
    except Exception as e:
        logger.error(f"❌ Error occurred while running the pipeline: {str(e)}")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
