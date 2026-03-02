import json
import os
import glob
from pathlib import Path
import re


def clean_filename(title):
    """Clean filename to be safe for file system"""
    # Remove invalid characters
    return re.sub(r'[\\/*?:"<>|]', "", title)


def parse_wire_magic_transcript(transcript_json):
    """Parse YouTube's wireMagic/pb3 JSON format"""
    try:
        data = json.loads(transcript_json)
        text_parts = []

        if "events" in data:
            for event in data["events"]:
                if "segs" in event:
                    for seg in event["segs"]:
                        if "utf8" in seg:
                            text_parts.append(seg["utf8"])
                # Add newline if needed, though usually segs flow together
                # Some events might be new lines?
                # Looking at the raw data, sometimes there is a "\n" segment

        return "".join(text_parts)
    except Exception as e:
        print(f"Error parsing wireMagic format: {e}")
        return transcript_json


def extract_transcripts():
    # Find the latest crawl record file
    files = glob.glob("data/crawl_records_*.json")
    if not files:
        print("No crawl records found in data/")
        return

    latest_file = max(files, key=os.path.getctime)
    print(f"Processing latest file: {latest_file}")

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            videos = json.load(f)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Create output directory
    output_dir = Path("data/transcripts")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(videos)} videos.")

    for i, video in enumerate(videos):
        title = video.get("title", f"video_{i}")
        transcript = video.get("transcript")

        if not transcript:
            print(f"Skipping {title}: No transcript")
            continue

        print(f"Processing: {title}")

        # Determine content
        content = ""
        if isinstance(transcript, str):
            if transcript.strip().startswith("{") and '"wireMagic"' in transcript:
                # It's the JSON format
                content = parse_wire_magic_transcript(transcript)
            else:
                # Assume it's already text or VTT
                content = transcript
        else:
            content = str(transcript)

        # Save to file
        safe_title = clean_filename(title)
        output_path = output_dir / f"{safe_title}.txt"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"Title: {title}\n")
            f.write(f"URL: {video.get('webpage_url', 'N/A')}\n")
            f.write("-" * 50 + "\n\n")
            f.write(content)

        print(f"Saved to: {output_path}")


if __name__ == "__main__":
    extract_transcripts()
