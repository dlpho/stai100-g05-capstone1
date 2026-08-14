"""
RAG-Specific Evaluations — Context Recall, Precision, and Mean Reciprocal Rank.

Queries the live ChromaDB collection (Qwen3-Embedding-0.6B) and scores the
retrieved chunks against golden "relevant section" labels from knowledge.md.

Run:  python evals/run_evals.py --layer rag
"""
import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend", "app"))

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_data.json")


def retrieve(query, top_k=2):
    from backend.app.services.rag_service import get_chroma_collection, get_embedder
    collection = get_chroma_collection()
    embedder = get_embedder()
    q_emb = embedder.encode([query]).tolist()
    res = collection.query(query_embeddings=q_emb, n_results=top_k)
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    return [{"section": m.get("section", ""), "doc": d[:120]} for d, m in zip(docs, metas)]


def main():
    with open(GOLDEN, "r", encoding="utf-8") as f:
        golden = json.load(f)["rag"]

    import time
    t0 = time.time()
    print("Loading embedding model / ChromaDB (may download Qwen3-Embedding-0.6B on first run)...")

    precisions, recalls, rr_scores = [], [], []
    per_case = []
    for case in golden:
        try:
            hits = retrieve(case["query"], top_k=2)
        except Exception as e:
            per_case.append({"query": case["query"], "error": f"{type(e).__name__}: {e}"})
            continue

        relevant = set(case["relevant_sections"])
        got_sections = [h["section"] for h in hits]

        # Precision@2 = fraction of retrieved chunks that are relevant
        prec = sum(1 for s in got_sections if s in relevant) / max(len(hits), 1)
        # Recall@2 = fraction of relevant sections retrieved
        rec = len([s for s in got_sections if s in relevant]) / max(len(relevant), 1)
        # Reciprocal rank of the first relevant hit
        rr = 0.0
        for rank, s in enumerate(got_sections, start=1):
            if s in relevant:
                rr = 1.0 / rank
                break
        precisions.append(prec)
        recalls.append(rec)
        rr_scores.append(rr)
        per_case.append({"query": case["query"], "got_sections": got_sections,
                         "expected": case["relevant_sections"], "rr": rr})

    n = len(precisions)
    if n == 0:
        p2, r2, mrr = 0.0, 0.0, 0.0
    else:
        p2 = round(sum(precisions) / n, 3)
        r2 = round(sum(recalls) / n, 3)
        mrr = round(sum(rr_scores) / n, 3)

    results = {
        "rag": {
            "precision@2": p2,
            "recall@2": r2,
            "mrr": mrr,
            "n_cases": n,
            "elapsed_s": round(time.time() - t0, 1),
            "per_case": per_case,
        }
    }
    out = os.path.join(os.path.dirname(__file__), "metrics_rag.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
    print(f"\n[rag] wrote {out}")


if __name__ == "__main__":
    main()
