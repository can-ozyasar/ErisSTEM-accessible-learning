# ADR 0002: Web PWA ve özel kaynak sınırı

Durum: Kabul edildi.

Öğrenci mobil öncelikli PWA, öğretmen masaüstü öncelikli web deneyimidir. Yerel HTML ve MathML tercih edilir; ARIA yalnız gerekli yerde kullanılır. Gerçek MEB PDF'leri, türev sayfa görselleri ve tam dönüştürülmüş içerik depoya alınmaz. Öğrenciler yükleme yapamaz; gelecekteki yetkili yükleme akışı MIME/magic-byte, sayfa sayısı, boyut ve izole worker kontrollerine tabi olacaktır.
