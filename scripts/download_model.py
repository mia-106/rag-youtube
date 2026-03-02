import sys
from sentence_transformers import SentenceTransformer
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_model():
    model_name = "BAAI/bge-m3"
    print(f"⏳ Downloading model: {model_name}...")
    try:
        # This will download and cache the model
        model = SentenceTransformer(model_name)
        print("✅ Model downloaded successfully!")

        # Verify dimensions
        dim = model.get_sentence_embedding_dimension()
        print(f"✅ Model dimensions: {dim}")

    except Exception as e:
        print(f"❌ Download failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    download_model()
