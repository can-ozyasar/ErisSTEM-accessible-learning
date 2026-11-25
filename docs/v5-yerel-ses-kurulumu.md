# V5 yerel ses adayı

Bu servis mevcut API'nin WAV üreten yerel TTS sözleşmesini uygular. V5 modeli
ve referans ses depoya dahil değildir; servis bunları indirmez. Bu talimatta
indirilen veya otomatik yüklenen bir dosya yoktur.

## Gerekli dosyalar ve ortam

- V5 eğitim çıktısı `t3_mtl23ls_v3.safetensors` (2.143.989.752 bayt),
  SHA-256 `8ec3a3312b9586a8650c38d2c8e8e8b6214851f13afbaa935ed4c9d598af8503`.
- Resmî `ResembleAI/chatterbox` modelinin
  `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18` sürümündeki `ve.pt`, `s3gen.pt`,
  `grapheme_mtl_merged_expanded_v1.json`, `conds.pt`, `Cangjie5_TC.json`;
  bunlar V5 T3 dosyasıyla aynı yerel model klasöründe olmalıdır.
- İzin kapsamında kullanılacak, en az altı saniyelik yerel referans WAV.
- Servis ortamında PyTorch, CUDA desteği, soundfile, NumPy ve
  `5de7a54aa4e5e2baadb0182dde554908b48b85c2` revizyonundaki resmî Chatterbox
  kodu. Kullanılan ortamın bağımlılıkları kurulmuş olmalıdır.

Servis yalnız T3 ağırlığının yukarıdaki özetini doğrular; diğer temel model
dosyalarının kaynağı ayrıca doğrulanmalıdır. CUDA varsayılandır; CPU için
`ERISTEM_V5_DEVICE=cpu` denenebilir, ancak hız ve bellek kullanımı ölçülmedi.

## Yerelde başlatma

Dosyalar ve bağımlılıklar hazır olduğunda, proje kökünden kendi sanal ortamınızla:

```bash
export ERISTEM_V5_MODEL_DIR=/ozel/yol/model
export ERISTEM_V5_REFERENCE_WAV=/ozel/yol/referans.wav
export PYTHONPATH=apps/api
python -m app.chatterbox_v5_service
```

Servis yalnız `127.0.0.1:8765` adresine bağlanır. Başarılı model yüklemesinden
sonra `GET /health` hazır durumunu, `POST /` ise `{"text":"..."}` için WAV
çıktısını sağlar. Metin 240 karakteri aşan parçalara ayrılır, parçalar sırayla
üretilir; bu **akışlı ilk ses** anlamına gelmez. Sesler 0,60 kazançla ve kırpma
kontrolüyle birleştirilir. Eksik veya hatalı V5 ağırlığı servis açılışını durdurur.

API aynı makine ve ağ ad alanında çalışıyorsa, API sürecinde:

```bash
export LOCAL_TTS_URL=http://127.0.0.1:8765/
export LOCAL_TTS_VOICE_CACHE_VERSION=chatterbox-v5-8ec3a331
export LOCAL_TTS_TIMEOUT_SECONDS=120
```

Farklı referans ses veya üretim ayarları kullanılırsa önbellek sürümünü de
değiştirin. API Docker içinde, servis host üzerinde çalışıyorsa `127.0.0.1`
aynı ad alanı değildir; bu yerleşim için ayrıca güvenli ağ yapılandırması
gerekir. Servis henüz Docker entegrasyonu, gerçek modelle uçtan uca üretim,
uzun metin kalitesi veya GPU gecikmesi açısından bu yerel ortamda sınanmadı.

## Kaggle üretim koşusunun dayanıklılığı

`experiments/kaggle/tts_v5_demo_generate.py`, her ses biriminden sonra
`run_records.json` dosyasını aynı çıktı klasöründe atomik olarak günceller.
Kernel kesilirse başarılı ve checksum'ı hâlâ eşleşen WAV'lar atlanır; eksik,
bozuk veya önceki koşuda başarısız olan birimler yeniden üretilir. Yeniden
başlatma; girdi manifesti, eğitilmiş T3 ağırlığı, runner kodu, model/referans
sürümleri, seed, referans WAV, örnekleme hızı ve çalışma ortamı aynı değilse
karışık çıktı üretmek yerine güvenli biçimde durur. Farklı bir girdi veya kod
sürümü için yeni bir çıktı klasörü kullanın.

Koşu kaydı GPU adı, Python/CUDA ve ilgili paket sürümlerini, model ve kaynak
checksum'larını, birim başına süreleri ve devam edilen/yeniden üretilen birim
sayılarını içerir; konuşulan metni kaydetmez. `ERISTEM_V5_DEMO_MAX_UNIQUE` ile
yapılan sınırlı koşu yalnız smoke testidir ve ürün paketine kurulamaz; tam paket
ancak tüm gerekli metin birimleri başarıyla üretildiğinde yükleyiciye verilir.
Rakam içeren sesler ayrıca telaffuz incelemesi için bekletilir. Üretilmiş WAV'lar
dinleme kontrolü tamamlanana kadar adaydır; otomatik çıktı dinleyici onayı veya
ses kalitesi üstünlüğü kanıtı değildir.
