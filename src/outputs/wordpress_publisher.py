import logging
import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure WordPress site credentials are available
WORDPRESS_SITE = os.getenv("WORDPRESS_SITE")
WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD")

# Validate the required environment variables
if not all([WORDPRESS_SITE, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD]):
    raise ValueError("One or more required environment variables are missing. Ensure WORDPRESS_SITE, WORDPRESS_USERNAME, and WORDPRESS_APP_PASSWORD are set.")

# Set up logging
logger = logging.getLogger(__name__)


def create_blog_post(title, content, categories=None, tags=None, status="publish"):
    """
    Create a new blog post on WordPress.

    Args:
        title (str): The title of the blog post.
        content (str): The HTML content of the blog post.
        categories (list, optional): List of category IDs to assign to the post.
        tags (list, optional): List of tag IDs to assign to the post.
        status (str, optional): The status of the post. Default is 'publish'.

    Returns:
        dict: The response data from the WordPress API.
    """
    try:
        # Define the WordPress post creation endpoint
        post_url = f"{WORDPRESS_SITE}/wp-json/wp/v2/posts"

        # Format the post data
        post_data = {
            "title": title,
            "content": content,
            "status": status,  # 'publish', 'draft', or 'pending'
        }

        if categories:
            post_data["categories"] = categories
        if tags:
            post_data["tags"] = tags

        # Send the request to create the post
        response = requests.post(
            post_url,
            json=post_data,
            auth=HTTPBasicAuth(WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD)
        )

        # Log the response for debugging
        logger.debug(f"Create post response status code: {response.status_code}")
        if response.status_code != 201:
            logger.error(f"Failed to create blog post. Response content: {response.text}")
            return None

        try:
            post_data = response.json()
            logger.info("🎉 Blog post created successfully:", post_data)
            return post_data
        except ValueError as e:
            logger.exception(f"Failed to parse JSON response for blog post: {e}")
            logger.debug(f"Response text: {response.text}")
            return None
    except Exception as e:
        logger.exception(f"❌ Error in create_blog_post: {e}")
        return None


def publish_daily_news_to_wordpress(news_content, post_title="Daily Tech & AI News Digest", category_id=None):
    """
    Publishes the daily news content to WordPress.

    Args:
        news_content (str): The formatted news content to be published as the blog post body.
        post_title (str, optional): The title of the blog post. Defaults to 'Daily Tech & AI News Digest'.

    Returns:
        dict: The response data from the WordPress API.
    """
    try:
        logger.info(f"📡 Publishing '{post_title}' to WordPress...")

        # Create the blog post with the specified title and content
        response_data = create_blog_post(title=post_title, content=news_content, categories=[category_id] if category_id else None)

        if response_data:
            post_url = response_data.get("link")
            logger.info(f"🎉 Successfully published blog post! View it at {post_url}")
        else:
            logger.error("❌ Failed to publish the blog post to WordPress.")

        return response_data
    except Exception as e:
        logger.exception(f"❌ Error in publish_daily_news_to_wordpress: {e}")
        return None
