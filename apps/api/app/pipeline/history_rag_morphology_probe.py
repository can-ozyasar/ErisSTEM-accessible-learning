"""Conservative plural-form retrieval probe. This is not a Turkish stemmer."""
from __future__ import annotations
from ..history_rag import terms, retrieve


def normalize_words(text):
    words=[]
    for word in terms(text):
        # A narrow heuristic; can still conflate unrelated words.
        if len(word) >= 7 and word.endswith(('lar', 'ler')):
            word=word[:-3]
        words.append(word)
    return words


def retrieve_plural_probe(index, approved_ids, topic, query, k=3):
    originals={c['id']:c for c in index['chunks']}
    normalized={'sections':index['sections'], 'chunks':[
        {**c, 'text':' '.join(normalize_words(c['text']))} for c in index['chunks']]}
    hits=retrieve(normalized,approved_ids,topic,' '.join(normalize_words(query)),k)
    return [{**originals[c['id']], 'score':c['score']} for c in hits]
