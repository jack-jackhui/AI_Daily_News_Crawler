import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main  # noqa: E402


class MainPipelineGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_summaries_abort_before_all_outputs(self):
        with patch.object(main, "validate_and_refresh_token", return_value=(True, "ok", None)), patch.object(
            main, "fetch_rss_feeds", return_value=[{"title": "Input"}]
        ), patch.object(
            main, "re_rank_and_summarize_with_llm", return_value=[]
        ), patch.object(
            main, "format_summary"
        ) as format_summary, patch.object(
            main, "send_to_telegram", new_callable=AsyncMock
        ) as send_to_telegram, patch.object(
            main, "send_to_wechat"
        ) as send_to_wechat, patch.object(
            main, "publish_daily_news_to_wordpress"
        ) as publish_wordpress, patch.object(
            main.os, "makedirs"
        ) as makedirs:
            await main.run_pipeline()

        format_summary.assert_not_called()
        makedirs.assert_not_called()
        send_to_telegram.assert_not_awaited()
        send_to_wechat.assert_not_called()
        publish_wordpress.assert_not_called()


if __name__ == "__main__":
    unittest.main()
