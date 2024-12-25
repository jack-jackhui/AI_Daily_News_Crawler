import os
import logging
# import requests
import tweepy
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# Configure logger
logger = logging.getLogger(__name__)

# Twitter API Credentials
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET_KEY = os.getenv("TWITTER_API_SECRET_KEY")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Azure OpenAI API Credentials
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

def create_openai_client():
    """Initialize and return the Azure OpenAI client."""
    try:
        return AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
    except Exception as e:
        logger.error(f"❌ Failed to initialize Azure OpenAI client: {e}")
        raise

def generate_tweet_content(blog_post_url):
    """Generate a tweet content using Azure OpenAI."""
    client = create_openai_client()

    # System and user prompts
    system_prompt = (
        "You are a social media maestro, specializing in creating tweets that stop thumbs from scrolling. Craft a tweet that sizzles with excitement to announce the launch of our exclusive Daily AI News Digest. Incorporate the provided blog link smoothly and make it irresistible for followers to click. Keep it punchy, under 280 characters, and seal the deal with #DailyAINews. Remember, you're not just sharing news, you're starting conversations!"
    )
    user_prompt = f"Hey, here's the link to our must-read Daily AI News Digest blog post: {blog_post_url}. Let's dive into the future of AI together! 🔥 #DailyAINews"

    try:
        logger.info("🧠 Generating tweet content using Azure OpenAI...")
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="gpt-4o",  # Replace with the correct model
            temperature=1,
            max_tokens=180,
        )
        tweet_content = response.choices[0].message.content.strip()
        logger.info(f"Azure OpenAI response: {tweet_content}")
        return tweet_content
    except Exception as e:
        logger.error(f"❌ Failed to generate tweet content: {e}")
        raise

def send_tweet_via_tweepy(tweet_content):
    """Send the tweet using the Tweepy & Twitter API V2."""
    try:
        # Authenticate with Twitter API
        client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET_KEY,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        )

        logger.info("📤 Sending tweet...")
        response = client.create_tweet(text=tweet_content)
        logger.info(f"✅ Tweet sent successfully. Tweet ID: {response.data['id']}")
        return response.data
    except tweepy.TweepyException as e:
        logger.error(f"❌ Failed to send tweet via Tweepy: {e}")
        raise

def publish_tweet_for_blog_post(tweet_content):
    """Main function to generate and send a tweet for the blog post."""
    try:
        # tweet_content = generate_tweet_content(blog_post_url)
        send_tweet_via_tweepy(tweet_content)
    except Exception as e:
        logger.error(f"❌ Failed to publish tweet for blog post: {e}")
