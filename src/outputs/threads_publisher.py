import os
import logging
import requests
import time
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Threads API Credentials
THREADS_USER_ID = os.getenv("THREADS_USER_ID")  # Replace with your Threads user ID
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")  # Access token for Threads Graph API

# Azure OpenAI API Credentials
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

def create_openai_client():
    """Initialize and return the Azure OpenAI client."""
    try:
        return AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
        )
    except Exception as e:
        logger.error(f"❌ Failed to initialize Azure OpenAI client: {e}")
        raise

def generate_thread_content(blog_post_url):
    """Generate a Threads post content using Azure OpenAI."""
    client = create_openai_client()

    # System and user prompts
    system_prompt = (
        "You are an expert at crafting concise and engaging posts for social media. Generate a post "
        "to announce the release of a daily AI news digest, including a provided blog link. "
        "Ensure the content is compelling, under 500 characters, and ends with #DailyAINews."
    )
    user_prompt = f"Blog post link: {blog_post_url}"

    try:
        logger.info("🧠 Generating Threads post content using Azure OpenAI...")
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="gpt-4o",  # Replace with the correct model
            temperature=1,
            max_tokens=500,
        )
        thread_content = response.choices[0].message.content.strip()
        logger.info(f"Azure OpenAI response: {thread_content}")
        return thread_content
    except Exception as e:
        logger.error(f"❌ Failed to generate Threads post content: {e}")
        raise

def create_threads_media_container(post_content, blog_post_url):
    """
    Step 1: Create a Threads media container.

    Args:
        post_content (str): The text content for the post.
        blog_post_url (str): The URL to be included in the post.

    Returns:
        str: The creation ID of the media container.
    """
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        logger.error("❌ Threads API configuration is missing. Check environment variables.")
        raise ValueError("Threads API configuration is missing.")

    try:
        # Define the Threads API endpoint for media container creation
        threads_endpoint = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"

        # Prepare payload
        payload = {
            "access_token": THREADS_ACCESS_TOKEN,
            "media_type": "TEXT",
            "text": f"{post_content}\n\n{blog_post_url}",
        }

        # Send the request to create the media container
        logger.info("📤 Creating Threads media container...")
        response = requests.post(threads_endpoint, params=payload)

        if response.status_code == 200:
            creation_id = response.json().get("id")
            logger.info(f"✅ Media container created successfully. Creation ID: {creation_id}")
            return creation_id
        else:
            logger.error(f"❌ Failed to create media container. Status: {response.status_code}, Response: {response.text}")
            raise Exception(f"Failed to create media container. {response.text}")

    except Exception as e:
        logger.error(f"❌ Error while creating Threads media container: {e}")
        raise

def publish_threads_media_container(creation_id):
    """
    Step 2: Publish the Threads media container.

    Args:
        creation_id (str): The ID of the media container to be published.

    Returns:
        dict: The response from the Threads API.
    """
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        logger.error("❌ Threads API configuration is missing. Check environment variables.")
        raise ValueError("Threads API configuration is missing.")

    try:
        # Define the Threads API endpoint for publishing
        threads_publish_endpoint = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"

        # Prepare payload
        payload = {
            "access_token": THREADS_ACCESS_TOKEN,
            "creation_id": creation_id,
        }

        # Send the request to publish the media container
        logger.info("📤 Publishing Threads media container...")
        response = requests.post(threads_publish_endpoint, params=payload)

        if response.status_code == 200:
            logger.info(f"✅ Post successfully published to Threads. Response: {response.json()}")
            return response.json()
        else:
            logger.error(f"❌ Failed to publish Threads media container. Status: {response.status_code}, Response: {response.text}")
            raise Exception(f"Failed to publish Threads media container. {response.text}")

    except Exception as e:
        logger.error(f"❌ Error while publishing Threads media container: {e}")
        raise

def publish_thread_for_blog_post(blog_post_url, tweet_content):
    """
    Main function to send a Threads post for the blog post.

    Args:
        blog_post_url (str): The URL of the blog post.
        tweet_content (str): The pre-generated content to use for the Threads post.
    """
    try:
        # Step 1: Create the media container
        creation_id = create_threads_media_container(tweet_content, blog_post_url)

        # Wait for a short period to ensure media container is ready
        logger.info("⏳ Waiting for media container to be processed...")
        time.sleep(30)  # Wait for 30 seconds as recommended

        # Step 2: Publish the media container
        publish_threads_media_container(creation_id)
    except Exception as e:
        logger.error(f"❌ Failed to publish Threads post for blog post: {e}")