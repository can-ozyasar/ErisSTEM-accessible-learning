from app.pipeline.prepare_ayt_history_qwen_calibration import build


def test_exports_answer_free_locked_input():
 qs=[{"id":f"q{i}","question":"soru","choices":["a"]*5} for i in range(120)]
 pack={"schema":"ayt-history-original-question-candidate-pack-v1","candidate_checksum":"a","corpus_checksum":"b","questions":qs}
 split={"schema":"ayt-history-candidate-split-v1","candidate_checksum":"a","records":[{"id":f"q{i}","split":"retrieval_test" if i<24 else "development"} for i in range(120)]}
 corpus={"schema":"multi-history-rag-v1","corpus_checksum":"b","books":[{"source_checksum":"s","index":{"evidence_atoms":[{"id":"x","text":"kanıt"}]}}]}
 out=build(pack,split,corpus); assert len(out["queries"])==24 and out["answer_key_accessed"] is False and "answer_label" not in str(out)
