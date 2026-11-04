import shutil
import subprocess
from pathlib import Path

import pytest

from app.history_rag import rank_chunks, terms


def test_compiled_bm25_matches_python_source_order(tmp_path):
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("C++ compiler unavailable")
    source = Path(__file__).parents[3] / "experiments/retrieval/bm25_batch.cpp"
    binary = tmp_path / "bm25_batch"
    subprocess.run([compiler, "-O2", "-std=c++17", str(source), "-o", str(binary)],
                   check=True, capture_output=True)
    docs = [
        {"id": "a", "page": 3, "text": "Lozan Antlaşması diplomasi ve barış görüşmeleri."},
        {"id": "b", "page": 2, "text": "İki savaş arasında ekonomik değişim yaşandı."},
        {"id": "c", "page": 4, "text": "Lozan görüşmeleri sonucunda yeni düzen oluştu."},
    ]
    queries = ["Lozan görüşmeleri", "ekonomik değişim"]
    lines = [f"{len(docs)} {len(queries)} 3"]
    lines.extend(f'{doc["id"]}\t{doc["page"]}\t{" ".join(terms(doc["text"]))}' for doc in docs)
    lines.extend(" ".join(terms(query)) for query in queries)
    output = subprocess.run([str(binary)], input="\n".join(lines) + "\n",
                            text=True, check=True, capture_output=True).stdout.splitlines()
    for query in queries:
        count = int(output.pop(0).split("\t")[0])
        actual = [output.pop(0).split("\t")[0] for _ in range(count)]
        expected = [item["id"] for item in rank_chunks(docs, query, limit=3)]
        assert actual == expected
