import importlib.util
import sys

print(f"Python version: {sys.version}")

yt_dlp_available = importlib.util.find_spec("yt_dlp") is not None
print(f"yt_dlp available: {yt_dlp_available}")

langchain_available = importlib.util.find_spec("langchain_community.document_loaders") is not None
print(f"langchain_community.document_loaders available: {langchain_available}")
