import re
from pathlib import Path
from typing import List, Dict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


POLICY_PATH = Path("data/return_policy.md")


def load_policy_sections(path: Path = POLICY_PATH) -> List[Dict[str, str]]:
    text = path.read_text(encoding="utf-8")

    sections = []
    current_title = None
    current_body = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_title:
                sections.append({
                    "title": current_title,
                    "body": "\n".join(current_body).strip()
                })
            current_title = line.replace("## ", "").strip()
            current_body = []
        elif current_title:
            current_body.append(line)

    if current_title:
        sections.append({
            "title": current_title,
            "body": "\n".join(current_body).strip()
        })

    return sections


class PolicyRetriever:
    def __init__(self):
        self.sections = load_policy_sections()
        self.documents = [
            f"{section['title']}\n{section['body']}"
            for section in self.sections
        ]

        # Character n-grams work reasonably across English and Arabic for a small prototype.
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            lowercase=True
        )
        self.matrix = self.vectorizer.fit_transform(self.documents)

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, str]]:
        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix)[0]

        ranked_indices = scores.argsort()[::-1][:top_k]

        results = []
        for idx in ranked_indices:
            results.append({
                "title": self.sections[idx]["title"],
                "body": self.sections[idx]["body"],
                "score": float(scores[idx])
            })

        return results


def format_policy_context(results: List[Dict[str, str]]) -> str:
    chunks = []
    for item in results:
        chunks.append(
            f"### {item['title']}\n"
            f"{item['body']}\n"
            f"retrieval_score={item['score']:.3f}"
        )
    return "\n\n".join(chunks)