# src/fetchers/crawler.py
import asyncio
import datetime

from crawl4ai import AsyncWebCrawler


async def crawl_website(url: str) -> dict:
    async with AsyncWebCrawler(verbose=True) as crawler:
        try:
            result = await crawler.arun(url=url)
            return {
                "content": result.markdown,
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "success",
                "url": url,
            }
        except Exception as e:
            return {
                "content": "",
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "failure",
                "url": url,
                "error": str(e),
            }


async def batch_crawl_websites(urls: list[str]) -> list[dict]:
    tasks = [crawl_website(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results
