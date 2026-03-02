import asyncio
import os
import sys
import json
from datasets import Dataset

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.graph import app
from src.core.config import settings
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.chat_models import ChatOpenAI

# Set up logging
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test Dataset
test_questions = ["How to find a niche?", "What is the one person business model?", "Why is saturation a myth?"]

test_ground_truths = [
    [
        "You do not find a niche, you create one. The most profitable niche is you. Your unique combination of interests, skills, and personality is what makes you irreplaceable."
    ],
    [
        "The goal is not to hire employees, but to use software and media to scale. You are the product. Your content is the marketing. Your products are the solution to the problems you solved for yourself."
    ],
    [
        "Market saturation only exists for those who copy. If you are authentic, you have no competition. The old economy was about fitting into a box. The new economy is about being a generalist."
    ],
]


async def generate_rag_results():
    """Run the RAG agent on test questions and collect results."""
    logger.info("🤖 Running RAG Agent on test set...")

    questions = []
    answers = []
    contexts = []
    ground_truths = []

    for i, question in enumerate(test_questions):
        logger.info(f"Processing Q{i + 1}: {question}")

        inputs = {"question": question, "retry_count": 0}

        # Run agent
        final_generation = ""
        retrieved_docs = []

        # Collect outputs
        async for output in app.astream(inputs):
            for key, value in output.items():
                if key == "generate":
                    final_generation = value.get("generation", "")
                if key == "self_correct":
                    final_generation = value.get("generation", "")
                if key == "retrieve":
                    # Extract raw content from JSON strings in documents
                    # The documents are now JSON strings: {"source":..., "concept":..., "content":...}
                    raw_docs = value.get("documents", [])
                    cleaned_docs = []
                    for doc_str in raw_docs:
                        try:
                            doc_json = json.loads(doc_str)
                            cleaned_docs.append(doc_json.get("content", ""))
                        except Exception:
                            cleaned_docs.append(doc_str)
                    retrieved_docs = cleaned_docs

        questions.append(question)
        answers.append(final_generation)
        contexts.append(retrieved_docs)
        ground_truths.append(test_ground_truths[i])

    return {
        "user_input": questions,
        "response": answers,
        "retrieved_contexts": contexts,
        "reference": [gt[0] for gt in ground_truths],  # Flatten list of lists to list of strings
    }


def main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 1. Generate Results
    data = asyncio.run(generate_rag_results())

    # 2. Convert to Dataset
    dataset = Dataset.from_dict(data)

    # 3. Configure RAGAS with Custom Models
    logger.info("⚙️ Configuring RAGAS with DeepSeek & BAAI...")

    # LLM (DeepSeek)
    llm = ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        openai_api_key=settings.DEEPSEEK_API_KEY,
        openai_api_base=settings.DEEPSEEK_BASE_URL,
        temperature=0,
    )

    # Embeddings (BAAI)
    # Note: We use the same model as in the project
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL, encode_kwargs={"normalize_embeddings": True}
    )

    # Define Custom Metric
    # style_critique = AspectCritique(...) - Skipped due to import issues in current Ragas version

    # 4. Run Evaluation
    logger.info("📊 Starting RAGAS Evaluation...")
    results = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
        llm=llm,
        embeddings=embeddings,
    )

    # 5. Output Results
    print("\n✅ Evaluation Complete!")
    print(results)

    # Save detailed results
    df = results.to_pandas()
    output_file = "ragas_evaluation_results.csv"
    df.to_csv(output_file, index=False)
    print(f"\n📄 Detailed results saved to {output_file}")


if __name__ == "__main__":
    main()
