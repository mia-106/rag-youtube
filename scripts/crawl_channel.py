#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube频道数据采集脚本
完整演示Firecrawl + Record Manager的工作流程
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List

# 处理Windows控制台编码问题
# if sys.platform.startswith('win'):
#     import codecs
#     sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
#     sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

# 添加项目根目录
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.firecrawl_client import FirecrawlClient
from src.ingestion.record_manager import RecordManager
from src.core.config import settings


async def crawl_youtube_channel(channel_url: str):
    """
    爬取YouTube频道的完整流程

    Args:
        channel_url: YouTube频道URL
    """
    print("=" * 60)
    print("YouTube频道数据采集开始")
    print("=" * 60)
    print(f"频道URL: {channel_url}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    # 强制实时刷新
    print(flush=True)

    try:
        # 1. 加载配置
        print("DEBUG: 开始加载配置...", flush=True)
        try:
            from src.core.config import settings

            print(f"DEBUG: 配置加载成功 - LOG_LEVEL: {settings.LOG_LEVEL}", flush=True)
            print(f"DEBUG: FIRECRAWL_API_KEY存在: {bool(settings.FIRECRAWL_API_KEY)}", flush=True)
        except Exception as e:
            print(f"DEBUG: 配置加载失败 - {e}", flush=True)
            raise

        # 2. 初始化客户端
        print("DEBUG: 开始初始化Firecrawl客户端...", flush=True)
        try:
            client = FirecrawlClient()
            print(f"DEBUG: 客户端初始化完成 - yt-dlp可用: {client.yt_dlp_available}", flush=True)
        except Exception as e:
            print(f"DEBUG: 客户端初始化失败 - {e}", flush=True)
            raise
        print()
        print(flush=True)

        # 3. 初始化记录管理器
        print("DEBUG: 开始初始化记录管理器...", flush=True)
        try:
            record_manager = RecordManager()
            print("DEBUG: 记录管理器初始化完成", flush=True)
        except Exception as e:
            print(f"DEBUG: 记录管理器初始化失败 - {e}", flush=True)
            raise
        print()
        print(flush=True)

        # 3.5. 检查数据库连接
        print("DEBUG: 尝试连接数据库...", flush=True)
        try:
            # 简单的数据库连接测试
            test_stats = record_manager.get_statistics()
            print("DEBUG: 数据库连接成功", flush=True)
        except Exception as e:
            print(f"DEBUG: 数据库连接失败 - {e}", flush=True)
            print("DEBUG: 跳过数据库操作，继续处理...", flush=True)
        print()
        print(flush=True)

        # 4. 爬取频道视频
        print("DEBUG: 开始爬取频道视频...", flush=True)
        videos = []

        try:
            # 检查URL类型，选择采集策略
            if "youtube.com" in channel_url or "youtu.be" in channel_url:
                print("[🎯] 检测到YouTube URL，使用LangChain YoutubeLoader...", flush=True)
                print(f"[⏰] 采集开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

                # 直接使用YouTube Handler
                from src.deepresearch_flow.handlers import create_youtube_handler

                handler = create_youtube_handler()

                if "/watch" in channel_url:
                    # 单个视频
                    print(f"[📹] 采集单个视频: {channel_url[:50]}...", flush=True)
                    start_time = datetime.now()

                    try:
                        video_metadata = handler.fetch_video_data(channel_url)
                        videos = [video_metadata]

                        elapsed = (datetime.now() - start_time).total_seconds()
                        print("[✅] 单个视频采集成功!", flush=True)
                        print(f"[📊] 视频标题: {video_metadata.title[:50]}...", flush=True)
                        print(f"[📈] 观看数: {video_metadata.view_count}", flush=True)
                        print(
                            f"[📝] 字幕长度: {len(video_metadata.transcript) if video_metadata.transcript else 0} 字符",
                            flush=True,
                        )
                        print(f"[⏱️] 采集耗时: {elapsed:.1f} 秒", flush=True)
                    except Exception as e:
                        print(f"[❌] 单个视频采集失败: {str(e)}", flush=True)
                        raise
                else:
                    # 频道
                    print(f"[📺] 采集YouTube频道视频列表: {channel_url[:50]}...", flush=True)
                    start_time = datetime.now()

                    try:
                        videos = handler.fetch_channel_data(channel_url, limit=20)

                        elapsed = (datetime.now() - start_time).total_seconds()
                        print("[✅] 频道采集完成!", flush=True)
                        print(f"[📊] 共获取 {len(videos)} 个视频", flush=True)
                        print(f"[⏱️] 采集耗时: {elapsed:.1f} 秒", flush=True)

                        # 显示前3个视频的概览
                        for i, video in enumerate(videos[:3], 1):
                            print(f"   [{i}] {video.title[:50]}... (观看: {video.view_count})", flush=True)
                    except Exception as e:
                        print(f"[❌] 频道采集失败: {str(e)}", flush=True)
                        raise
            else:
                # 非YouTube URL，使用Firecrawl
                print("[🌐] 使用Firecrawl采集...", flush=True)
                videos = await client.crawl_channel(channel_url)

            print(f"DEBUG: 爬取完成，获得 {len(videos)} 个视频", flush=True)
        except Exception as e:
            print(f"DEBUG: 爬取失败 - {e}", flush=True)
            import traceback

            traceback.print_exc()
            raise
        print()
        print(flush=True)

        # 5. 处理视频数据
        print("DEBUG: 开始处理视频数据...", flush=True)
        try:
            # 设置频道ID并显示视频列表
            for i, video in enumerate(videos):
                video.channel_id = video.channel_id or client.extract_channel_id(channel_url) or "unknown"

            # 显示采集到的视频列表
            if videos:
                print("DEBUG: 采集到的视频列表:", flush=True)
                for i, video in enumerate(videos, 1):
                    duration_str = f"{video.duration}秒" if video.duration else "N/A"
                    view_count_str = f"{video.view_count:,}" if video.view_count else "0"
                    print(f"  {i}. {video.title[:60]}...", flush=True)
                    print(f"     时长: {duration_str} | 观看: {view_count_str}", flush=True)

            print(f"DEBUG: 完成 {len(videos)} 个视频的数据处理", flush=True)
        except Exception as e:
            print(f"DEBUG: 视频数据处理失败 - {e}", flush=True)
            raise
        print()
        print(flush=True)

        # 5. 使用Record Manager管理记录
        print("DEBUG: 开始管理视频记录...", flush=True)
        export_path = None  # 初始化导出路径
        try:
            stats = record_manager.batch_insert_videos(videos)
            print(f"DEBUG: 插入 {stats['inserted']} 条记录，跳过 {stats['skipped']} 条", flush=True)
        except Exception as e:
            print(f"DEBUG: 记录管理失败 - {e}", flush=True)
            print("DEBUG: 跳过数据库操作，使用内存记录...", flush=True)
            # 创建内存记录
            stats = {"inserted": len(videos), "skipped": 0, "total": len(videos)}
        print()
        print(flush=True)

        # 6. 显示统计信息
        print("DEBUG: 开始显示采集统计...", flush=True)
        try:
            final_stats = record_manager.get_statistics()
            for key, value in final_stats.items():
                print(f"  • {key}: {value}", flush=True)
        except Exception as e:
            print(f"DEBUG: 统计信息获取失败 - {e}", flush=True)
            print("DEBUG: 使用内存统计...", flush=True)
            final_stats = {"total_videos": len(videos), "inserted": stats["inserted"], "skipped": stats["skipped"]}
            for key, value in final_stats.items():
                print(f"  • {key}: {value}", flush=True)
        print()
        print(flush=True)

        # 7. 导出记录
        print("DEBUG: 开始导出记录...", flush=True)
        try:
            export_path = f"data/crawl_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            os.makedirs("data", exist_ok=True)

            # 直接导出到文件，不依赖数据库
            import json

            videos_data = []
            for video in videos:
                video_dict = {
                    "video_id": video.video_id,
                    "channel_id": video.channel_id,
                    "channel_name": getattr(video, "channel_name", video.channel_id),
                    "title": video.title,
                    "description": video.description or "",
                    "duration": video.duration,
                    "view_count": video.view_count,
                    "like_count": getattr(video, "like_count", None),
                    "upload_date": getattr(video, "upload_date", None),
                    "webpage_url": getattr(video, "webpage_url", None),
                    "thumbnail_url": getattr(video, "thumbnail_url", None),
                    "transcript": getattr(video, "transcript", ""),
                }
                videos_data.append(video_dict)

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(videos_data, f, ensure_ascii=False, indent=2)

            print(f"DEBUG: 导出完成 - {export_path}", flush=True)
        except Exception as e:
            print(f"DEBUG: 记录导出失败 - {e}", flush=True)
            print("DEBUG: 跳过导出...", flush=True)
            export_path = None  # 导出失败时设为None
        print()
        print(flush=True)

        # 8. 显示成功信息
        print("=" * 60)
        print("数据采集完成!", flush=True)
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"总视频数: {final_stats['total_videos']}", flush=True)
        print(f"导出文件: {export_path if 'export_path' in locals() else 'N/A'}", flush=True)
        print("=" * 60)
        print(flush=True)

        return record_manager

    except Exception as e:
        print(f"❌ 数据采集失败: {str(e)}", flush=True)
        import traceback

        traceback.print_exc()
        return None


async def batch_crawl_channels(channel_urls: List[str]):
    """
    批量爬取多个频道

    Args:
        channel_urls: 频道URL列表
    """
    print("=" * 60)
    print("🚀 批量频道数据采集开始")
    print("=" * 60)
    print(f"📡 频道数量: {len(channel_urls)}")
    print()

    client = FirecrawlClient()
    record_manager = RecordManager()

    for i, channel_url in enumerate(channel_urls, 1):
        print(f"\n📡 处理频道 {i}/{len(channel_urls)}")
        print(f"   URL: {channel_url}")

        try:
            videos = await client.crawl_channel(channel_url)
            for video in videos:
                video.channel_id = client.extract_channel_id(channel_url) or "unknown"

            stats = record_manager.batch_insert_videos(videos)
            print(f"   ✅ 成功: {stats['inserted']} 条, 跳过: {stats['skipped']} 条")

        except Exception as e:
            print(f"   ❌ 失败: {str(e)}")

    # 显示最终统计
    final_stats = record_manager.get_statistics()
    print("\n" + "=" * 60)
    print("✅ 批量采集完成!")
    print(f"📊 总视频数: {final_stats['total_videos']}")
    print(f"📊 总频道数: {final_stats['total_channels']}")
    print("=" * 60)

    return record_manager


def validate_environment():
    """验证环境配置"""
    print("验证环境配置...")

    if not settings.FIRECRAWL_API_KEY:
        print("警告: FIRECRAWL_API_KEY 未设置")
        print("   请在 .env 文件中配置")
        return False

    print("OK: Firecrawl API Key 已配置")
    return True


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("YouTube Agentic RAG - 数据采集系统")
    print("=" * 60 + "\n")

    # 调试：检查命令行参数
    print(f"DEBUG: 命令行参数数量: {len(sys.argv)}")
    print(f"DEBUG: 命令行参数: {sys.argv}")
    print()

    # 验证环境
    print("DEBUG: 开始验证环境...")
    if not validate_environment():
        print("\n错误: 环境配置不完整，请检查 .env 文件")
        return

    # 检查命令行参数
    if len(sys.argv) > 1:
        # 从命令行参数获取频道URL
        channel_url = sys.argv[1]
        print("DEBUG: 使用命令行参数")
        print(f"DEBUG: URL: {channel_url}")
        print()
        # 动作前置反馈：立即提示用户
        print("[🚀] 已接收 URL，正在初始化采集流程...", flush=True)
        print()
        asyncio.run(crawl_youtube_channel(channel_url))
        return

    # 示例频道URL (实际使用时替换为真实URL)
    example_channels = [
        # "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw",  # Google for Developers
        # "https://www.youtube.com/c/Coreyms",  # Corey's Channel
    ]

    if not example_channels:
        print("\n=== 直接测试模式 ===")
        print("请输入YouTube频道URL进行测试:")
        print("格式示例:")
        print("  https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw")
        print("  https://www.youtube.com/@username")
        print("  https://www.youtube.com/c/channelname")

        channel_url = input("\n请输入频道URL (或直接回车退出): ").strip()

        if channel_url:
            print(f"\n开始采集: {channel_url}")
            # 动作前置反馈：立即提示用户
            print("[🚀] 已接收 URL，正在初始化采集流程...", flush=True)
            print()
            asyncio.run(crawl_youtube_channel(channel_url))
        else:
            print("\n操作已取消")
        return

    # 选择运行模式
    print("\n请选择运行模式:")
    print("1. 单个频道")
    print("2. 批量频道")

    choice = input("\n请输入选择 (1/2): ").strip()

    if choice == "1":
        channel_url = input("\n请输入YouTube频道URL: ").strip()
        if channel_url:
            asyncio.run(crawl_youtube_channel(channel_url))
    elif choice == "2":
        if example_channels:
            print(f"\n将批量爬取 {len(example_channels)} 个频道")
            asyncio.run(batch_crawl_channels(example_channels))
        else:
            print("错误: 没有配置批量频道")
    else:
        print("错误: 无效选择")


if __name__ == "__main__":
    main()
