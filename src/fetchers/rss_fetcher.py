import re
import feedparser
from datetime import datetime, timedelta
from newspaper import Article
from urllib.parse import urlparse
from tranco import Tranco
import logging
import textstat  # Make sure you have textstat installed

# Set up logger
logger = logging.getLogger(__name__)

# Initialize Tranco list
latest_list = None

def initialize_tranco_list():
    """Initialize the Tranco list using the Tranco package."""
    global latest_list
    if latest_list is None:
        t = Tranco(cache=True, cache_dir='.tranco')
        latest_list = t.list()
        logger.info('Tranco list initialized.')

def clean_text(text):
    """Remove HTML tags from the text."""
    return re.sub(r'<.*?>', '', text)

def get_full_text(url):
    """Retrieve the full text of an article from its URL using newspaper3k."""
    try:
        article = Article(url, browser_user_agent='Mozilla/5.0')
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        logger.warning(f"Could not retrieve full text for {url}: {e}")
        return ""

def get_readability_score(text):
    """Compute the readability score of the text using Flesch Reading Ease."""
    try:
        score = textstat.flesch_reading_ease(text)
        # Normalize the score to a range of 0-10
        normalized_score = max(0, min((score / 100) * 10, 10))
        return normalized_score
    except Exception as e:
        logger.warning(f"Could not compute readability score: {e}")
        return 5  # Default to an average score of 5

def fetch_rss_feeds(feed_urls: list[str], max_to_rank: int = 20) -> list[dict]:
    """Fetch, rank, and filter the most valuable articles from RSS feeds."""
    all_articles = []
    now = datetime.now()
    cutoff_date = now - timedelta(days=1)  # Get articles from the last 24 hours

    ai_keywords = [
        "AI", "Artificial Intelligence", "Machine Learning", "Deep Learning",
        "Neural Network", "Natural Language Processing", "NLP", "OpenAI", "ChatGPT"
    ]

    crypto_keywords = [
        "Blockchain", "Bitcoin", "Ethereum", "Cryptocurrency", "DeFi"
    ]

    keywords_with_weights = {kw.lower(): 4 for kw in ai_keywords}
    keywords_with_weights.update({kw.lower(): 1 for kw in crypto_keywords})

    if latest_list is None:
        initialize_tranco_list()

    seen_links = set()

    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                published_date = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else now

                if published_date < cutoff_date:
                    continue

                link = entry.link
                if link in seen_links:
                    continue

                seen_links.add(link)
                full_text = get_full_text(link) or clean_text(entry.get('summary', ''))

                title_lower = entry.title.lower()
                content_lower = full_text.lower()

                # Calculate scores using different criteria
                title_score = sum(title_lower.count(kw) * weight for kw, weight in keywords_with_weights.items())
                content_score = sum(content_lower.count(kw) * weight for kw, weight in keywords_with_weights.items())
                readability_score = get_readability_score(full_text)

                total_score = (
                    title_score * 3 +
                    content_score * 2 +
                    readability_score * 1
                )

                article = {
                    "title": entry.title,
                    "content": full_text,
                    "url": link,
                    "published": published_date.isoformat(),
                    "status": 'success' if full_text else 'failure',
                    "total_score": total_score
                }

                if total_score > 0:
                    all_articles.append(article)
        except Exception as e:
            logger.error(f"Failed to parse feed {feed_url}: {e}")

    sorted_articles = sorted(all_articles, key=lambda x: x.get('total_score', 0), reverse=True)
    top_articles = sorted_articles[:max_to_rank]

    logger.info(f"Total articles prepared for re-ranking: {len(top_articles)}")
    return top_articles