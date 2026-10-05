# Commit stratejisi / Commit strategy

Her commit tek bir doğrulanabilir değişiklik grubunu içermeli; gerçek MEB kaynağı veya türetilmiş içeriği asla içermemelidir. Commit öncesinde `git status --ignored` ile `data/meb/` ve `data/derived/` altında hassas dosya görünmediği kontrol edilir.

Önerilen sıralama:

1. `chore: proje iskeleti ve yerel veri koruması` — yapılandırma, `.gitignore`, Docker, CI ve iki dilli README.
2. `feat(api): kaynak koordinatlı güvenli yayın akışı` — API şeması, RBAC, denetim kaydı ve testler.
3. `feat(web): erişilebilir öğrenci ve öğretmen arayüzü` — PWA, semantik HTML ve öğretmen düzeltme ekranı.
4. `feat(pipeline): izole belge işleme hattı` — yalnız worker/şema/testler, hiçbir telifli artefact olmadan.

Each commit must contain one verifiable change set and must never include real MEB source material or derived content. Before committing, use `git status --ignored` to verify sensitive files remain under `data/meb/` or `data/derived/`.

Suggested sequence is the Turkish list above. Commit only after its relevant lint, test, build, and security checks pass.
