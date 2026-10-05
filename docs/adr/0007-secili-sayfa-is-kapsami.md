# ADR 0007: Seçili sayfa kapsamı iş kimliğinin parçasıdır / Selected-page scope is part of job identity

Durum: Kabul edildi.

Öğretmen, tam kitabı değil eğitim hedefiyle ilgili belirli PDF sayfalarını seçer. Bu seçim kanonik, sıralı bir sayfa listesine dönüştürülür ve iş idempotency anahtarına kaynak SHA-256 checksum'ı ile pipeline sürümünün yanında eklenir. Böylece aynı kapsam yeniden gönderildiğinde işlem tekrarlanmaz; farklı sayfa kapsamı ise önceki taslağı ezmeden bağımsız bir taslak üretir.

Worker yalnız bu sayfalardan metin katmanı bloklarını çıkarır. Taslak belge kimliği de kapsam hash'i taşır. Gerçek PDF ve türetilmiş JSON, Git dışında özel depoda kalır; yayımlanmış içerik başlangıçta boş kalır ve öğretmen/onaylayıcı denetimi olmadan öğrenciye görünmez.

Status: Accepted.

Teachers select only the PDF pages relevant to the learning objective, not an entire book. The selection is canonicalised into an ordered page list and added to the idempotency key alongside the source SHA-256 checksum and pipeline version. Re-submitting the same scope does not repeat work; a different scope creates an independent draft without overwriting the previous one.

The worker extracts text-layer blocks only from that scope. The draft document ID also contains a scope hash. The real PDF and derived JSON remain private and outside Git; the published material begins empty and is not visible to students before teacher/reviewer approval.
