import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"
MIN_SCORE = 0.10


def load_chunks():
    chunks = []

    for path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")

        # Our reference files use ## headings for individual topics.
        sections = re.split(r"(?m)^##\s+", text)

        for section in sections[1:]:
            heading, separator, body = section.partition("\n")
            body = body.strip()

            if not separator or not body:
                continue

            chunks.append({
                "filename": path.name,
                "section": heading.strip(),
                "text": body,
            })

    return chunks


def retrieve(question, top_k=3):
    if not question.strip() or top_k < 1:
        return []

    chunks = load_chunks()
    if not chunks:
        return []

    documents = []
    for chunk in chunks:
        searchable_text = f"{chunk['section']}\n{chunk['text']}"

        # Keep source URLs in returned text, but don't rank URL words.
        searchable_text = re.sub(
            r"https?://\S+",
            "",
            searchable_text,
        )
        documents.append(searchable_text)

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
    )

    document_vectors = vectorizer.fit_transform(documents)
    question_vector = vectorizer.transform([question])

    scores = cosine_similarity(
        question_vector,
        document_vectors,
    )[0]

    ranked_indices = scores.argsort()[::-1]
    results = []

    for index in ranked_indices:
        score = float(scores[index])
        if score < MIN_SCORE:
            continue

        results.append({
            **chunks[index],
            "score": score,
        })

        if len(results) >= top_k:
            break

    return results
