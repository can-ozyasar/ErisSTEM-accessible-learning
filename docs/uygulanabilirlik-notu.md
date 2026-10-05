# İlk uygulama notu

İlk hedef için gerçek MEB verisi kullanılmadan, kaynak koordinatlı sentetik bir formül işlenir. API'nin kalıcı depo adaptörü sonraki adımda PostgreSQL'e bağlanacak biçimde sınırlandırılmıştır; bu dikey dilim deterministik demo deposu kullanır. Böylece CI, kaynak veriye erişmeden güvenlik/yayın akışını sınar.

Karar bekleyen konular:

1. MEB kaynak sürümü, erişim hukuku ve kurum yetkilendirmesi yazılı olarak sabitlenmeden gerçek PDF yüklenmeyecek.
2. Docling/PaddleOCR-VL/Granite-Docling seçimi, ayrık Dev ve Gold kümede ölçülmeden yapılmayacak.
3. Türkçe MathCAT kuralı ve TTS motoru, MathTR-Readings ile doğrulanmadan tamamlandı iddia edilmeyecek.

Sonraki teknik adım, PostgreSQL repository, S3-uyumlu nesne deposu ve ağsız/kaynak limitli worker container'ını bu kontratların arkasına eklemektir.
