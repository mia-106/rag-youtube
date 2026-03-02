"""
上下文增强块模块
实现上下文增强块策略为每个分块添加视频摘要
"""

import re
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass


def _split_text_with_regex(text: str, separator: str, *, keep_separator: bool | Literal["start", "end"]) -> List[str]:
    if separator:
        if keep_separator:
            splits_ = re.split(f"({separator})", text)
            splits = (
                ([splits_[i] + splits_[i + 1] for i in range(0, len(splits_) - 1, 2)])
                if keep_separator == "end"
                else ([splits_[i] + splits_[i + 1] for i in range(1, len(splits_), 2)])
            )
            if len(splits_) % 2 == 0:
                splits += splits_[-1:]
            splits = ([*splits, splits_[-1]]) if keep_separator == "end" else ([splits_[0], *splits])
        else:
            splits = re.split(separator, text)
    else:
        splits = list(text)
    return [s for s in splits if s]


class RecursiveCharacterTextSplitter:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        keep_separator: bool | Literal["start", "end"] = True,
        is_separator_regex: bool = False,
        strip_whitespace: bool = True,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be > 0, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be >= 0, got {chunk_overlap}")
        if chunk_overlap > chunk_size:
            raise ValueError(
                f"Got a larger chunk overlap ({chunk_overlap}) than chunk size ({chunk_size}), should be smaller."
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]
        self.keep_separator = keep_separator
        self.is_separator_regex = is_separator_regex
        self.strip_whitespace = strip_whitespace

    def split_text(self, text: str) -> List[str]:
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        final_chunks: List[str] = []
        separator = separators[-1] if separators else ""
        new_separators: List[str] = []
        for i, sep in enumerate(separators):
            sep_pattern = sep if self.is_separator_regex else re.escape(sep)
            if not sep:
                separator = sep
                break
            if re.search(sep_pattern, text):
                separator = sep
                new_separators = separators[i + 1 :]
                break

        split_pattern = separator if self.is_separator_regex else re.escape(separator)
        splits = _split_text_with_regex(text, split_pattern, keep_separator=self.keep_separator)

        good_splits: List[str] = []
        merge_separator = "" if self.keep_separator else separator
        for split in splits:
            if len(split) < self.chunk_size:
                good_splits.append(split)
            else:
                if good_splits:
                    final_chunks.extend(self._merge_splits(good_splits, merge_separator))
                    good_splits = []
                if not new_separators:
                    final_chunks.append(split)
                else:
                    final_chunks.extend(self._split_text(split, new_separators))
        if good_splits:
            final_chunks.extend(self._merge_splits(good_splits, merge_separator))
        return final_chunks

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        separator_len = len(separator)
        docs: List[str] = []
        current_doc: List[str] = []
        total = 0
        for split in splits:
            split_len = len(split)
            if total + split_len + (separator_len if current_doc else 0) > self.chunk_size:
                if current_doc:
                    doc = separator.join(current_doc)
                    doc = doc.strip() if self.strip_whitespace else doc
                    if doc:
                        docs.append(doc)
                    while total > self.chunk_overlap or (
                        total + split_len + (separator_len if current_doc else 0) > self.chunk_size and total > 0
                    ):
                        total -= len(current_doc[0]) + (separator_len if len(current_doc) > 1 else 0)
                        current_doc = current_doc[1:]
            current_doc.append(split)
            total += split_len + (separator_len if len(current_doc) > 1 else 0)
        doc = separator.join(current_doc)
        doc = doc.strip() if self.strip_whitespace else doc
        if doc:
            docs.append(doc)
        return docs


@dataclass
class ContextualChunk:
    """上下文增强块"""

    content: str
    video_summary: str
    chunk_index: int
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    content_hash: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def enhanced_content(self) -> str:
        """获取增强后的内容包含上下文摘要"""
        return f"**视频摘要**: {self.video_summary}\n\n**内容**: {self.content}"


class ContextualChunker:
    """上下文增强分块器"""

    def __init__(self, chunk_size: int = 1000, overlap_size: int = 200):
        """
        初始化分块器

        Args:
            chunk_size: 每个分块的最大字符数
            overlap_size: 相邻分块的重叠字符数
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.overlap_size,
            separators=["\n\n", "\n", "", "", "", " ", ""],
        )

    def chunk_text(self, text: str) -> List[str]:
        """
        文本分块

        Args:
            text: 输入文本

        Returns:
            分块列表
        """
        return self.text_splitter.split_text(text)

    def add_overlap(self, chunks: List[str]) -> List[str]:
        """
        为相邻分块添加重叠

        Args:
            chunks: 原始分块列表

        Returns:
            带有重叠的分块列表
        """
        if len(chunks) <= 1:
            return chunks

        overlapped_chunks = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_chunk = overlapped_chunks[-1]
            current_chunk = chunks[i]

            # 计算重叠内容
            overlap_text = prev_chunk[-self.overlap_size :] if len(prev_chunk) > self.overlap_size else prev_chunk
            new_chunk = overlap_text + " " + current_chunk

            overlapped_chunks.append(new_chunk)

        return overlapped_chunks

    def attach_context(self, chunks: List[str], video_summary: str) -> List[ContextualChunk]:
        """
        为分块附加上下文摘要

        Args:
            chunks: 文本分块列表
            video_summary: 视频摘要

        Returns:
            上下文增强块列表
        """
        contextual_chunks = []

        for i, chunk in enumerate(chunks):
            contextual_chunk = ContextualChunk(content=chunk, video_summary=video_summary, chunk_index=i)
            contextual_chunks.append(contextual_chunk)

        return contextual_chunks

    def chunk_subtitle_blocks(self, subtitle_blocks: List[Dict[str, Any]], video_summary: str) -> List[ContextualChunk]:
        """
        处理字幕块并生成上下文增强分块

        Args:
            subtitle_blocks: 字幕块列表
            video_summary: 视频摘要

        Returns:
            上下文增强块列表
        """
        # 合并所有字幕内容
        full_text = " ".join([block["content"] for block in subtitle_blocks])

        chunks = self.chunk_text(full_text)
        contextual_chunks = self.attach_context(chunks, video_summary)

        # 分配时间戳如果有的话
        if subtitle_blocks and "start_time" in subtitle_blocks[0]:
            self._assign_timestamps(contextual_chunks, subtitle_blocks)

        return contextual_chunks

    def _assign_timestamps(self, chunks: List[ContextualChunk], subtitle_blocks: List[Dict[str, Any]]):
        """为分块分配时间戳"""
        if not subtitle_blocks:
            return

        total_chars = sum(len(block["content"]) for block in subtitle_blocks)

        for chunk in chunks:
            # 基于字符位置估算时间戳
            char_position = chunk.chunk_index * self.chunk_size
            time_ratio = char_position / total_chars if total_chars > 0 else 0

            if subtitle_blocks[-1].get("end_time"):
                video_duration = subtitle_blocks[-1]["end_time"]
                estimated_time = int(video_duration * time_ratio)

                chunk.start_time = estimated_time
                chunk.end_time = estimated_time + 30  # 假设每个分块30秒

    def chunk_by_semantic_units(self, text: str, video_summary: str) -> List[ContextualChunk]:
        """
        基于语义单元的分块更智能的方法

        Args:
            text: 输入文本
            video_summary: 视频摘要

        Returns:
            语义分块列表
        """
        # 使用段落分割
        paragraphs = text.split("\n\n")

        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            test_chunk = current_chunk + ("\n\n" if current_chunk else "") + paragraph

            if len(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph

        if current_chunk:
            chunks.append(current_chunk)

        return self.attach_context(chunks, video_summary)

    def extract_key_topics(self, text: str, num_topics: int = 3) -> List[str]:
        """
        提取关键主题简单实现

        Args:
            text: 输入文本
            num_topics: 要提取的主题数量

        Returns:
            关键主题列表
        """
        # 简单的关键词提取实际实现中可以使用更复杂的NLP方法
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        word_freq = {}

        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # 排序并返回最常见的词
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:num_topics]]

    def generate_enhanced_summary(self, text: str, key_topics: List[str]) -> str:
        """
        生成增强摘要

        Args:
            text: 输入文本
            key_topics: 关键主题

        Returns:
            增强摘要
        """
        # 提取前100个字符作为基础摘要
        base_summary = text[:200] + "..." if len(text) > 200 else text

        # 添加关键主题
        topics_str = ", ".join(key_topics) if key_topics else ""

        enhanced_summary = f"{base_summary}\n\n关键主题: {topics_str}"
        return enhanced_summary


def test_contextual_chunker():
    """测试上下文增强分块器"""
    chunker = ContextualChunker(chunk_size=200, overlap_size=50)

    # 测试文本
    test_text = """
    Python是一种高级编程语言由Guido van Rossum创建它是一种解释型面向对象动态数据类型的高级程序设计语言

    Python的设计哲学强调代码的可读性和简洁的语法相比于其他编程语言如C++或JavaPython让程序员能够用更少的代码表达想法

    Python支持多种编程范式包括面向对象编程过程式编程和函数式编程它有一个庞大而全面的标准库

    Python在数据分析人工智能Web开发自动化脚本等领域广泛应用
    """.strip()

    print(" 测试文本分块...")
    chunks = chunker.chunk_text(test_text)
    print(f" 生成 {len(chunks)} 个分块")

    for i, chunk in enumerate(chunks[:2]):  # 显示前2个分块
        print(f"\n分块 {i + 1} (长度: {len(chunk)}):")
        print(chunk[:100] + "..." if len(chunk) > 100 else chunk)

    # 测试重叠
    print("\n 测试重叠功能...")
    overlapped = chunker.add_overlap(chunks)
    print(f" 生成 {len(overlapped)} 个重叠分块")

    # 测试上下文附加
    print("\n 测试上下文附加...")
    video_summary = "Python编程语言入门教程"
    contextual_chunks = chunker.attach_context(chunks, video_summary)
    print(f" 生成 {len(contextual_chunks)} 个上下文增强块")

    print("\n第一个增强块示例:")
    first_chunk = contextual_chunks[0]
    print(f"内容: {first_chunk.content[:100]}...")
    print(f"摘要: {first_chunk.video_summary}")
    print("增强内容前100字符:")
    print(first_chunk.enhanced_content[:100] + "...")

    # 测试关键主题提取
    print("\n 测试关键主题提取...")
    key_topics = chunker.extract_key_topics(test_text, num_topics=3)
    print(f" 提取关键主题: {key_topics}")

    # 测试增强摘要
    print("\n 测试增强摘要...")
    enhanced_summary = chunker.generate_enhanced_summary(test_text, key_topics)
    print(" 增强摘要:")
    print(enhanced_summary)

    print("\n 所有测试完成")


if __name__ == "__main__":
    test_contextual_chunker()
