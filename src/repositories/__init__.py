"""
Repository layer for data access
Provides abstract data access with database implementations
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.interfaces import IDatabaseClient
from src.core.models import VideoMetadata, SubtitleChunk, Channel


class IVideoRepository(ABC):
    """Video repository interface"""

    @abstractmethod
    async def get_by_id(self, video_id: str) -> Optional[VideoMetadata]:
        """Get video by ID"""
        pass

    @abstractmethod
    async def get_by_channel(self, channel_id: str) -> List[VideoMetadata]:
        """Get all videos for a channel"""
        pass

    @abstractmethod
    async def save(self, video: VideoMetadata) -> str:
        """Save a video"""
        pass

    @abstractmethod
    async def update(self, video: VideoMetadata) -> bool:
        """Update a video"""
        pass

    @abstractmethod
    async def delete(self, video_id: str) -> bool:
        """Delete a video"""
        pass

    @abstractmethod
    async def exists(self, video_id: str) -> bool:
        """Check if video exists"""
        pass

    @abstractmethod
    async def get_by_content_hash(self, content_hash: str) -> Optional[VideoMetadata]:
        """Get video by content hash"""
        pass


class ISubtitleChunkRepository(ABC):
    """Subtitle chunk repository interface"""

    @abstractmethod
    async def get_by_id(self, chunk_id: str) -> Optional[SubtitleChunk]:
        """Get chunk by ID"""
        pass

    @abstractmethod
    async def get_by_video(self, video_id: str) -> List[SubtitleChunk]:
        """Get all chunks for a video"""
        pass

    @abstractmethod
    async def save_many(self, chunks: List[SubtitleChunk]) -> bool:
        """Save multiple chunks"""
        pass

    @abstractmethod
    async def delete_by_video(self, video_id: str) -> bool:
        """Delete all chunks for a video"""
        pass

    @abstractmethod
    async def exists(self, content_hash: str) -> bool:
        """Check if chunk exists"""
        pass


class IChannelRepository(ABC):
    """Channel repository interface"""

    @abstractmethod
    async def get_by_id(self, channel_id: str) -> Optional[Channel]:
        """Get channel by ID"""
        pass

    @abstractmethod
    async def save(self, channel: Channel) -> str:
        """Save a channel"""
        pass

    @abstractmethod
    async def update(self, channel: Channel) -> bool:
        """Update a channel"""
        pass

    @abstractmethod
    async def delete(self, channel_id: str) -> bool:
        """Delete a channel"""
        pass


class VideoRepository(IVideoRepository):
    """Video repository implementation"""

    def __init__(self, db_client: IDatabaseClient):
        self.db = db_client

    async def get_by_id(self, video_id: str) -> Optional[VideoMetadata]:
        """Get video by ID"""
        query = """
            SELECT video_id, channel_id, title, description, duration,
                   view_count, like_count, published_at, content_hash,
                   thumbnail_url, tags, created_at, updated_at
            FROM videos
            WHERE video_id = $1
        """
        row = await self.db.fetch_one(query, {"video_id": video_id})
        if not row:
            return None

        return VideoMetadata(
            video_id=row["video_id"],
            channel_id=row["channel_id"],
            title=row["title"],
            description=row["description"],
            duration=row["duration"],
            view_count=row["view_count"],
            like_count=row["like_count"],
            published_at=row["published_at"],
            content_hash=row["content_hash"],
            thumbnail_url=row["thumbnail_url"],
            tags=row["tags"] or [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_by_channel(self, channel_id: str) -> List[VideoMetadata]:
        """Get all videos for a channel"""
        query = """
            SELECT video_id, channel_id, title, description, duration,
                   view_count, like_count, published_at, content_hash,
                   thumbnail_url, tags, created_at, updated_at
            FROM videos
            WHERE channel_id = $1
            ORDER BY published_at DESC
        """
        rows = await self.db.fetch_many(query, {"channel_id": channel_id})

        return [
            VideoMetadata(
                video_id=row["video_id"],
                channel_id=row["channel_id"],
                title=row["title"],
                description=row["description"],
                duration=row["duration"],
                view_count=row["view_count"],
                like_count=row["like_count"],
                published_at=row["published_at"],
                content_hash=row["content_hash"],
                thumbnail_url=row["thumbnail_url"],
                tags=row["tags"] or [],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def save(self, video: VideoMetadata) -> str:
        """Save a video"""
        query = """
            INSERT INTO videos (
                video_id, channel_id, title, description, duration,
                view_count, like_count, published_at, content_hash,
                thumbnail_url, tags
            ) VALUES (
                $video_id, $channel_id, $title, $description, $duration,
                $view_count, $like_count, $published_at, $content_hash,
                $thumbnail_url, $tags
            )
            ON CONFLICT (video_id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                view_count = EXCLUDED.view_count,
                updated_at = CURRENT_TIMESTAMP
            RETURNING video_id
        """
        return await self.db.fetch_val(
            query,
            {
                "video_id": video.video_id,
                "channel_id": video.channel_id,
                "title": video.title,
                "description": video.description,
                "duration": video.duration,
                "view_count": video.view_count,
                "like_count": video.like_count,
                "published_at": video.published_at,
                "content_hash": video.content_hash,
                "thumbnail_url": video.thumbnail_url,
                "tags": video.tags,
            },
        )

    async def update(self, video: VideoMetadata) -> bool:
        """Update a video"""
        query = """
            UPDATE videos
            SET title = $title,
                description = $description,
                view_count = $view_count,
                updated_at = CURRENT_TIMESTAMP
            WHERE video_id = $video_id
        """
        result = await self.db.execute(
            query,
            {
                "video_id": video.video_id,
                "title": video.title,
                "description": video.description,
                "view_count": video.view_count,
            },
        )
        return result is not None

    async def delete(self, video_id: str) -> bool:
        """Delete a video"""
        query = "DELETE FROM videos WHERE video_id = $1"
        await self.db.execute(query, {"video_id": video_id})
        return True

    async def exists(self, video_id: str) -> bool:
        """Check if video exists"""
        query = "SELECT 1 FROM videos WHERE video_id = $1 LIMIT 1"
        result = await self.db.fetch_val(query, {"video_id": video_id})
        return result is not None

    async def get_by_content_hash(self, content_hash: str) -> Optional[VideoMetadata]:
        """Get video by content hash"""
        query = """
            SELECT video_id, channel_id, title, description, duration,
                   view_count, like_count, published_at, content_hash,
                   thumbnail_url, tags, created_at, updated_at
            FROM videos
            WHERE content_hash = $content_hash
            LIMIT 1
        """
        row = await self.db.fetch_one(query, {"content_hash": content_hash})
        if not row:
            return None

        return VideoMetadata(
            video_id=row["video_id"],
            channel_id=row["channel_id"],
            title=row["title"],
            description=row["description"],
            duration=row["duration"],
            view_count=row["view_count"],
            like_count=row["like_count"],
            published_at=row["published_at"],
            content_hash=row["content_hash"],
            thumbnail_url=row["thumbnail_url"],
            tags=row["tags"] or [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class SubtitleChunkRepository(ISubtitleChunkRepository):
    """Subtitle chunk repository implementation"""

    def __init__(self, db_client: IDatabaseClient):
        self.db = db_client

    async def get_by_id(self, chunk_id: str) -> Optional[SubtitleChunk]:
        """Get chunk by ID"""
        query = """
            SELECT chunk_id, video_id, chunk_index, content,
                   video_summary, start_time, end_time, content_hash,
                   metadata, created_at
            FROM subtitle_chunks
            WHERE chunk_id = $1
        """
        row = await self.db.fetch_one(query, {"chunk_id": chunk_id})
        if not row:
            return None

        return SubtitleChunk(
            video_id=row["video_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            video_summary=row["video_summary"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            content_hash=row["content_hash"],
            metadata=row["metadata"] or {},
            created_at=row["created_at"],
        )

    async def get_by_video(self, video_id: str) -> List[SubtitleChunk]:
        """Get all chunks for a video"""
        query = """
            SELECT chunk_id, video_id, chunk_index, content,
                   video_summary, start_time, end_time, content_hash,
                   metadata, created_at
            FROM subtitle_chunks
            WHERE video_id = $1
            ORDER BY chunk_index ASC
        """
        rows = await self.db.fetch_many(query, {"video_id": video_id})

        return [
            SubtitleChunk(
                video_id=row["video_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                video_summary=row["video_summary"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                content_hash=row["content_hash"],
                metadata=row["metadata"] or {},
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def save_many(self, chunks: List[SubtitleChunk]) -> bool:
        """Save multiple chunks"""
        await self.db.begin_transaction()

        try:
            for chunk in chunks:
                query = """
                    INSERT INTO subtitle_chunks (
                        video_id, chunk_index, content, video_summary,
                        start_time, end_time, content_hash, metadata
                    ) VALUES (
                        $video_id, $chunk_index, $content, $video_summary,
                        $start_time, $end_time, $content_hash, $metadata
                    )
                    ON CONFLICT (content_hash) DO NOTHING
                """
                await self.db.execute(
                    query,
                    {
                        "video_id": chunk.video_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "video_summary": chunk.video_summary,
                        "start_time": chunk.start_time,
                        "end_time": chunk.end_time,
                        "content_hash": chunk.content_hash,
                        "metadata": chunk.metadata,
                    },
                )

            await self.db.commit()
            return True

        except Exception as e:
            await self.db.rollback()
            raise e

    async def delete_by_video(self, video_id: str) -> bool:
        """Delete all chunks for a video"""
        query = "DELETE FROM subtitle_chunks WHERE video_id = $1"
        await self.db.execute(query, {"video_id": video_id})
        return True

    async def exists(self, content_hash: str) -> bool:
        """Check if chunk exists"""
        query = "SELECT 1 FROM subtitle_chunks WHERE content_hash = $1 LIMIT 1"
        result = await self.db.fetch_val(query, {"content_hash": content_hash})
        return result is not None


class ChannelRepository(IChannelRepository):
    """Channel repository implementation"""

    def __init__(self, db_client: IDatabaseClient):
        self.db = db_client

    async def get_by_id(self, channel_id: str) -> Optional[Channel]:
        """Get channel by ID"""
        query = """
            SELECT channel_id, channel_name, description,
                   subscriber_count, created_at, updated_at
            FROM channels
            WHERE channel_id = $1
        """
        row = await self.db.fetch_one(query, {"channel_id": channel_id})
        if not row:
            return None

        return Channel(
            channel_id=row["channel_id"],
            channel_name=row["channel_name"],
            description=row["description"],
            subscriber_count=row["subscriber_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def save(self, channel: Channel) -> str:
        """Save a channel"""
        query = """
            INSERT INTO channels (
                channel_id, channel_name, description, subscriber_count
            ) VALUES (
                $channel_id, $channel_name, $description, $subscriber_count
            )
            ON CONFLICT (channel_id) DO UPDATE SET
                channel_name = EXCLUDED.channel_name,
                description = EXCLUDED.description,
                subscriber_count = EXCLUDED.subscriber_count,
                updated_at = CURRENT_TIMESTAMP
            RETURNING channel_id
        """
        return await self.db.fetch_val(
            query,
            {
                "channel_id": channel.channel_id,
                "channel_name": channel.channel_name,
                "description": channel.description,
                "subscriber_count": channel.subscriber_count,
            },
        )

    async def update(self, channel: Channel) -> bool:
        """Update a channel"""
        query = """
            UPDATE channels
            SET channel_name = $channel_name,
                description = $description,
                subscriber_count = $subscriber_count,
                updated_at = CURRENT_TIMESTAMP
            WHERE channel_id = $channel_id
        """
        result = await self.db.execute(
            query,
            {
                "channel_id": channel.channel_id,
                "channel_name": channel.channel_name,
                "description": channel.description,
                "subscriber_count": channel.subscriber_count,
            },
        )
        return result is not None

    async def delete(self, channel_id: str) -> bool:
        """Delete a channel"""
        query = "DELETE FROM channels WHERE channel_id = $1"
        await self.db.execute(query, {"channel_id": channel_id})
        return True
