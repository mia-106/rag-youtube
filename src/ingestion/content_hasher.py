"""
内容哈希工具模块
用于生成内容哈希确保数据唯一性
"""

import hashlib
from typing import Dict, Any, Optional


class ContentHasher:
    """内容哈希生成器"""

    @staticmethod
    def generate_hash(data: str) -> str:
        """
        生成SHA-256哈希值

        Args:
            data: 输入字符串

        Returns:
            64位十六进制哈希值
        """
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_video_hash(video_metadata: Dict[str, Any]) -> str:
        """
        生成视频内容哈希

        哈希策略
        1. 视频标题 + 描述 + 时长
        2. 去除时间相关的可变字段
        3. 规范化文本内容

        Args:
            video_metadata: 视频元数据字典

        Returns:
            视频内容哈希值
        """
        # 提取核心字段
        core_content = f"{video_metadata.get('title', '')}{video_metadata.get('description', '')}{video_metadata.get('duration', '')}"

        # 清理空白字符
        normalized_content = " ".join(core_content.split())

        return ContentHasher.generate_hash(normalized_content)

    @staticmethod
    def generate_subtitle_hash(subtitle_text: str) -> str:
        """
        生成字幕内容哈希

        Args:
            subtitle_text: 字幕文本内容

        Returns:
            字幕内容哈希值
        """
        # 清理字幕格式去除时间戳
        lines = subtitle_text.strip().split("\n")
        content_lines = [line for line in lines if not line.strip().startswith(("00:", "01:", "02:"))]

        normalized_content = " ".join(content_lines)

        return ContentHasher.generate_hash(normalized_content)

    @staticmethod
    def generate_chunk_hash(content: str, video_summary: str, timestamp: Optional[str] = None) -> str:
        """
        生成分块内容哈希

        Args:
            content: 分块文本内容
            video_summary: 视频摘要
            timestamp: 时间戳可选

        Returns:
            分块内容哈希值
        """
        # 构建哈希内容
        hash_content = f"{content}{video_summary}"
        if timestamp:
            hash_content += timestamp

        return ContentHasher.generate_hash(hash_content)

    @staticmethod
    def verify_hash(data, hash_value: str) -> bool:
        """
        验证哈希值

        Args:
            data: 原始数据可以是字符串或字典
            hash_value: 要验证的哈希值

        Returns:
            验证结果
        """
        if isinstance(data, dict):
            computed_hash = ContentHasher.generate_video_hash(data)
        else:
            computed_hash = ContentHasher.generate_hash(data)
        return computed_hash == hash_value


def test_content_hasher():
    """测试内容哈希功能"""
    # 测试基本哈希
    test_text = "这是一个测试文本"
    hash1 = ContentHasher.generate_hash(test_text)
    hash2 = ContentHasher.generate_hash(test_text)
    assert hash1 == hash2, "相同文本应生成相同哈希"
    print(f" 基本哈希测试通过: {hash1[:16]}...")

    # 测试视频哈希
    video_metadata = {
        "title": "Python编程教程",
        "description": "学习Python基础知识",
        "duration": 3600,
        "view_count": 100000,
    }
    video_hash = ContentHasher.generate_video_hash(video_metadata)
    print(f" 视频哈希测试通过: {video_hash[:16]}...")

    # 测试字幕哈希
    subtitle_text = "00:00:00 --> 00:00:05\n欢迎来到Python教程\n\n00:00:05 --> 00:00:10\n今天我们将学习基础语法"
    subtitle_hash = ContentHasher.generate_subtitle_hash(subtitle_text)
    print(f" 字幕哈希测试通过: {subtitle_hash[:16]}...")

    # 测试哈希验证
    is_valid = ContentHasher.verify_hash(test_text, hash1)
    assert is_valid, "哈希验证应返回True"
    print(" 哈希验证测试通过")


if __name__ == "__main__":
    test_content_hasher()
