# ErişSTEM

MEB STEM kaynaklarını, kaynak konumu ve öğretmen denetimini koruyarak erişilebilir öğrenme materyaline dönüştürmek için monorepo.

Bu depoda **MEB PDF'si, sayfa görüntüsü veya dönüştürülmüş gerçek kitap içeriği bulunmaz**. Yetkili olarak edinilen MEB kaynakları yalnızca yerelde `data/meb/` altında işlenebilir; PDF'ler ve türetilmiş EPUB/BRF çıktıları Git tarafından yok sayılır ve GitHub'a gönderilmez. Demo, telif açısından güvenli sentetik bir geometri örneğidir.

## İlk dikey dilim

- Kaynak koordinatlı belge öğeleri (`page`, `bbox`, `checksum`, işlem adımı).
- Güven kuralları: formül şema/render denetimi geçmeden yayımlanamaz.
- Öğrenci okuyucusu: semantik başlıklar, MathML, kaynak/denetim durumu ve klavye kısayolları.
- Öğretmen kuyruğu: düşük güvenli formülü düzeltme, sürüm/audit kaydı, onaylayıcıyla yayın.

## Çalıştırma

```bash
docker compose up --build
```

API: `http://localhost:8000/docs` · Web: `http://localhost:5173`

Yerelde:

```bash
cd apps/api && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]' && uvicorn app.main:app --reload
cd apps/web && npm install && npm run dev
```

Demo yetkileri API'de yalnızca geliştirme amacıyla `X-Role` başlığıyla seçilir: `student`, `teacher`, `reviewer`, `admin`. Üretimde OIDC doğrulanmış claim'leri bu bağımlılığı beslemelidir.

Yetkili yerel PDF'nin metin katmanını çıkarmak için (çıktı `data/derived/` altında kalır):

```bash
cd apps/api
python -m app.pipeline.worker --input ../../data/meb/kitap.pdf --source-root ../../data/meb --output-dir ../../data/derived
```

## Sınırlar

- Öğrencinin dosya yükleme endpoint'i yoktur.
- Belge işleme taslağı `worker` sınırında kalır; gerçek PDF ayrıştırıcıları ağsız, limitli worker içine eklenecektir.
- OCR/VLM/model seçimi benchmark olmadan sabitlenmez.

İlgili kararlar [ADR dizininde](docs/adr) ve ilk uygulama notu [burada](docs/uygulanabilirlik-notu.md).

---

# ErişSTEM — English

A monorepo for transforming MEB STEM sources into accessible learning material while preserving source location and teacher oversight.

This repository contains **no MEB PDFs, page images, or converted real textbook content**. Authorised MEB sources may be processed locally only under `data/meb/`; PDFs and derived EPUB/BRF outputs are ignored by Git and must never be pushed to GitHub. The demo uses copyright-safe synthetic geometry content.

## First vertical slice

- Source-coordinate document blocks (`page`, `bbox`, `checksum`, processing step).
- Safety rules: a formula cannot be published before schema and render validation.
- Student reader: semantic headings, MathML, source/review state, and keyboard shortcuts.
- Teacher queue: correct a low-confidence formula, preserve revision/audit history, then publish through an approver.

## Run

```bash
docker compose up --build
```

API: `http://localhost:8000/docs` · Web: `http://localhost:5173`

For local development:

```bash
cd apps/api && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]' && uvicorn app.main:app --reload
cd apps/web && npm install && npm run dev
```

The API accepts `X-Role` only for development demonstrations: `student`, `teacher`, `reviewer`, and `admin`. Production must supply these roles from verified OIDC claims.

To extract the text layer of an authorised local PDF (output remains under `data/derived/`):

```bash
cd apps/api
python -m app.pipeline.worker --input ../../data/meb/book.pdf --source-root ../../data/meb --output-dir ../../data/derived
```

## Boundaries

- Students have no source-PDF upload endpoint.
- The document-processing boundary is intentionally isolated; production parsers must run in network-restricted, resource-limited workers.
- OCR/VLM/model selection is never fixed before benchmark evidence.

See the [ADR directory](docs/adr) and the initial [implementation note](docs/uygulanabilirlik-notu.md).
