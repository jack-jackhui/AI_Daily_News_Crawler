from processors.llm_reranker import re_rank_and_summarize_with_llm
from processors.formatter import format_summary
from outputs.telegram_sender import send_to_telegram
from outputs.wechat_sender import send_to_wechat
from outputs.wordpress_publisher import publish_daily_news_to_wordpress
from outputs.twitter_publisher import publish_tweet_for_blog_post, generate_tweet_content
from outputs.threads_publisher import publish_thread_for_blog_post
from utils.threads_token_manager import validate_and_refresh_token
# from outputs.local_storage import save_summary_to_file
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

# Category ID for the "Daily AI News" category in WordPress
DAILY_AI_NEWS_CATEGORY_ID = 103  # Replace with the actual category ID


async def run_pipeline():
    try:
        # Pre-validate Threads token at startup (auto-refreshes if expiring soon)
        logger.info("🔐 Validating API tokens...")
        threads_ok, threads_msg, _ = validate_and_refresh_token(auto_update_env=True)
        logger.info(f"   Threads: {threads_msg}")

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

        if not re_ranked_and_summarized_articles:
            logger.error(
                "❌ LLM produced no validated summaries. Aborting before any output is written or published."
            )
            return

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

        # 6. Send the formatted summary to WeChat
        logger.info("📲 Sending the summary to WeChat...")
        send_to_wechat(formatted_summary)  # Call send_to_wechat function from wechat_sender.py
        logger.info("Summary sent to WeChat successfully.")

        # 7. Publish the daily news summary to WordPress
        logger.info("🌐 Publishing the daily news summary to WordPress...")
        wordpress_response = publish_daily_news_to_wordpress(
            news_content=formatted_summary,
            post_title="Daily Tech & AI News Digest",
            category_id=DAILY_AI_NEWS_CATEGORY_ID,
        )

        if wordpress_response:
            blog_post_url = wordpress_response.get("link")
            logger.info(f"✅ Blog post published successfully. URL: {blog_post_url}")

            # 8. Generate content for Twitter and Threads
            logger.info("🐦 Generating content for Twitter and Threads...")
            tweet_content = generate_tweet_content(blog_post_url)

            # Publish tweet
            logger.info("🐦 Publishing a tweet for the daily news digest...")
            tweet_success = publish_tweet_for_blog_post(tweet_content)
            if tweet_success:
                logger.info("✅ Tweet published successfully.")
            else:
                logger.warning("⚠️ Tweet publishing failed. Check Twitter API credentials.")

            # Publish Threads post
            logger.info("📤 Publishing a Threads post for the daily news digest...")
            threads_success = publish_thread_for_blog_post(blog_post_url, tweet_content)
            if threads_success:
                logger.info("✅ Threads post published successfully.")
            else:
                logger.warning("⚠️ Threads publishing failed. Check Threads API access token.")
        else:
            logger.error("❌ Failed to publish the daily news summary to WordPress. Skipping tweet.")

        logger.info("🎉 Pipeline complete.")

    except Exception as e:
        logger.error(f"❌ Error occurred while running the pipeline: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
