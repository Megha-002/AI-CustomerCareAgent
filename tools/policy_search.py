import os

from dotenv import load_dotenv

from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

INDEX_NAME = "policydb"

TOP_K = 3

embedding_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)


class PolicySearch:

    def __init__(self):

        self.pc = Pinecone(
            api_key=PINECONE_API_KEY
        )

        self.index = self.pc.Index(INDEX_NAME)

    def search(
        self,
        question: str,
        top_k: int = TOP_K,
    ):

        query_embedding = embedding_model.encode(
            question
        ).tolist()

        response = self.index.query(

            vector=query_embedding,

            top_k=top_k,

            include_metadata=True,

        )

        results = []

        for match in response.matches:

            results.append(

                {

                    "score": round(match.score, 4),

                    "section": match.metadata.get(
                        "section",
                        "Unknown"
                    ),

                    "decision": match.metadata.get(
                        "decision",
                        "general"
                    ),

                    "metadata": match.metadata,

                    "text": match.metadata.get(
                        "text",
                        ""
                    )

                }

            )

        return results


policy_search = PolicySearch()


if __name__ == "__main__":

    question = input(
        "\nAsk Policy Question: "
    )

    results = policy_search.search(question)

    print("\n")

    print("=" * 80)

    print("POLICY SEARCH RESULTS")

    print("=" * 80)

    for i, result in enumerate(results):

        print(f"\nResult {i+1}")

        print("-" * 80)

        print(f"Similarity : {result['score']}")

        print(f"Section    : {result['section']}")

        print(f"Decision   : {result['decision']}")

        print()

        print(result["text"])