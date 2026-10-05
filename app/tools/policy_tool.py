from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class PolicySearch:
    """Local policy retrieval with document/section-aware ranking.

    Each chunk is indexed using its filename, section heading, and body text.
    Retrieval combines TF-IDF similarity with a small lexical boost for exact
    query-term matches in document/section metadata. This helps queries such
    as "refund approval limit" reliably prioritize the refund policy.
    """

    def __init__(self) -> None:
        self.chunks: list[dict[str, str]] = []
        for path in sorted(settings.policy_path.glob("*.md")):
            section = "Overview"
            buffer: list[str] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    chunk_text = "\n".join(buffer).strip()
                    if chunk_text:
                        self.chunks.append(
                            {
                                "doc": path.name,
                                "section": section,
                                "text": chunk_text,
                            }
                        )
                    buffer = []
                    section = line.lstrip("# ").strip()
                else:
                    buffer.append(line)

            chunk_text = "\n".join(buffer).strip()
            if chunk_text:
                self.chunks.append(
                    {
                        "doc": path.name,
                        "section": section,
                        "text": chunk_text,
                    }
                )

        corpus = [
            f"{chunk['doc']} {chunk['section']} {chunk['text']}"
            for chunk in self.chunks
        ] or ["No policy documents found."]

        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(corpus)

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return set(_TOKEN_RE.findall(value.lower()))

    def search(self, query: str, k: int = 3) -> list[dict[str, str]]:
        if not self.chunks:
            return []
        query_text = query.strip()
        if not query_text:
            return []

        q = self.vectorizer.transform([query_text])
        cosine_scores = cosine_similarity(q, self.matrix)[0]
        query_tokens = self._tokens(query_text)

        combined: list[tuple[int, float]] = []
        for i, chunk in enumerate(self.chunks):
            metadata_tokens = self._tokens(f"{chunk['doc']} {chunk['section']}")
            body_tokens = self._tokens(chunk["text"])
            metadata_overlap = len(query_tokens & metadata_tokens) / max(len(query_tokens), 1)
            body_overlap = len(query_tokens & body_tokens) / max(len(query_tokens), 1)
            score = float(cosine_scores[i]) + 0.30 * metadata_overlap + 0.05 * body_overlap
            combined.append((i, score))

        combined.sort(key=lambda item: item[1], reverse=True)
        selected = combined[: max(1, k)]
        return [
            {**self.chunks[i], "score": f"{score:.3f}"}
            for i, score in selected
        ]


policy_search = PolicySearch()
