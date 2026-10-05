# ADR 0004: İş kuyruğu checksum ve pipeline sürümüyle idempotenttir / Idempotent jobs

Durum: Kabul edildi.

Her belge işi, kaynak PDF SHA-256 checksum'ı ve pipeline sürümü ile tanımlanır. Aynı ikili tekrar kuyruğa eklenirse ikinci iş oluşturulmaz; ilk iş döndürülür. Bu, ağ kesintisi veya öğretmen arayüzündeki tekrar tıklama nedeniyle kaynak PDF'nin gereksiz tekrar işlenmesini önler.

İş oluşturma yalnız yönetici rolüyle mümkündür. Öğrenci tarafında dosya/iş endpoint'i yoktur. İş kayıtları PostgreSQL'de tutulur; SQLite sadece yerel geliştirme ve test uyumluluğudur.

Status: Accepted. Every document job is identified by the source PDF SHA-256 checksum and pipeline version. Re-submitting the same pair returns the original job rather than creating a duplicate. Only an administrator can create jobs; SQLite is development/test compatibility only.
