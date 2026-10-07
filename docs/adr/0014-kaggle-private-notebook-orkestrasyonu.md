# ADR 0014: Kaggle private Notebook orkestrasyonu / private Notebook orchestration

Durum: Kabul edildi.

Kaggle GPU benchmark'larının elle Dataset ekleme, hücre yapıştırma ve output
indirme adımları tekrarlanabilirliği zayıflatır. Ancak private MEB verisini
kontrolsüz biçimde indirmek veya yanlışlıkla public Notebook/Dataset oluşturmak
kabul edilemez. Bu nedenle `kaggle_ops.py`, yalnız `data/private/` altında
oluşturulan script paketlerini kabul eder; metadata içinde private Notebook,
GPU ve tam olarak bir izinli Dataset kaynağını doğrular. Uzak Notebook
oluşturma/güncelleme/çalıştırma yalnız `push-notebook --apply` ile mümkündür.
Çıktı alma, ham artefact yerine adları sabit içeriksiz JSON raporlarıyla
allowlist'e alınmıştır ve checksum manifesti üretir.

Status: Accepted.

Manual Dataset attachment, cell pasting, and output download weaken the
reproducibility of Kaggle GPU benchmarks. Uncontrolled retrieval of private MEB
data or accidental public Notebook/Dataset creation is unacceptable. Therefore,
`kaggle_ops.py` accepts only script packages created under `data/private/`, and
verifies private Notebook metadata, GPU enablement, and exactly one declared
Dataset source. Remote creation/update/execution requires
`push-notebook --apply`. Output retrieval is allowlisted to named content-free
JSON reports and produces a checksum manifest.
