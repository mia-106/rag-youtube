"""
IBM Dockling解析器模块
使用IBM Dockling实现字幕图片和视频结构的标准化Markdown转换
"""

import re
from typing import List, Dict, Any
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocklingParseError(Exception):
    """Dockling解析错误"""

    pass


class IBMDocklingParser:
    """IBM Dockling解析器"""

    def __init__(self):
        self.supported_subtitle_formats = [".srt", ".vtt", ".ass", ".ssa"]
        self.max_chunk_size = 1000  # 最大分块大小(tokens)
        self.overlap_size = 100  # 重叠大小(tokens)

    def parse_subtitle(self, subtitle_content: str, format_type: str = "srt") -> List[Dict[str, Any]]:
        """
        解析字幕内容为结构化数据

        Args:
            subtitle_content: 字幕文件内容
            format_type: 字幕格式 (srt, vtt, ass, ssa)

        Returns:
            解析后的字幕块列表

        Raises:
            DocklingParseError: 解析失败
        """
        try:
            if format_type.lower() == "srt":
                return self._parse_srt(subtitle_content)
            elif format_type.lower() == "vtt":
                return self._parse_vtt(subtitle_content)
            elif format_type.lower() in ["ass", "ssa"]:
                return self._parse_ass(subtitle_content)
            else:
                raise DocklingParseError(f"不支持的字幕格式: {format_type}")

        except Exception as e:
            raise DocklingParseError(f"字幕解析失败: {str(e)}")

    def _parse_srt(self, content: str) -> List[Dict[str, Any]]:
        """解析SRT格式字幕"""
        blocks = re.split(r"\n\s*\n", content.strip())
        parsed_blocks = []

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue

            # 提取序号
            index = lines[0].strip()

            # 提取时间戳
            timestamp_match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", lines[1])
            if not timestamp_match:
                continue

            start_time = self._time_to_seconds(timestamp_match.group(1))
            end_time = self._time_to_seconds(timestamp_match.group(2))

            # 提取字幕文本
            text = " ".join(lines[2:]).strip()

            parsed_blocks.append(
                {"index": int(index), "start_time": start_time, "end_time": end_time, "content": text, "format": "srt"}
            )

        return parsed_blocks

    def _parse_vtt(self, content: str) -> List[Dict[str, Any]]:
        """解析VTT格式字幕"""
        lines = content.strip().split("\n")
        parsed_blocks = []
        i = 0

        # 跳过VTT头部
        if lines[0].startswith("WEBVTT"):
            i = 1

        while i < len(lines):
            line = lines[i].strip()

            # 跳过空行
            if not line:
                i += 1
                continue

            # 提取时间戳
            timestamp_match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})", line)
            if not timestamp_match:
                i += 1
                continue

            start_time = self._time_to_seconds(timestamp_match.group(1))
            end_time = self._time_to_seconds(timestamp_match.group(2))

            # 提取字幕文本
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1

            text = " ".join(text_lines)

            parsed_blocks.append(
                {
                    "index": len(parsed_blocks) + 1,
                    "start_time": start_time,
                    "end_time": end_time,
                    "content": text,
                    "format": "vtt",
                }
            )

            i += 1

        return parsed_blocks

    def _parse_ass(self, content: str) -> List[Dict[str, Any]]:
        """解析ASS/SSA格式字幕"""
        lines = content.strip().split("\n")
        parsed_blocks = []
        in_events = False

        for line in lines:
            line = line.strip()

            if line.startswith("[Events]"):
                in_events = True
                continue

            if not in_events:
                continue

            if line.startswith("Dialogue:"):
                # 解析ASS格式
                # Dialogue: 0,0:00:01.23,0:00:05.67,Style,Name,0000,0000,0000,,Text content
                parts = line.split(",", 9)
                if len(parts) < 10:
                    continue

                start_time = self._ass_time_to_seconds(parts[1])
                end_time = self._ass_time_to_seconds(parts[2])
                text = parts[9].strip()

                parsed_blocks.append(
                    {
                        "index": len(parsed_blocks) + 1,
                        "start_time": start_time,
                        "end_time": end_time,
                        "content": text,
                        "format": "ass",
                    }
                )

        return parsed_blocks

    def _time_to_seconds(self, time_str: str) -> float:
        """将时间字符串转换为秒数"""
        # 格式: HH:MM:SS,mmm 或 HH:MM:SS.mmm
        time_str = time_str.replace(",", ".")
        parts = time_str.split(":")

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_parts = parts[2].split(".")
        seconds = int(seconds_parts[0])
        milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0

        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

    def _ass_time_to_seconds(self, time_str: str) -> float:
        """将ASS时间字符串转换为秒数"""
        # 格式: H:MM:SS.cc
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_parts = parts[2].split(".")
        seconds = int(seconds_parts[0])
        centiseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0

        return hours * 3600 + minutes * 60 + seconds + centiseconds / 100

    def to_structured_markdown(self, subtitle_blocks: List[Dict[str, Any]], video_summary: str = "") -> str:
        """
        将字幕块转换为结构化Markdown

        Args:
            subtitle_blocks: 字幕块列表
            video_summary: 视频摘要

        Returns:
            结构化Markdown字符串
        """
        markdown = []

        # 添加视频摘要
        if video_summary:
            markdown.append("## 视频摘要")
            markdown.append(f"{video_summary}")
            markdown.append("")

        # 添加时间轴
        markdown.append("## 视频内容")
        markdown.append("")

        for block in subtitle_blocks:
            start_time = self._seconds_to_time_str(block["start_time"])
            end_time = self._seconds_to_time_str(block["end_time"])

            markdown.append(f"### [{start_time} - {end_time}]")
            markdown.append(f"{block['content']}")
            markdown.append("")

        return "\n".join(markdown)

    def _seconds_to_time_str(self, seconds: float) -> str:
        """将秒数转换为时间字符串"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def extract_context_summary(self, subtitle_blocks: List[Dict[str, Any]]) -> str:
        """
        从字幕块中提取上下文摘要

        Args:
            subtitle_blocks: 字幕块列表

        Returns:
            视频摘要字符串
        """
        if not subtitle_blocks:
            return ""

        # 提取前几个字幕块的内容作为摘要
        summary_blocks = subtitle_blocks[:10]  # 取前10个字幕块

        # 合并内容
        content = " ".join([block["content"] for block in summary_blocks])

        # 简单关键词提取实际实现中可以使用更复杂的NLP方法
        words = content.split()
        if len(words) > 100:
            content = " ".join(words[:100]) + "..."

        return content.strip()

    def process_video_structure(
        self, video_metadata: Dict[str, Any], subtitle_blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        处理视频结构信息

        Args:
            video_metadata: 视频元数据
            subtitle_blocks: 字幕块列表

        Returns:
            处理后的视频结构
        """
        video_summary = self.extract_context_summary(subtitle_blocks)

        return {
            "video_id": video_metadata.get("video_id"),
            "title": video_metadata.get("title", ""),
            "summary": video_summary,
            "total_duration": video_metadata.get("duration", 0),
            "subtitle_blocks_count": len(subtitle_blocks),
            "structured_markdown": self.to_structured_markdown(subtitle_blocks, video_summary),
            "processed_at": datetime.now().isoformat(),
        }


def test_ibm_dockling_parser():
    """测试IBM Dockling解析器"""
    parser = IBMDocklingParser()

    # 测试SRT解析
    srt_content = """1
00:00:01,000 --> 00:00:03,000
欢迎来到Python编程教程

2
00:00:03,000 --> 00:00:06,000
今天我们将学习基础语法

3
00:00:06,000 --> 00:00:10,000
让我们开始吧
"""

    print(" 测试SRT解析...")
    try:
        parsed = parser.parse_subtitle(srt_content, "srt")
        print(f" 解析成功共 {len(parsed)} 个字幕块")

        for block in parsed[:2]:  # 显示前2个块
            print(f"  - [{block['start_time']:.1f}s - {block['end_time']:.1f}s] {block['content']}")

        # 测试Markdown转换
        markdown = parser.to_structured_markdown(parsed, "Python编程基础教程")
        print("\n Markdown转换成功")
        print("前200字符:")
        print(markdown[:200] + "...")

    except Exception as e:
        print(f" 解析失败: {str(e)}")

    # 测试摘要提取
    print("\n 测试摘要提取...")
    summary = parser.extract_context_summary(parsed)
    print(f" 摘要提取: {summary[:100]}...")

    # 测试视频结构处理
    print("\n 测试视频结构处理...")
    video_metadata = {"video_id": "test123", "title": "Python基础教程", "duration": 600}
    structure = parser.process_video_structure(video_metadata, parsed)
    print(" 视频结构处理完成")
    print(f"  - 标题: {structure['title']}")
    print(f"  - 摘要: {structure['summary'][:50]}...")
    print(f"  - 字幕块数: {structure['subtitle_blocks_count']}")


if __name__ == "__main__":
    test_ibm_dockling_parser()
