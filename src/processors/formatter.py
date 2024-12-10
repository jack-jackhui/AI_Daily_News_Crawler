# processors/formatter.py


def format_summary(news_items: list[dict]) -> str:
    """
    Format a list of news items into the desired three-line format for each item:
    1. Icon and Title
    2. One-liner summary
    3. Link

    All items preceded by a main heading '**AI News Digest**'.
    """
    if not news_items:
        return "**Today's Tech & AI News Digest**\n\nNo new content to summarize."

    formatted_lines = ["**🎉 Today's Tech & AI News Digest 🎉**\n"]

    for item in news_items:
        icon = item.get("icon", "📰")  # Default icon if none provided
        title = item.get("title", "No Title")
        summary = item.get("summary", "No summary provided.")
        url = item.get("url", "#")

        formatted_lines.append(f"{icon} {title}")
        formatted_lines.append(summary)
        formatted_lines.append(url)
        formatted_lines.append("")  # Blank line after each entry

    return "\n".join(formatted_lines).strip()
