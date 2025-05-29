import json
import os

from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables from .env
load_dotenv()


def summarize_news_articles(articles: list[dict]) -> list[dict]:
    """
    Summarize a list of articles using Azure OpenAI and return a structured list of dicts.
    Each dict will have keys: icon, title, summary, url.

    :param articles: A list of dictionaries containing news articles.
                     Expected keys: 'title', 'content', 'url'
    :return: A list of dicts, each representing a summarized article:
             [
               {
                 "icon": "📜",
                 "title": "Article Title",
                 "summary": "One-liner summary of the article",
                 "url": "https://example.com/article"
               },
               ...
             ]
             or empty list if no articles or if an error occurs.
    """
    # Filter only articles with content
    valid_articles = [a for a in articles if a.get("content")]
    if not valid_articles:
        print("No valid articles found to summarize.")
        return []

    # Prepare a JSON-friendly list of article data for the prompt
    article_json_str = json.dumps(
        [
            {
                "url": a.get("url", ""),
                "title": a.get("title", "Untitled"),
                "content": a["content"][
                    :500
                ],  # Truncate content to 500 characters to avoid token overload
            }
            for a in valid_articles
        ],
        ensure_ascii=False,
    )

    system_prompt = (
        "You are a helpful assistant that outputs ONLY valid JSON. "
        "Do NOT include any explanation, headers, or text outside of the JSON array.")
    user_prompt = (
        "Below is a list of AI news articles in JSON format. Each article "
        "includes fields such as 'title', 'url', and 'content' (a short snippet of the article).\n\n"
        "Using this data, generate a JSON array of summarized articles. For each article:\n"
        "- icon: Use an appropriate emoji icon (e.g., 📜, 🤖, 💧) related to tech or AI.\n"
        "- title: Extract the original news article title directly from the data.\n"
        "- summary: A one-liner summary highlighting the main point of the article "
        "(this should be a concise summary of the article’s content or theme, not just a repetition of the title).\n"
        "- url: The original article URL (from the 'url' field in the data).\n\n"
        "Return only valid JSON with no extra text. The output should be an array, for example:\n"
        "[\n"
        "  {\n"
        '    "icon": "📜",\n'
        '    "title": "Article title here",\n'
        '    "summary": "A brief one-line summary.",\n'
        '    "url": "https://example.com/article"\n'
        "  },\n"
        "  ...\n"
        "]\n\n"
        "Articles:\n"
        f"{article_json_str}")

    # Initialize the Azure OpenAI client
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv(
            "AZURE_OPENAI_API_VERSION",
            "2025-01-01-preview"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=os.getenv("AZURE_OPENAI_MODEL"),  # Replace with the correct model name/variant for your account
            temperature=0.7,
            max_tokens=1000,
        )
        response_text = chat_completion.choices[0].message.content.strip()
        print("Azure response:", response_text)  # Debugging line

        # Attempt to parse the returned JSON
        summarized_articles = json.loads(response_text)
        if isinstance(summarized_articles, list):
            return summarized_articles
        else:
            print("Summarizer returned a non-list JSON structure.")
            return []
    except Exception as e:
        print(f"Failed to summarize articles: {str(e)}")
        return []


if __name__ == "__main__":
    # Example input: A list of already-fetched articles
    example_articles = [{"title": "AI Breakthrough in 2024",
                         "content": "Researchers have made a groundbreaking discovery in artificial intelligence that could change the future of machine learning and automation...",
                         "url": "https://example.com/ai-breakthrough-2024",
                         },
                        {"title": "Tech Giants Launch New Products",
                         "content": "Leading technology companies have announced a new wave of products for 2024, including advanced AI tools, robotics, and consumer devices...",
                         "url": "https://example.com/tech-giants-products-2024",
                         },
                        ]

    # Call the summarizer
    summarized_articles = summarize_news_articles(example_articles)

    # Print summarized articles
    print("\n--- Summarized Articles ---\n")
    print(json.dumps(summarized_articles, indent=2, ensure_ascii=False))
