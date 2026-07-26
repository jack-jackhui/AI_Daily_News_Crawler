import json
import logging
from dotenv import load_dotenv
import re
from utils.llm_client import (
    LLMResponseValidationError,
    get_llm_client,
    get_llm_model,
    get_llm_provider,
)
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
    Attempt to repair incomplete or malformed JSON from LLM responses.
    Handles:
    - Markdown code blocks (```json ... ```)
    - Unquoted emoji values ("icon": 🤖 -> "icon": "🤖")
    - Missing brackets
    - Trailing commas
    """
    response_text = response_text.strip()

    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        # Remove opening ```json or ``` and closing ```
        response_text = re.sub(r"^```(?:json)?\s*\n?", "", response_text)
        response_text = re.sub(r"\n?```\s*$", "", response_text)
        response_text = response_text.strip()

    # Fix unquoted emoji values: "icon": 🤖 -> "icon": "🤖"
    # This pattern matches "icon": followed by an emoji (not in quotes)
    emoji_pattern = r'("icon"\s*:\s*)([^\s",\[\]{}][^\s,\[\]{}]*?)(\s*[,}\]])'
    response_text = re.sub(emoji_pattern, r'\1"\2"\3', response_text)

    # Ensure it starts with '[' and ends with ']'
    if not response_text.startswith("["):
        response_text = "[" + response_text
    if not response_text.endswith("]"):
        response_text += "]"

    # Remove invalid trailing commas
    response_text = re.sub(r",\s*]", "]", response_text)

    return response_text


def _validate_summary_response(chat_completion) -> list[dict]:
    """Parse and strictly validate an LLM summary response."""
    try:
        response_text = chat_completion.choices[0].message.content
        if not isinstance(response_text, str) or not response_text.strip():
            raise ValueError("response content is empty")
        logger.info("Raw LLM response before parsing: %s", response_text)
        parsed = json.loads(repair_json(response_text))
    except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LLMResponseValidationError(f"Invalid summary JSON: {exc}") from exc

    if not isinstance(parsed, list) or not parsed:
        raise LLMResponseValidationError("Summary response must be a non-empty JSON array")

    validated = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise LLMResponseValidationError(f"Summary item {index} is not an object")
        normalized = {}
        for field in ("title", "summary", "url"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise LLMResponseValidationError(
                    f"Summary item {index} has invalid {field}"
                )
            normalized[field] = value.strip()
        icon = item.get("icon")
        normalized["icon"] = icon.strip() if isinstance(icon, str) and icon.strip() else "🤖"
        validated.append(normalized)
    return validated

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

    client = get_llm_client()
    logger.info("Using %s model %s", get_llm_provider(), get_llm_model())

    try:
        return client.chat.completions.create_validated(
            _validate_summary_response,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=get_llm_model(),
            temperature=1,
            max_completion_tokens=2000,
        )

    except Exception as e:
        logger.error(f"Error while re-ranking and summarizing articles with LLM: {e}")
        return []
