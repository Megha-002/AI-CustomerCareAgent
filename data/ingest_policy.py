import os
import re

from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

load_dotenv()

POLICY_PATH = "data/policy.md"


# --------------------------------------------------
# Load Policy
# --------------------------------------------------

def load_policy():

    loader = TextLoader(
        POLICY_PATH,
        encoding="utf-8"
    )

    documents = loader.load()

    return documents


# --------------------------------------------------
# Split Policy
# --------------------------------------------------

def split_policy(documents):

    splitter = RecursiveCharacterTextSplitter(

        chunk_size=512,

        chunk_overlap=50,

        separators=[
            "\n# ",
            "\n## ",
            "\n### ",
            "\n\n",
            "\n",
            " ",
            ""
        ]

    )

    chunks = splitter.split_documents(documents)

    return chunks


# --------------------------------------------------
# Metadata Extraction
# --------------------------------------------------

def extract_metadata(text):

    metadata = {

        "section": "general",

        "decision": "general",

        "product_category": "general",

        "refund_window": None,

        "contains_fraud_policy": False,

        "contains_shipping_policy": False,

        "contains_gold_policy": False,

        "requires_manual_review": False,

    }

    lower = text.lower()

    # ----------------------------
    # Section
    # ----------------------------

    match = re.search(r"#\s+(.*)", text)

    if match:
        metadata["section"] = match.group(1).strip()

    # ----------------------------
    # Decision
    # ----------------------------

    if "approve" in lower:
        metadata["decision"] = "approve"

    if "reject" in lower:
        metadata["decision"] = "reject"

    if "escalate" in lower:
        metadata["decision"] = "escalate"

    # ----------------------------
    # Product Category
    # ----------------------------

    if "physical" in lower:
        metadata["product_category"] = "physical"

    elif "digital" in lower:
        metadata["product_category"] = "digital"

    elif "perishable" in lower:
        metadata["product_category"] = "perishable"

    elif "electronics" in lower:
        metadata["product_category"] = "electronics"

    elif "apparel" in lower:
        metadata["product_category"] = "apparel"

    # ----------------------------
    # Refund Window
    # ----------------------------

    if "45 days" in lower:

        metadata["refund_window"] = 45

    elif "30 days" in lower:

        metadata["refund_window"] = 30

    elif "29 days" in lower:

        metadata["refund_window"] = 29

    elif "22 days" in lower:

        metadata["refund_window"] = 22

    elif "14 days" in lower:

        metadata["refund_window"] = 14

    elif "7 days" in lower:

        metadata["refund_window"] = 7

    # ----------------------------
    # Flags
    # ----------------------------

    metadata["contains_fraud_policy"] = (
        "fraud" in lower
    )

    metadata["contains_shipping_policy"] = (
        "shipping" in lower or
        "delivery" in lower
    )

    metadata["contains_gold_policy"] = (
        "gold" in lower
    )

    metadata["requires_manual_review"] = (
        "manual_review_required" in lower or
        "manual review" in lower or
        "escalate" in lower
    )

    return metadata


# --------------------------------------------------
# Attach Metadata
# --------------------------------------------------

def tag_chunks(chunks):

    tagged = []

    for chunk in chunks:

        chunk.metadata.update(
            extract_metadata(chunk.page_content)
        )

        tagged.append(chunk)

    return tagged

# --------------------------------------------------
# Embedding Model
# --------------------------------------------------

embedding_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

# --------------------------------------------------
# Pinecone
# --------------------------------------------------

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

INDEX_NAME = "policydb"


# --------------------------------------------------
# Upload to Pinecone
# --------------------------------------------------

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

INDEX_NAME = "policydb"


def upload_to_pinecone(chunks):

    pc = Pinecone(api_key=PINECONE_API_KEY)

    index = pc.Index(INDEX_NAME)

    vectors = []

    for i, chunk in enumerate(chunks):

        embedding = embedding_model.encode(
            chunk.page_content
        ).tolist()

        metadata = {}

        for key, value in chunk.metadata.items():

             if value is not None:
                 metadata[key] = value

        metadata["text"] = chunk.page_content

        vectors.append({

            "id": f"policy-{i}",

            "values": embedding,

            "metadata": metadata

        })

    index.upsert(vectors=vectors)

    print("\n")

    print("=" * 60)

    print("UPLOAD COMPLETE")

    print("=" * 60)

    print(index.describe_index_stats())

    return index


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    documents = load_policy()

    chunks = split_policy(documents)

    tagged_chunks = tag_chunks(chunks)

    print("\n")
    print("=" * 60)
    print("POLICY CHUNKS")
    print("=" * 60)

    print(f"Total Chunks : {len(tagged_chunks)}")

    print("\n")

    for i, chunk in enumerate(tagged_chunks):

        print("=" * 60)

        print(f"Chunk {i+1}")

        print("-" * 60)

        print(chunk.metadata)

        print()

        print(chunk.page_content[:250])

        print()

    upload_to_pinecone(tagged_chunks)

    print("\nPolicy ingestion completed successfully.")


if __name__ == "__main__":

    main()