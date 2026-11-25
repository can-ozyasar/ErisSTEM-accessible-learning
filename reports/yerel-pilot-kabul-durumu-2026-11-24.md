# ErişSTEM yerel pilot kabul durumu — 24 Kasım 2026

## Kapsam

Bu rapor, görme engelli öğrencinin yerelde çalışan AYT Tarih denemesini
bağımsız çözmesi için hazırlanan pilotun teknik kabul durumunu özetler. Bu
rapor kullanıcı başarısı, öğrenme etkisi veya insan öğretmen eşdeğerliği iddia
etmez.

## Geçen kapılar

| Kapı | Kanıt | Sonuç |
| --- | --- | --- |
| Çalışan paket | Docker içinden `active_pack_mode()` ve `active_tasks()` | `licensed_local_pilot`, 63 soru |
| Kaynak bütünlüğü | Paket yüklenirken PDF checksum, sayfa sayısı ve bbox doğrulaması | Geçti |
| Aktif sınav gizliliği | Sınav/koçluk testleri | Cevap ve açıklama teslim öncesi açılmıyor |
| Koçluk akışı | Yanlış yanıtta iki ardışık tur testi | Geçti; ikinci tur sonrasında kaynaklı açıklama |
| Oturum güvenilirliği | 100 tekrarlı oturum ve eşzamanlı yazma testleri | Geçti |
| API/servis sağlığı | Docker `api`, `db`, `tts`, `exam-maintenance` sağlık kontrolü | Geçti |
| Web birim katmanı | `npm run lint`, `npm run test` | Lint temiz; 15 test geçti |
| Web üretim derlemesi | `docker compose build web` (Node 20) | Geçti |
| Web E2E | Playwright erişilebilirlik, sesli/klavye gezinme senaryoları | 16 test geçti |
| Kaynak inceleme pipeline'ı | OGM/Qwen/pilot test seçkisi | 19 test geçti |

API/koçluk seçkisinde ayrıca 36 test geçti. Bu testlerin bir bölümü bellek içi
veya geçici SQLite ortamı kullanır; üretim kullanıcı testi yerine geçmez.

## RAG genişletme araştırması

Önceki 63 soruluk paketin dışındaki 84 kaynak yetersiz adayı için Qwen3
Embedding 4B dense retrieval araştırıldı. Cevap anahtarı ve çözüm metni
kullanılmadan yapılan iki aşamalı AI kaynak denetiminde 18 aday tam kapsam
uzlaşmasına ulaştı; 65 aday ilk aşamada, bir aday da anlaşmazlık çözümünde
çekimser bırakıldı.

Bu 18 aday için non-runtime kanıt paketi geçerli olsa da öğrenci paketine
eklenmemiştir. AI incelemesi insan/PDF kaynak onayı değildir. 19 adayın PDF
kesitleri yerel inceleme ekranında bulunur:

`http://localhost:5173/v1/review/ogm-ayt-evidence/`

Ayrıntılı retrieval raporu:
[ayt-tarih-qwen-dense-kalibrasyon-2026-11-24.md](ayt-tarih-qwen-dense-kalibrasyon-2026-11-24.md)

## Açık kapılar

| Konu | Gerekli kanıt | Mevcut durum |
| --- | --- | --- |
| Yeni 18 soru | Proje sahibi/uzman PDF kesiti kararı, paket bütünlük testi | İnceleme bekliyor |
| Kullanılabilirlik | NVDA+Firefox ve TalkBack+Chrome görev kontrolü, katılımcı gözlemi | Teknik E2E geçti; kullanıcı gözlemi yok |
| Komut kalitesi | En az 100 Türkçe komut varyantı ölçümü | Güvenli ayrıştırma testleri var; sayısal saha raporu eksik |
| Performans | p50/p95 komut, koçluk ve TTS ölçümü | Retrieval araştırma gecikmesi ölçüldü; uçtan uca cihaz raporu eksik |
| QLoRA | Ayrılmış gerçek geliştirme kümesinde base karşılaştırması | Araştırma artefaktı; canlı ürün yoluna bağlı değil |

## Dürüst ürün ifadesi

Mevcut sürüm, **63 kaynak-bağlı AYT Tarih sorusuyla yerelde çalışan teknik
pilot**tur. Kullanıcı testi yapılmadan bağımsız kullanım başarısı, öğrenme
kazanımı veya öğretmen eşdeğerliği iddia edilmemelidir.
