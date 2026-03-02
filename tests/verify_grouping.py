import json


# Simulate the logic in generate node
def verify_grouping():
    print("Starting verification of grouping logic...")

    # Simulate retrieved documents
    # 3 chunks from same video, 1 from another
    documents = [
        json.dumps(
            {
                "id": "video_123",
                "source": "https://youtube.com/watch?v=123&t=10",
                "concept": "Video A",
                "content": "Chunk 1 content",
                "source_type": "video",
            }
        ),
        json.dumps(
            {
                "id": "video_123",
                "source": "https://youtube.com/watch?v=123&t=50",
                "concept": "Video A",
                "content": "Chunk 2 content",
                "source_type": "video",
            }
        ),
        json.dumps(
            {
                "id": "video_456",
                "source": "https://youtube.com/watch?v=456",
                "concept": "Video B",
                "content": "Video B content",
                "source_type": "video",
            }
        ),
    ]

    # --- Copy of the Logic ---
    memory_layer_parts = []
    reference_list = []

    video_count = 0
    web_count = 0

    # Track assigned IDs to deduplicate sources
    assigned_ids = {}

    # Group content by stable ID first
    grouped_docs = {}  # {stable_id: {doc_id: "...", title: "...", source: "...", content_list: []}}

    for doc_str in documents:
        try:
            doc_data = json.loads(doc_str)
            content = doc_data.get("content", "")
            source = doc_data.get("source", "")
            title = doc_data.get("concept", "Unknown Title")
            source_type = doc_data.get("source_type", "video")  # Default to video

            # Get stable ID for grouping
            # Use 'id' if available (from retrieve), else fallback to 'source' (url)
            stable_id = doc_data.get("id", source)

            if stable_id not in assigned_ids:
                if source_type == "web":
                    web_count += 1
                    doc_id = f"W{web_count}"
                else:
                    video_count += 1
                    doc_id = str(video_count)
                assigned_ids[stable_id] = doc_id

                grouped_docs[stable_id] = {
                    "doc_id": doc_id,
                    "title": title,
                    "source": source,
                    "content_list": [content],
                }
            else:
                # Append content to existing group
                grouped_docs[stable_id]["content_list"].append(content)
        except Exception:
            # Fallback for malformed docs (treat as generic video/text)
            video_count += 1
            memory_layer_parts.append(f"Document [{video_count}]:\n{doc_str}\n")

    # Build Memory Layer from Grouped Docs
    for stable_id, data in grouped_docs.items():
        doc_id = data["doc_id"]
        title = data["title"]
        source = data["source"]
        # Join content parts with a separator to indicate different chunks
        combined_content = "\n---\n".join(data["content_list"])

        memory_layer_parts.append(
            f"Document [{doc_id}]:\nTitle: {title}\nSource: {source}\nContent: {combined_content}\n"
        )

        # Keep track for the prompt instructions
        reference_list.append(f"[{doc_id}]: {source}")
    # -------------------------

    print(f"Generated {len(memory_layer_parts)} memory parts.")
    for part in memory_layer_parts:
        print(part)
        print("=" * 20)

    # Verification
    # Should have 2 docs total
    assert len(memory_layer_parts) == 2, f"Expected 2 docs, got {len(memory_layer_parts)}"

    # Doc [1] should contain Chunk 1 and Chunk 2
    assert "Chunk 1 content" in memory_layer_parts[0]
    assert "Chunk 2 content" in memory_layer_parts[0]
    assert "Document [1]" in memory_layer_parts[0]

    # Doc [2] should be Video B
    assert "Video B content" in memory_layer_parts[1]
    assert "Document [2]" in memory_layer_parts[1]

    print("✅ Verification Passed!")


if __name__ == "__main__":
    verify_grouping()
