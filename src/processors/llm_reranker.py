import json
import logging
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import re
# Load environment variables
load_dotenv()

# Configure logger with timestamps
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def repair_json(response_text):
    """
    Attempt to repair incomplete JSON by adding missing brackets or commas.
    """
    response_text = response_text.strip()

    # Ensure it starts with '[' and ends with ']'
    if not response_text.startswith("["):
        response_text = "[" + response_text
    if not response_text.endswith("]"):
        response_text += "]"

    # Remove invalid trailing commas
    response_text = re.sub(r",\s*]", "]", response_text)

    return response_text

def re_rank_and_summarize_with_llm(articles: list[dict]) -> list[dict]:
    """
    Combine LLM Re-Rank and Summarize into a single function.
    This function groups similar articles, ranks them, and summarizes them into one concise summary.
    :param articles: List of articles to process.
                     Each article is a dictionary containing 'title', 'content', and 'url'.
    :return: List of re-ranked and summarized articles.
    """
    if not articles:
        logger.warning("No articles provided for re-ranking and summarization.")
        return []

    logger.info(f"Re-ranking and summarizing {len(articles)} articles using LLM...")

    article_json_str = json.dumps(
        [
            {
                "url": a.get("url", ""),
                "title": a.get("title", "Untitled")[:100],
                "content": a.get("content", "")[
                    :500
                ],  # Limit content to avoid token overflow
            }
            for a in articles
        ],
        ensure_ascii=False,
    )

    system_prompt = (
        "You are a helpful assistant that outputs ONLY valid JSON. "
        "Do NOT include any explanation, headers, or text outside of the JSON array."
    )

    user_prompt = (
        "Below is a list of AI news articles in JSON format. Each article includes fields like "
        "'title', 'url', and 'content'.\n\n"
        "1️⃣ **Group related articles together** based on similar topics or subject matter (similar titles, themes, or main points).\n"
        "2️⃣ **Select the most important article in each group** to represent the group.\n"
        "3️⃣ **Summarize the grouped content**. Write a concise one-liner summary of the combined content of the group. \n"
        "4️⃣ **Return a JSON array** of the final ranked, summarized articles with the following structure:\n"
        "- icon: Use an appropriate emoji related to AI (like 🤖, 📜, 🔍, 🚀, etc.).\n"
        "- title: The title of the grouped topic.\n"
        "- summary: A one-liner summary of the grouped content.\n"
        "- url: The URL of the most relevant article in the group.\n\n"
        "Return only valid JSON. Here is an example of the expected format:\n"
        "[\n"
        "  {\n"
        '    "icon": "🤖",\n'
        '    "title": "Title of the grouped topic",\n'
        '    "summary": "A one-liner summary of the grouped content.",\n'
        '    "url": "https://example.com/most-relevant-article"\n'
        "  },\n"
        "  ...\n"
        "]\n\n"
        "Articles:\n"
        f"{article_json_str}"
    )

    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=os.getenv("AZURE_OPENAI_MODEL"),  # Replace with the correct model
            temperature=1,
            max_completion_tokens=2000,
        )
        response_text = chat_completion.choices[0].message.content.strip()
        logger.info(f"Raw LLM response before parsing: {response_text}")

        response_text = repair_json(response_text)

        try:
            re_ranked_and_summarized_articles = json.loads(response_text)
            if isinstance(re_ranked_and_summarized_articles, list):
                return re_ranked_and_summarized_articles
            else:
                logger.error("LLM returned a non-list JSON structure.")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response. Error: {e}")
            logger.debug(f"Repaired LLM response text: {response_text}")
            return []

    except Exception as e:
        logger.error(f"Error while re-ranking and summarizing articles with LLM: {e}")
        return []
