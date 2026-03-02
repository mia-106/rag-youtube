"""
Deep Research Flow - 智能路由系统
根据URL类型自动选择最适合的采集策略
"""

import logging
from typing import Dict, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SmartScraper:
    """
    智能采集器
    根据URL类型自动选择采集策略
    """

    def __init__(self):
        """初始化智能采集器"""
        self._init_handlers()

    def _init_handlers(self):
        """初始化所有可用的处理器"""
        # 导入YouTube Handler
        try:
            from src.deepresearch_flow.handlers import create_youtube_handler

            self.youtube_handler = create_youtube_handler()
            self._has_youtube_handler = True
            logger.info("YouTube Handler initialized")
        except Exception as e:
            self.youtube_handler = None
            self._has_youtube_handler = False
            logger.warning(f"YouTube Handler not available: {e}")

        # 导入Firecrawl Client
        try:
            from src.ingestion.firecrawl_client import FirecrawlClient

            self.firecrawl_client = FirecrawlClient()
            self._has_firecrawl = True
            logger.info("Firecrawl Client initialized")
        except Exception as e:
            self.firecrawl_client = None
            self._has_firecrawl = False
            logger.warning(f"Firecrawl Client not available: {e}")

    def select_strategy(self, url: str) -> str:
        """
        根据URL选择采集策略

        Args:
            url: 要采集的URL

        Returns:
            策略名称: 'youtube', 'firecrawl', 或 'unknown'
        """
        if not url:
            return "unknown"

        parsed = urlparse(url.lower())
        domain = parsed.netloc

        # YouTube相关域名
        youtube_domains = ["youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"]
        if any(yt_domain in domain for yt_domain in youtube_domains):
            logger.info(f"URL detected as YouTube: {url}")
            return "youtube"

        # 其他已知支持的网站可以扩展
        supported_domains = ["vimeo.com", "dailymotion.com", "twitch.tv"]
        if any(supp_domain in domain for supp_domain in supported_domains):
            logger.info(f"URL detected as supported site: {url}")
            return "firecrawl"

        # 默认使用Firecrawl
        logger.info(f"URL will use default Firecrawl strategy: {url}")
        return "firecrawl"

    def scrape(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        根据URL自动选择策略并采集数据

        Args:
            url: 要采集的URL
            **kwargs: 传递给具体处理器的额外参数

        Returns:
            采集结果字典
        """
        # 选择策略
        strategy = self.select_strategy(url)

        try:
            if strategy == "youtube":
                return self._scrape_youtube(url, **kwargs)
            elif strategy == "firecrawl":
                return self._scrape_firecrawl(url, **kwargs)
            else:
                return {"success": False, "error": f"Unknown or unsupported URL: {url}", "strategy": strategy}
        except Exception as e:
            logger.error(f"Scraping failed with strategy {strategy}: {e}")
            return {"success": False, "error": str(e), "strategy": strategy, "url": url}

    def _scrape_youtube(self, url: str, **kwargs) -> Dict[str, Any]:
        """使用YouTube Handler采集"""
        if not self._has_youtube_handler:
            return {"success": False, "error": "YouTube Handler not available", "strategy": "youtube"}

        try:
            # 检查是否是频道URL
            parsed = urlparse(url.lower())
            if "/channel/" in parsed.path or "/c/" in parsed.path or "/@" in parsed.path:
                # 频道采集
                limit = kwargs.get("limit", 50)
                print(f"[] 检测到YouTube频道URL使用批量采集策略限制 {limit} 个视频", flush=True)
                logger.info(f"Scraping YouTube channel with limit: {limit}")
                channel_data = self.youtube_handler.fetch_channel_data(url, limit=limit)

                # 将VideoMetadata列表转换为字典格式
                videos = [self._video_metadata_to_dict(vm) for vm in channel_data]

                return {
                    "success": True,
                    "data": {"success": True, "videos": videos, "count": len(videos)},
                    "strategy": "youtube",
                    "url": url,
                    "type": "channel",
                }
            else:
                # 单个视频采集
                print("[] 检测到YouTube视频URL使用LangChain YoutubeLoader", flush=True)
                logger.info("Scraping YouTube video")
                video_metadata = self.youtube_handler.fetch_video_data(url)

                # 将VideoMetadata转换为字典格式
                video_dict = self._video_metadata_to_dict(video_metadata)

                return {
                    "success": True,
                    "data": {"success": True, **video_dict},
                    "strategy": "youtube",
                    "url": url,
                    "type": "video",
                }

        except Exception as e:
            logger.error(f"YouTube scraping failed: {e}")
            print(f"[] YouTube采集失败: {str(e)}", flush=True)
            return {"success": False, "error": str(e), "strategy": "youtube", "url": url}

    def _video_metadata_to_dict(self, video_metadata) -> Dict[str, Any]:
        """将VideoMetadata对象转换为字典"""
        if hasattr(video_metadata, "__dict__"):
            return video_metadata.__dict__
        return video_metadata

    def _scrape_firecrawl(self, url: str, **kwargs) -> Dict[str, Any]:
        """使用Firecrawl Client采集"""
        if not self._has_firecrawl:
            return {"success": False, "error": "Firecrawl Client not available", "strategy": "firecrawl"}

        try:
            import asyncio

            logger.info(f"Scraping with Firecrawl: {url}")

            # 异步执行Firecrawl采集
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                videos = loop.run_until_complete(self.firecrawl_client.crawl_channel(url))

                # 转换为标准格式
                video_list = []
                for video in videos:
                    video_dict = {
                        "video_id": video.video_id,
                        "channel_id": video.channel_id,
                        "title": video.title,
                        "description": video.description,
                        "duration": video.duration,
                        "view_count": video.view_count,
                        "webpage_url": video.webpage_url,
                    }
                    video_list.append(video_dict)

                return {
                    "success": True,
                    "data": {"videos": video_list, "total": len(video_list)},
                    "strategy": "firecrawl",
                    "url": url,
                    "type": "general",
                }

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Firecrawl scraping failed: {e}")
            return {"success": False, "error": str(e), "strategy": "firecrawl", "url": url}

    def batch_scrape(self, urls: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        批量采集多个URL

        Args:
            urls: URL列表
            **kwargs: 传递给采集器的参数

        Returns:
            结果列表
        """
        results = []
        for url in urls:
            logger.info(f"Processing URL {len(results) + 1}/{len(urls)}: {url}")
            result = self.scrape(url, **kwargs)
            results.append(result)

        return results


def create_smart_scraper() -> SmartScraper:
    """
    工厂函数创建智能采集器实例

    Returns:
        SmartScraper实例
    """
    return SmartScraper()


if __name__ == "__main__":
    # 测试代码
    import sys
    import json

    scraper = create_smart_scraper()

    if len(sys.argv) > 1:
        url = sys.argv[1]
        result = scraper.scrape(url)

        # 输出结果过滤敏感信息
        safe_result = {
            "success": result.get("success"),
            "strategy": result.get("strategy"),
            "type": result.get("type"),
            "error": result.get("error"),
        }

        # 如果成功添加数据摘要
        if result.get("success"):
            data = result.get("data", {})
            if result.get("type") == "video":
                safe_result["video_id"] = data.get("video_id")
                safe_result["title"] = data.get("title", "")[:50] + "..."
            elif result.get("type") == "channel":
                safe_result["channel"] = data.get("channel_info", {}).get("channel")
                safe_result["video_count"] = data.get("total_videos", 0)

        print(json.dumps(safe_result, indent=2, ensure_ascii=True))
    else:
        print("Usage: python scraper.py <url>")
