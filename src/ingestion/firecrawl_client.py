"""
Firecrawl客户端模块并发控制版
使用Firecrawl Deep Research API进行YouTube频道数据采集
包含严格的输入验证错误处理和并发控制
"""

import asyncio
import importlib.util
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
import requests
from src.core.config import settings
from src.ingestion.content_hasher import ContentHasher
from src.core.models import VideoMetadata

import logging

logger = logging.getLogger(__name__)


class FirecrawlError(Exception):
    """Firecrawl相关错误"""

    pass


class ValidationError(FirecrawlError):
    """验证错误"""

    pass


class FirecrawlClient:
    """Firecrawl API客户端带并发控制"""

    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY
        self.base_url = settings.FIRECRAWL_DEEP_RESEARCH_URL
        self.session = requests.Session()
        # 设置请求超时 60秒
        self.session.timeout = 60
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})

        #  输入验证配置
        self.allowed_domains = {"youtube.com", "www.youtube.com"}
        self.max_url_length = 2048
        self.max_channel_id_length = 100

        #  并发控制
        self.max_concurrent_crawls = getattr(settings, "MAX_CONCURRENT_CRAWLS", 5)
        self.crawl_semaphore = asyncio.Semaphore(self.max_concurrent_crawls)
        self.crawl_delay = getattr(settings, "CRAWL_DELAY", 1.0)  # 请求间隔

        #  爬取统计
        self.crawl_stats = {
            "total_crawls": 0,
            "successful_crawls": 0,
            "failed_crawls": 0,
            "avg_crawl_time": 0.0,
            "last_crawl_time": 0,
        }

        # 检查 yt-dlp 可用性
        self._check_ytdlp_availability()

    def _check_ytdlp_availability(self):
        """检查 yt-dlp 是否可用"""
        self.yt_dlp_available = importlib.util.find_spec("yt_dlp") is not None
        if self.yt_dlp_available:
            logger.info(" yt-dlp 可用")
        else:
            logger.warning(" yt-dlp 不可用将使用 Firecrawl API")

    def _is_youtube_url(self, url: str) -> bool:
        """
        检测URL是否为YouTube相关

        Args:
            url: 要检测的URL

        Returns:
            如果是YouTube URL返回True否则返回False
        """
        if not url:
            return False

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url.lower())
            domain = parsed.netloc

            youtube_domains = ["youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"]
            return any(yt_domain in domain for yt_domain in youtube_domains)

        except Exception as e:
            logger.warning(f"检测YouTube URL失败: {e}")
            return False

    def _sanitize_input(self, input_str: str) -> str:
        """清理输入字符串"""
        if not isinstance(input_str, str):
            raise ValidationError("输入必须是字符串类型")

        # 移除控制字符
        sanitized = "".join(char for char in input_str if ord(char) >= 32 or char in "\t\n\r")

        # 限制长度
        if len(sanitized) > self.max_url_length:
            raise ValidationError(f"输入长度超过限制 ({self.max_url_length})")

        return sanitized.strip()

    def _validate_channel_url(self, channel_url: str) -> bool:
        """严格验证YouTube频道URL"""
        # 清理输入
        try:
            channel_url = self._sanitize_input(channel_url)
        except ValidationError as e:
            logger.warning(f"URL验证失败: {e}")
            return False

        # 基本格式检查
        if not channel_url:
            logger.warning("URL为空")
            return False

        # 检查协议
        if not (channel_url.startswith("http://") or channel_url.startswith("https://")):
            logger.warning(f"URL缺少协议: {channel_url}")
            return False

        # 解析URL
        try:
            parsed = urlparse(channel_url)
        except Exception as e:
            logger.warning(f"URL解析失败: {e}")
            return False

        # 验证域名
        if parsed.netloc not in self.allowed_domains:
            logger.warning(f"不支持的域名: {parsed.netloc}")
            return False

        # 验证路径格式
        path = parsed.path.lower()
        valid_patterns = [
            r"^/channel/[a-zA-Z0-9_-]+",
            r"^/c/[a-zA-Z0-9_-]+",
            r"^/@[a-zA-Z0-9_-]+",
            r"^/user/[a-zA-Z0-9_-]+",
            r"^/watch",  # 支持单个视频URL
        ]

        if not any(re.match(pattern, path) for pattern in valid_patterns):
            logger.warning(f"无效的频道URL路径: {path}")
            return False

        # 检查是否包含危险字符移除?因为YouTube URL包含查询参数
        dangerous_chars = ["<", ">", '"', "'", "&", "#"]
        if any(char in channel_url for char in dangerous_chars):
            logger.warning(f"URL包含危险字符: {dangerous_chars}")
            return False

        # 验证查询参数
        if parsed.query:
            query_params = parse_qs(parsed.query)
            # 只允许特定的查询参数YouTube可能有更多参数
            allowed_params = {"v", "list", "index", "t", "si", "feature", "pp"}
            for param in query_params.keys():
                if param not in allowed_params:
                    logger.warning(f"不允许的查询参数: {param}")
                    return False

        return True

    def _validate_channel_id(self, channel_id: str) -> bool:
        """验证频道ID"""
        if not isinstance(channel_id, str):
            return False

        # 清理输入
        try:
            channel_id = self._sanitize_input(channel_id)
        except ValidationError:
            return False

        # 检查长度
        if len(channel_id) == 0 or len(channel_id) > self.max_channel_id_length:
            return False

        # 检查字符频道ID只能包含字母数字下划线和连字符
        if not re.match(r"^[a-zA-Z0-9_-]+$", channel_id):
            logger.warning(f"频道ID包含非法字符: {channel_id}")
            return False

        # 检查是否包含路径遍历
        if ".." in channel_id or "/" in channel_id or "\\" in channel_id:
            logger.warning(f"频道ID包含路径遍历: {channel_id}")
            return False

        return True

    def extract_channel_id(self, channel_url: str) -> Optional[str]:
        """从URL中提取频道ID带验证"""
        if not self._validate_channel_url(channel_url):
            raise ValidationError(f"无效的频道URL: {channel_url}")

        try:
            # 清理URL
            channel_url = self._sanitize_input(channel_url)

            # 提取频道ID
            if "/channel/" in channel_url:
                channel_id = channel_url.split("/channel/")[-1].split("/")[0]
            elif "/c/" in channel_url:
                channel_id = channel_url.split("/c/")[-1].split("/")[0]
            elif "/@" in channel_url:
                channel_id = channel_url.split("/@")[-1].split("/")[0]
            elif "/user/" in channel_url:
                channel_id = channel_url.split("/user/")[-1].split("/")[0]
            else:
                logger.warning(f"无法识别的URL格式: {channel_url}")
                return None

            # 验证提取的频道ID
            if not self._validate_channel_id(channel_id):
                logger.warning(f"提取的频道ID无效: {channel_id}")
                return None

            return channel_id

        except Exception as e:
            logger.error(f"提取频道ID时出错: {e}")
            return None

    async def crawl_channel(self, channel_url: str) -> List[VideoMetadata]:
        """
        爬取频道视频列表带智能检测

        检测到YouTube URL时自动使用yt-dlp否则使用Firecrawl API

        Args:
            channel_url: YouTube频道URL

        Returns:
            视频元数据列表

        Raises:
            FirecrawlError: 所有方法都失败时抛出
        """
        if not self._validate_channel_url(channel_url):
            raise FirecrawlError(f"无效的频道URL: {channel_url}")

        # 检测是否为YouTube URL如果是则直接使用yt-dlp
        if self._is_youtube_url(channel_url):
            logger.info(f"检测到YouTube URL直接使用 yt-dlp: {channel_url}")
            if not self.yt_dlp_available:
                raise FirecrawlError("yt-dlp 不可用无法处理YouTube URL")

            try:
                # 在线程池中运行同步的 yt-dlp设置超时
                import concurrent.futures

                loop = asyncio.get_event_loop()

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = loop.run_in_executor(executor, self.crawl_with_ytdlp, channel_url)
                    # 设置超时 60秒
                    videos = await asyncio.wait_for(future, timeout=60)

                logger.info(f" yt-dlp 成功采集 {len(videos)} 个视频")
                return videos

            except asyncio.TimeoutError:
                logger.error(" yt-dlp 采集超时60秒")
                raise FirecrawlError("yt-dlp 采集超时")
            except Exception as e:
                logger.error(f" yt-dlp 采集失败: {str(e)}")
                raise FirecrawlError(f"yt-dlp 采集失败: {str(e)}")

        # 非YouTube URL使用Firecrawl API
        return await self._crawl_with_firecrawl(channel_url)

    async def _crawl_with_firecrawl(self, channel_url: str) -> List[VideoMetadata]:
        """使用 Firecrawl API 采集私有方法"""
        try:
            # 构建搜索查询
            search_query = f"site:youtube.com channel {channel_url} videos"

            # 调用Firecrawl Deep Research API
            payload = {
                "query": search_query,
                "filters": {"type": "pdf", "includeTags": ["video"], "excludeTags": ["playlist"]},
                "limit": 100,
            }

            # 使用异步方式调用带超时
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=60),  # 60秒超时
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

            videos = self._parse_search_results(result)
            return videos

        except asyncio.TimeoutError:
            raise FirecrawlError("Firecrawl API 请求超时60秒")
        except requests.exceptions.RequestException as e:
            raise FirecrawlError(f"Firecrawl API调用失败: {str(e)}")
        except Exception as e:
            raise FirecrawlError(f"Firecrawl采集失败: {str(e)}")

    def _update_crawl_stats(self, success: bool, crawl_time: float = 0.0):
        """更新爬取统计"""
        self.crawl_stats["total_crawls"] += 1

        if success:
            self.crawl_stats["successful_crawls"] += 1
            # 更新平均爬取时间
            total = self.crawl_stats["total_crawls"]
            current_avg = self.crawl_stats["avg_crawl_time"]
            self.crawl_stats["avg_crawl_time"] = (current_avg * (total - 1) + crawl_time) / total
        else:
            self.crawl_stats["failed_crawls"] += 1

    def get_crawl_status(self) -> Dict[str, Any]:
        """获取爬取状态"""
        total = self.crawl_stats["total_crawls"]
        if total == 0:
            return {
                "status": "ready",
                "concurrent_slots_available": self.crawl_semaphore._value,
                "stats": self.crawl_stats,
            }

        success_rate = (self.crawl_stats["successful_crawls"] / total) * 100
        failure_rate = (self.crawl_stats["failed_crawls"] / total) * 100

        return {
            "status": "active",
            "concurrent_slots_available": self.crawl_semaphore._value,
            "crawl_delay_seconds": self.crawl_delay,
            "max_concurrent_crawls": self.max_concurrent_crawls,
            "stats": {
                **self.crawl_stats,
                "success_rate_percent": round(success_rate, 2),
                "failure_rate_percent": round(failure_rate, 2),
            },
        }

    def reset_crawl_stats(self):
        """重置爬取统计"""
        self.crawl_stats = {
            "total_crawls": 0,
            "successful_crawls": 0,
            "failed_crawls": 0,
            "avg_crawl_time": 0.0,
            "last_crawl_time": 0,
        }
        logger.info(" 爬取统计已重置")

    def _parse_search_results(self, result: Dict[str, Any]) -> List[VideoMetadata]:
        """解析搜索结果"""
        videos = []
        search_results = result.get("data", [])

        for item in search_results:
            try:
                # 提取视频信息
                video_url = item.get("url", "")
                if "watch?v=" not in video_url:
                    continue

                video_id = parse_qs(urlparse(video_url).query).get("v", [None])[0]
                if not video_id:
                    continue

                # 从标题和描述中提取信息
                title = item.get("title", "").strip()
                description = item.get("description", "").strip()

                # 生成内容哈希
                content_hash = ContentHasher.generate_video_hash(
                    {
                        "title": title,
                        "description": description,
                        "duration": 0,  # 后续通过YouTube API补充
                    }
                )

                video = VideoMetadata(
                    video_id=video_id,
                    channel_id="",  # 后续从URL提取
                    title=title,
                    description=description,
                    content_hash=content_hash,
                )

                videos.append(video)

            except Exception as e:
                print(f" 解析视频项失败: {str(e)}")
                continue

        return videos

    async def get_video_details(self, video_id: str) -> Optional[VideoMetadata]:
        """
        获取单个视频详细信息

        Args:
            video_id: YouTube视频ID

        Returns:
            视频元数据或None
        """
        try:
            # 这里可以使用YouTube Data API或yt-dlp获取详细信息
            # 为简化演示返回基础信息
            return VideoMetadata(
                video_id=video_id,
                channel_id="",
                title=f"视频 {video_id}",
                description="",
                content_hash=ContentHasher.generate_hash(video_id),
            )
        except Exception as e:
            print(f" 获取视频详情失败: {str(e)}")
            return None

    async def extract_subtitle_urls(self, video_id: str) -> List[str]:
        """
        提取字幕链接

        Args:
            video_id: YouTube视频ID

        Returns:
            字幕文件URL列表
        """
        # 实际实现中需要通过YouTube API或yt-dlp获取字幕
        # 这里返回模拟数据
        return [
            f"https://www.youtube.com/api/timedtext?lang=en&v={video_id}",
            f"https://www.youtube.com/api/timedtext?lang=zh&v={video_id}",
        ]

    async def batch_crawl_channels(self, channel_urls: List[str]) -> List[VideoMetadata]:
        """
        批量爬取多个频道

        Args:
            channel_urls: 频道URL列表

        Returns:
            所有视频元数据列表
        """
        all_videos = []
        semaphore = asyncio.Semaphore(5)  # 限制并发数

        async def crawl_single_channel(url):
            async with semaphore:
                return await self.crawl_channel(url)

        tasks = [crawl_single_channel(url) for url in channel_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_videos.extend(result)
            else:
                print(f" 爬取失败: {result}")

        return all_videos

    def crawl_with_ytdlp(self, channel_url: str) -> List[VideoMetadata]:
        """
        使用 yt-dlp 直接采集YouTube频道同步方法

        Args:
            channel_url: YouTube频道URL

        Returns:
            视频元数据列表
        """
        if not self.yt_dlp_available:
            raise FirecrawlError("yt-dlp 不可用")

        import yt_dlp

        videos = []

        # yt-dlp 配置
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,  # 不下载视频
            "writesubtitles": False,
            "writeautomaticsub": False,
            "subtitleslangs": ["en", "zh"],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f" 使用 yt-dlp 采集频道: {channel_url}")

                # 获取频道信息
                channel_info = ydl.extract_info(channel_url, download=False, ie_key=None)

                logger.info(f" 频道: {channel_info.get('channel', 'Unknown')}")
                logger.info(f" 视频数: {channel_info.get('video_count', 0)}")

                # 遍历视频列表
                if "entries" in channel_info:
                    for video in channel_info["entries"]:
                        if video:
                            video_data = VideoMetadata(
                                video_id=video.get("id"),
                                channel_id=channel_info.get("channel_id", ""),
                                title=video.get("title", "Unknown"),
                                description=video.get("description", ""),
                                duration=video.get("duration", 0),
                                view_count=video.get("view_count", 0),
                                upload_date=video.get("upload_date"),
                                webpage_url=video.get("webpage_url"),
                                content_hash=ContentHasher.generate_hash(video.get("id", "")),
                            )
                            videos.append(video_data)

                logger.info(f" 成功采集 {len(videos)} 个视频")
                return videos

        except Exception as e:
            logger.error(f" yt-dlp 采集失败: {str(e)}")
            raise FirecrawlError(f"yt-dlp 采集失败: {str(e)}")


def test_firecrawl_client():
    """测试Firecrawl客户端"""
    client = FirecrawlClient()

    # 测试URL验证
    valid_urls = [
        "https://www.youtube.com/channel/UC1234567890",
        "https://www.youtube.com/c/TestChannel",
        "https://www.youtube.com/@testchannel",
    ]

    for url in valid_urls:
        assert client._validate_channel_url(url), f"URL验证失败: {url}"
    print(" URL验证测试通过")

    # 测试频道ID提取
    test_url = "https://www.youtube.com/channel/UC1234567890"
    channel_id = client.extract_channel_id(test_url)
    assert channel_id == "UC1234567890", "频道ID提取失败"
    print(" 频道ID提取测试通过")

    print(" Firecrawl客户端测试完成")


if __name__ == "__main__":
    test_firecrawl_client()
