"""
记录管理器模块
管理数据采集记录防止重复抓取
"""

from typing import List, Optional, Set
from datetime import datetime
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.models import VideoMetadata


class RecordManager:
    """记录管理器 - 防重复机制"""

    def __init__(self):
        # 使用内存存储作为演示生产环境应使用数据库
        self.video_records: dict = {}
        self.content_hashes: Set[str] = set()
        self.channel_videos: dict = {}

    def check_duplicate(self, content_hash: str) -> bool:
        """
        检查内容哈希是否已存在

        Args:
            content_hash: 内容哈希值

        Returns:
            True表示已存在False表示新内容
        """
        return content_hash in self.content_hashes

    def insert_video_record(self, video: VideoMetadata) -> bool:
        """
        插入视频记录

        Args:
            video: 视频元数据

        Returns:
            插入是否成功
        """
        # 检查重复
        if self.check_duplicate(video.content_hash):
            print(f" 视频已存在跳过: {video.title[:50]}...")
            return False

        # 插入记录
        self.video_records[video.video_id] = video
        self.content_hashes.add(video.content_hash)

        # 更新频道映射
        if video.channel_id not in self.channel_videos:
            self.channel_videos[video.channel_id] = []
        self.channel_videos[video.channel_id].append(video.video_id)

        print(f" 新增视频记录: {video.title[:50]}...")
        return True

    def update_video_record(self, video_id: str, updates: dict) -> bool:
        """
        更新视频记录

        Args:
            video_id: 视频ID
            updates: 更新字段字典

        Returns:
            更新是否成功
        """
        if video_id not in self.video_records:
            print(f" 视频记录不存在: {video_id}")
            return False

        video = self.video_records[video_id]
        for key, value in updates.items():
            if hasattr(video, key):
                setattr(video, key, value)

        video.updated_at = datetime.now()
        print(f" 更新视频记录: {video.title[:50]}...")
        return True

    def get_video_by_id(self, video_id: str) -> Optional[VideoMetadata]:
        """
        根据ID获取视频

        Args:
            video_id: 视频ID

        Returns:
            视频元数据或None
        """
        return self.video_records.get(video_id)

    def get_channel_videos(self, channel_id: str) -> List[VideoMetadata]:
        """
        获取频道的所有视频

        Args:
            channel_id: 频道ID

        Returns:
            视频列表
        """
        video_ids = self.channel_videos.get(channel_id, [])
        return [self.video_records[vid] for vid in video_ids if vid in self.video_records]

    def get_all_videos(self) -> List[VideoMetadata]:
        """
        获取所有视频记录

        Returns:
            所有视频列表
        """
        return list(self.video_records.values())

    def get_statistics(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        total_videos = len(self.video_records)
        total_channels = len(self.channel_videos)
        total_content_hashes = len(self.content_hashes)

        return {
            "total_videos": total_videos,
            "total_channels": total_channels,
            "unique_content_hashes": total_content_hashes,
            "duplicate_prevented": 0,  # 实际实现中应统计
        }

    def batch_insert_videos(self, videos: List[VideoMetadata]) -> dict:
        """
        批量插入视频

        Args:
            videos: 视频列表

        Returns:
            插入统计信息
        """
        inserted = 0
        skipped = 0

        for video in videos:
            if self.insert_video_record(video):
                inserted += 1
            else:
                skipped += 1

        return {"inserted": inserted, "skipped": skipped, "total": len(videos)}

    def cleanup_old_records(self, days: int = 30) -> int:
        """
        清理旧记录

        Args:
            days: 保留天数

        Returns:
            清理的记录数
        """
        # 实际实现中应基于时间戳清理
        # 这里只是演示
        return 0

    def export_records(self, filepath: str) -> bool:
        """
        导出记录到文件

        Args:
            filepath: 导出文件路径

        Returns:
            导出是否成功
        """
        try:
            import json
            from src.core.models import to_dict

            data = {
                "videos": [to_dict(video) for video in self.video_records.values()],
                "statistics": self.get_statistics(),
                "exported_at": datetime.now().isoformat(),
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            print(f" 记录已导出到: {filepath}")
            return True

        except Exception as e:
            print(f" 导出失败: {str(e)}")
            return False

    def import_records(self, filepath: str) -> bool:
        """
        从文件导入记录

        Args:
            filepath: 导入文件路径

        Returns:
            导入是否成功
        """
        try:
            import json
            from src.core.models import from_dict, VideoMetadata

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for video_data in data.get("videos", []):
                video = from_dict(video_data, VideoMetadata)
                self.video_records[video.video_id] = video
                self.content_hashes.add(video.content_hash)

                if video.channel_id not in self.channel_videos:
                    self.channel_videos[video.channel_id] = []
                self.channel_videos[video.channel_id].append(video.video_id)

            print(f" 成功导入 {len(self.video_records)} 条记录")
            return True

        except Exception as e:
            print(f" 导入失败: {str(e)}")
            return False


def test_record_manager():
    """测试记录管理器"""
    manager = RecordManager()

    # 测试插入视频
    video1 = VideoMetadata(
        video_id="video1",
        channel_id="channel1",
        title="测试视频1",
        description="这是一个测试视频",
        content_hash="hash1",
    )

    video2 = VideoMetadata(
        video_id="video2",
        channel_id="channel1",
        title="测试视频2",
        description="这是另一个测试视频",
        content_hash="hash2",
    )

    # 插入第一条记录
    result1 = manager.insert_video_record(video1)
    assert result1, "插入第一条记录应成功"
    print(" 插入第一条记录成功")

    # 插入第二条记录
    result2 = manager.insert_video_record(video2)
    assert result2, "插入第二条记录应成功"
    print(" 插入第二条记录成功")

    # 测试重复检查
    duplicate_video = VideoMetadata(
        video_id="video3",
        channel_id="channel1",
        title="重复视频",
        description="这是一个重复的视频",
        content_hash="hash1",  # 相同的哈希
    )

    result3 = manager.insert_video_record(duplicate_video)
    assert not result3, "插入重复记录应失败"
    print(" 重复检查功能正常")

    # 测试获取视频
    retrieved = manager.get_video_by_id("video1")
    assert retrieved is not None, "应能获取视频"
    assert retrieved.title == "测试视频1", "视频信息应匹配"
    print(" 获取视频功能正常")

    # 测试统计信息
    stats = manager.get_statistics()
    assert stats["total_videos"] == 2, "统计信息应正确"
    print(f" 统计信息: {stats}")

    print(" 记录管理器测试完成")


if __name__ == "__main__":
    test_record_manager()
