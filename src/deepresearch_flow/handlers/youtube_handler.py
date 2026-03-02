"""
Deep Research Flow - YouTube Handler
使用 langchain_community.document_loaders.YoutubeLoader 进行YouTube内容提取
支持yt-dlp降级方案具备抗封锁优化和代理支持
"""

import importlib.util
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import json


from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from core.models import VideoMetadata

logger = logging.getLogger(__name__)

# 抗封锁配置最新的浏览器User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class YtDlpLogger:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        logger.error(msg)


class YouTubeHandler:
    """
    YouTube内容处理器 - 工业级标准方案
    主要使用 langchain_community.document_loaders.YoutubeLoader
    保留 yt-dlp 作为降级方案
    """

    def __init__(self):
        """初始化处理器"""
        self._check_dependencies()
        self.proxy_config = self._load_proxy_config()

    def _check_dependencies(self) -> None:
        """检查依赖是否可用"""
        self.langchain_available = importlib.util.find_spec("langchain_community.document_loaders") is not None
        if self.langchain_available:
            logger.info("langchain_community.document_loaders.YoutubeLoader available")
        else:
            logger.error("langchain_community not available or incompatible")

        self.transcript_api_available = importlib.util.find_spec("youtube_transcript_api") is not None
        if self.transcript_api_available:
            logger.info("youtube-transcript-api available")
        else:
            logger.error("youtube-transcript-api not available")

        self.yt_dlp_available = importlib.util.find_spec("yt_dlp") is not None
        if self.yt_dlp_available:
            logger.info("yt-dlp available (fallback)")
        else:
            logger.warning("yt-dlp not available (fallback disabled)")

    def _load_proxy_config(self) -> Optional[Dict[str, str]]:
        """从环境变量加载代理配置"""
        proxy_vars = {
            "http_proxy": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
            "https_proxy": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
        }

        proxies = {k: v for k, v in proxy_vars.items() if v}
        if proxies:
            logger.info(f"Proxy configuration loaded: {proxies}")
            return proxies
        return None

    def _enhanced_logging(self, step: str, total: int = None, current: int = None) -> None:
        """
        增强的日志显示 - 话痨级详细进度

        Args:
            step: 当前步骤描述
            total: 总数量
            current: 当前数量
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        if total and current is not None:
            progress = (current / total) * 100
            print(f"[{timestamp}] [{current}/{total}]  {step} - {progress:.1f}%", flush=True)
        else:
            print(f"[{timestamp}]  {step}", flush=True)

    def _enhanced_anti_blocking(self) -> None:
        """增强的抗封锁延迟 - 包含工作时间和抖动机制"""
        base_delay = random.uniform(5, 10)

        # 工作时间延长延迟
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 18:
            base_delay *= 1.5

        # 添加抖动
        jitter = random.uniform(0.5, 2.0)
        total_delay = min(base_delay + jitter, 15)

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}]  智能抗封锁延迟: {total_delay:.1f}s", flush=True)
        # 兼容同步和异步调用场景
        # 实际上这个类目前主要是同步调用但如果在异步循环中调用time.sleep会阻塞
        # 不过目前fetch_video_data是同步方法
        time.sleep(total_delay)

    def _get_random_user_agent(self) -> str:
        """随机选择User-Agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)

    def _extract_video_id(self, url: str) -> str:
        """从YouTube URL提取视频ID"""
        import re

        patterns = [r"(?:youtube\.com/watch\?v=|youtu\.be/)([^&\n?#]+)", r"youtube\.com/embed/([^&\n?#]+)"]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"无法从URL提取视频ID: {url}")

    def _prefer_langchain_loader(self, url: str) -> bool:
        """判断是否优先使用LangChain Loader"""
        # LangChain Loader通常更稳定优先使用
        return self.langchain_available and self.transcript_api_available

    def fetch_video_data(self, url: str) -> VideoMetadata:
        """
        提取单个视频的完整数据 - 智能选择加载器

        Args:
            url: YouTube视频URL

        Returns:
            VideoMetadata 对象
        """
        self._enhanced_anti_blocking()  # 使用增强的抗封锁延迟
        self._enhanced_logging("开始提取视频数据", None, None)

        # 优先使用LangChain Loader
        if self._prefer_langchain_loader(url):
            try:
                print(f"[] 使用 LangChain YoutubeLoader 提取: {url[:50]}...", flush=True)
                return self._fetch_via_langchain(url)
            except Exception as e:
                logger.warning(f"LangChain加载失败降级到yt-dlp: {e}")
                print(f"[] LangChain加载失败降级到yt-dlp: {str(e)[:50]}", flush=True)

        # 降级到yt-dlp
        if self.yt_dlp_available:
            print(f"[] 使用 yt-dlp 提取: {url[:50]}...", flush=True)
            return self._fetch_via_yt_dlp(url)
        else:
            raise RuntimeError("所有加载器都不可用")

    def _fetch_via_langchain(self, url: str) -> VideoMetadata:
        """使用 LangChain YoutubeLoader 获取视频数据"""
        from langchain_community.document_loaders import YoutubeLoader

        video_id = self._extract_video_id(url)

        try:
            # 使用LangChain YoutubeLoader
            loader = YoutubeLoader.from_youtube_url(
                url, add_video_info=True, language=["zh-Hans", "en", "zh-Hant"], translation="en"
            )

            documents = loader.load()

            if not documents:
                raise ValueError("LangChain Loader返回空结果")

            doc = documents[0]
            metadata = doc.metadata

            # 使用youtube-transcript-api获取字幕
            transcript = self._get_transcript_with_api(video_id)

            # 构建VideoMetadata
            video_metadata = VideoMetadata(
                video_id=video_id,
                channel_id=metadata.get("channel_id", ""),
                channel_name=metadata.get("channel", ""),
                title=metadata.get("title", ""),
                description=metadata.get("description", "") or "",
                duration=metadata.get("duration"),
                view_count=metadata.get("view_count"),
                like_count=metadata.get("like_count"),
                upload_date=metadata.get("upload_date"),
                transcript=transcript,
                webpage_url=url,
                thumbnail_url=metadata.get("thumbnail"),
                tags=metadata.get("tags", []),
            )

            print(f"[] LangChain采集成功: {video_metadata.title[:50]}...", flush=True)
            print(
                f"[] 观看数: {video_metadata.view_count} | 字幕长度: {len(transcript) if transcript else 0} 字符",
                flush=True,
            )

            return video_metadata

        except Exception as e:
            logger.error(f"LangChain采集失败: {e}")
            raise

    def _get_transcript_with_api(self, video_id: str) -> Optional[str]:
        """使用youtube-transcript-api获取字幕"""
        if not self.transcript_api_available:
            logger.warning("youtube-transcript-api不可用")
            return None

        try:
            # 获取字幕列表尝试多种语言
            languages = ["zh-Hans", "en", "zh-Hant"]
            transcript_list = None

            proxies = None
            if self.proxy_config:
                proxies = {"http": self.proxy_config.get("http_proxy"), "https": self.proxy_config.get("https_proxy")}

            for lang in languages:
                try:
                    # 使用实例化方式调用以兼容旧版本API
                    # 优先使用 list -> find -> fetch 模式
                    api = YouTubeTranscriptApi()
                    transcript_list_obj = api.list(video_id)
                    transcript = transcript_list_obj.find_transcript([lang])
                    transcript_data = transcript.fetch()

                    if transcript_data:
                        transcript_list = transcript_data
                        logger.info(f"获取到{lang}字幕")
                        print(f"[] 字幕降级采集成功 ({lang})", flush=True)
                        break
                except Exception:
                    # 尝试静态方法作为后备 (虽然在新版本中已被弃用或更改但在某些版本中可能仍有效)
                    try:
                        transcript_list = YouTubeTranscriptApi.get_transcript(
                            video_id, languages=[lang], proxies=proxies
                        )
                        if transcript_list:
                            logger.info(f"通过静态方法获取到{lang}字幕")
                            print(f"[] 字幕降级采集成功 ({lang}) - 静态方法", flush=True)
                            break
                    except Exception:
                        continue

            if not transcript_list:
                logger.warning(f"无法获取视频{video_id}的字幕")
                return None

            # 格式化为纯文本
            formatter = TextFormatter()
            transcript_text = formatter.format_transcript(transcript_list)

            logger.info(f"字幕提取成功长度: {len(transcript_text)} 字符")
            return transcript_text

        except Exception as e:
            logger.warning(f"youtube-transcript-api获取字幕失败: {e}")
            return None

    def _fetch_via_yt_dlp(self, url: str) -> VideoMetadata:
        """使用 yt-dlp 获取视频数据 (降级方案)"""
        if not self.yt_dlp_available:
            raise RuntimeError("yt-dlp not available")

        import yt_dlp

        # yt-dlp 配置抗封锁优化
        ydl_opts = {
            "logger": YtDlpLogger(),
            "quiet": True,
            "no_warnings": True,
            "encoding": None,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["zh-Hans", "en", "zh-Hant"],
            "socket_timeout": 30,
            "retries": 3,
            "extractor_retries": 3,
            "cookiesfrombrowser": ("chrome",),
            "http_headers": {
                "User-Agent": self._get_random_user_agent(),
            },
        }

        # 如果有代理配置添加到yt-dlp
        if self.proxy_config:
            ydl_opts["proxy"] = self.proxy_config.get("http_proxy") or self.proxy_config.get("https_proxy")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # 解析字幕
                transcript = self._extract_transcript_from_info(info)

                # 构建VideoMetadata
                video_metadata = VideoMetadata(
                    video_id=info.get("id"),
                    channel_id=info.get("channel_id", ""),
                    channel_name=info.get("channel") or info.get("uploader", "Unknown"),
                    title=info.get("title", ""),
                    description=info.get("description", "") or "",
                    duration=info.get("duration"),
                    view_count=info.get("view_count"),
                    like_count=info.get("like_count"),
                    upload_date=info.get("upload_date"),
                    transcript=transcript,
                    webpage_url=info.get("webpage_url", url),
                    thumbnail_url=info.get("thumbnail"),
                    tags=info.get("tags", []),
                )

                print(f"[] yt-dlp采集成功: {video_metadata.title[:50]}...", flush=True)
                return video_metadata

        except Exception as e:
            logger.error(f"yt-dlp采集失败: {e}")
            raise

    def _extract_transcript_from_info(self, info: Dict[str, Any]) -> Optional[str]:
        """从yt-dlp信息中提取字幕 (保留原有逻辑)"""
        try:
            subtitles = info.get("subtitles", {})
            automatic_captions = info.get("automatic_captions", {})

            # 优先手动字幕
            for lang in ["zh-Hans", "en", "zh-Hant"]:
                if lang in subtitles and subtitles[lang]:
                    subtitle_url = subtitles[lang][0]["url"]
                    result = self._download_and_parse_subtitle(subtitle_url)
                    if result:
                        print(f"[] 已获取手动字幕: {lang}", flush=True)
                        return result

            # 降级到自动字幕
            for lang in ["zh-Hans", "en", "zh-Hant"]:
                if lang in automatic_captions and automatic_captions[lang]:
                    subtitle_url = automatic_captions[lang][0]["url"]
                    result = self._download_and_parse_subtitle(subtitle_url)
                    if result:
                        print(f"[] 已获取自动字幕: {lang}", flush=True)
                        return result

            # 如果yt-dlp字幕提取失败尝试使用youtube-transcript-api作为最后的降级方案
            video_id = info.get("id")
            if video_id:
                logger.info(f"yt-dlp未找到字幕尝试使用youtube-transcript-api: {video_id}")
                return self._get_transcript_with_api(video_id)

            logger.warning("未找到可用字幕")
            return None

        except Exception as e:
            logger.warning(f"字幕提取失败: {e}")
            return None

    def _download_and_parse_subtitle(self, subtitle_url: str) -> Optional[str]:
        """下载并解析字幕文件 (保留原有逻辑)"""
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            # 配置重试策略
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)

            session = requests.Session()
            session.mount("https://", adapter)
            session.mount("http://", adapter)

            # 使用与yt-dlp相同的User-Agent
            headers = {"User-Agent": self._get_random_user_agent()}

            response = session.get(subtitle_url, headers=headers, timeout=15)
            response.raise_for_status()

            # 检测字幕格式
            if subtitle_url.endswith(".vtt") or "fmt=vtt" in subtitle_url:
                content = self._parse_vtt_subtitles(response.text)
            else:
                content = response.text

            if content:
                print("[] yt-dlp字幕下载成功", flush=True)
                return content
            return None

        except Exception as e:
            # 这里的失败通常是429我们会尝试降级方案所以降级日志级别或明确提示
            logger.warning(f"yt-dlp原声字幕下载失败 (将尝试降级方案): {e}")
            return None

    def _parse_vtt_subtitles(self, vtt_content: str) -> str:
        """清洗VTT格式字幕 (保留原有逻辑)"""
        lines = vtt_content.split("\n")
        cleaned_lines = []

        for line in lines:
            # 跳过时间戳行
            if "-->" in line:
                continue
            # 跳过WEBVTT标记
            if line.startswith("WEBVTT"):
                continue
            # 跳过空行
            if not line.strip():
                continue
            # 跳过数字标记
            if line.strip().isdigit():
                continue

            # 清理歌词标记和特殊字符
            line = line.strip()
            if line:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def fetch_channel_data(self, channel_url: str, limit: int = 50) -> List[VideoMetadata]:
        """
        提取频道的视频列表

        Args:
            channel_url: YouTube频道URL
            limit: 限制提取的视频数量

        Returns:
            VideoMetadata 对象列表
        """
        if not self.yt_dlp_available:
            raise RuntimeError("yt-dlp not available for channel extraction")

        import yt_dlp

        # 优化URL移除查询参数并确保指向/videos标签页以获取视频列表
        # 否则yt-dlp可能会返回频道标签页列表如Home, Videos, Shorts等而不是视频
        if "youtube.com" in channel_url or "youtu.be" in channel_url:
            clean_url = channel_url.split("?")[0].split("&")[0].rstrip("/")
            if not any(clean_url.endswith(suffix) for suffix in ["/videos", "/shorts", "/streams", "/releases"]):
                print(f"[] 优化频道URL: {channel_url} -> {clean_url}/videos", flush=True)
                channel_url = f"{clean_url}/videos"

        print(f"[] 批量削减策略从{limit}个视频减少到{limit}个", flush=True)

        ydl_opts = {
            "logger": YtDlpLogger(),
            "quiet": True,
            "no_warnings": True,
            "encoding": None,
            "extract_flat": True,
            "skip_download": True,
            "playlistend": limit,
            "socket_timeout": 30,
            "retries": 3,
            "extractor_retries": 3,
            "http_headers": {
                "User-Agent": self._get_random_user_agent(),
            },
        }

        if self.proxy_config:
            ydl_opts["proxy"] = self.proxy_config.get("http_proxy") or self.proxy_config.get("https_proxy")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)

                videos = []
                entries = info.get("entries", [])

                for i, entry in enumerate(entries):
                    try:
                        video_url = entry.get("url")
                        if not video_url:
                            continue

                        # 为每个视频添加随机延迟
                        if i > 0:
                            self._enhanced_anti_blocking()

                        # 提取单个视频数据
                        video_metadata = self.fetch_video_data(video_url)
                        videos.append(video_metadata)

                        sub_len = len(video_metadata.transcript) if video_metadata.transcript else 0
                        print(
                            f"[] 采集进度: {len(videos)}/{limit} - {video_metadata.title[:50]}... (字幕: {sub_len}字)",
                            flush=True,
                        )

                        if len(videos) >= limit:  # 限制采集数量
                            break

                    except Exception as e:
                        logger.warning(f"采集视频{i}失败: {e}")
                        continue

                print(f"[] 频道采集完成共获取{len(videos)}个视频", flush=True)
                return videos

        except Exception as e:
            logger.error(f"频道数据提取失败: {e}")
            raise


def create_youtube_handler() -> YouTubeHandler:
    """
    工厂函数创建YouTube处理器实例

    Returns:
        YouTubeHandler实例
    """
    return YouTubeHandler()


if __name__ == "__main__":
    # 测试代码
    import sys

    handler = create_youtube_handler()

    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(json.dumps(handler.fetch_video_data(url), indent=2, ensure_ascii=False))
    else:
        print("Usage: python youtube_handler.py <youtube_url>")
