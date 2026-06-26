import os
import re

from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
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
# Semantic Section Chunking (Markdown heading based)
# --------------------------------------------------

def split_policy(documents):

    text = documents[0].page_content

    lines = text.split("\n")

    sections = []
    current_lines = []

    for line in lines:

        is_heading = re.match(r"^#{1,6}\s+", line)

        if is_heading:

            if current_lines:
                sections.append("\n".join(current_lines).strip())

            current_lines = [line]

        else:

            current_lines.append(line)

    if current_lines:
        sections.append("\n".join(current_lines).strip())

    chunks = []

    for section in sections:

        section = section.strip()

        if not section:
            continue

        metadata = extract_metadata(section)

        chunks.append(

            Document(

                page_content=section,

                metadata=metadata

            )

        )

    return chunks


# --------------------------------------------------
# Metadata Extraction
# --------------------------------------------------

def extract_metadata(text):

    metadata = {

        "section": "general",

        "decision": "general",

        "product_category": "general",

        "refund_window": -1,

        "contains_fraud_policy": False,

        "contains_shipping_policy": False,

        "contains_gold_policy": False,

        "requires_manual_review": False,

    }

    lower = text.lower()

    heading = re.search(
        r"^#+\s+(.*)",
        text,
        re.MULTILINE,
    )

    if heading:

        metadata["section"] = heading.group(1).strip()

    section = metadata["section"].lower()

    # ---------------------------------------
    # Decision
    # ---------------------------------------

    if "approval" in section:

        metadata["decision"] = "approve"

    elif "rejection" in section:

        metadata["decision"] = "reject"

    elif (

        "escalation" in section

        or

        "boundary"

        in section

        or

        "damaged"

        in section

        or

        "manual review"

        in section

        or

        "wrong item"

        in section

        or

        "goodwill"

        in section

        or

        "lost shipment"

        in section

    ):

        metadata["decision"] = "escalate"

    # ---------------------------------------
    # Product Category
    # ---------------------------------------

    for category in [

        "physical",

        "digital",

        "perishable",

        "electronics",

        "apparel",

    ]:

        if category in lower:

            metadata["product_category"] = category

            break

    # ---------------------------------------
    # Refund Window
    # ---------------------------------------

    days = re.findall(r"(\d+)\s*days", lower)

    if days:

        metadata["refund_window"] = int(days[0])

    # ---------------------------------------
    # Flags
    # ---------------------------------------

    metadata["contains_fraud_policy"] = (

        "fraud" in lower

    )

    metadata["contains_shipping_policy"] = (

        "shipping" in lower

        or

        "delivery" in lower

    )

    metadata["contains_gold_policy"] = (

        "gold" in lower

    )

    metadata["requires_manual_review"] = (

        metadata["decision"] == "escalate"

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

def upload_to_pinecone(chunks):

    pc = Pinecone(api_key=PINECONE_API_KEY)

    index = pc.Index(INDEX_NAME)

    print("Deleting existing vectors...")

    index.delete(delete_all=True)

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