# Tarih kitabı RAG ve rehberli soru çözümü

## Çalışan akış

MEB 9. sınıf tarih kitabı çevrimdışı taranır. İçindekilerdeki 13 numaralı ders konusu PDF sayfa aralıklarına dönüşür. Kitabın metin katmanından alınan bloklar, kısa sayfa süsleri, etkinlik komutları, cevap alanları, değerlendirme sayfaları ve açık görsel işaretleri açısından elenir. Kalan her **aday** `source_checksum`, konu, PDF sayfası ve `bbox` ile kaydedilir. Bu işlem doğruluk onayı değildir.

Öğretmen, soru bankası denetimindeki **Konu bazlı bilgi parçaları** bölümünden metni PDF görüntüsüyle karşılaştırır. Ders bilgisi içermeyen alıntı, rubrik, görsel betimi ve yönergeleri onaylamaz. Onay DB'de kaynak sürümüyle tutulur; PDF değişirse eski onay yeni dizinde kullanılamaz.

Öğrenci bir soruda yardım istediğinde sistem test sayfasındaki konuyu kitap başlığıyla eşleştirir. Sadece eşleşen konunun öğretmen onaylı parçaları üzerinden Türkçe sözcüksel BM25 araması yapılır. Konu veya kanıt yoksa cevap üretimi durur. İlk tur soru kökünü anlamaya, sonraki tur kanıt ile seçenekleri ilişkilendirmeye yönelir. Doğrulanmış cevap şıkkı sunucu sınırını aşmaz. Destekçi yanıtı yerel Piper TTS ile okunabilir. Öğrenci, tarayıcıda Türkçe cihaz içi tanıma mevcutsa konuşarak metin yazabilir; tanıma yoksa yazı alanı kullanılır. Metin öğrenci gönderene kadar API'ye gitmez.

## Yerel hazırlama

```bash
# Docker içindeki worker, yalnız yerel ve telifli PDF'yi okur.
./baslat.sh hazirla-rag
```

Çıktı `data/derived/history-rag-v1.json` altında kalır ve Git'e eklenmez. PDF dosya adı ve checksum dizinde saklanır. Yeni kitap sürümünde komut yeniden çalıştırılır. Örnek yerel kaynakta ilk ayıklama **13 konu, 348 aday** üretmiştir; hiçbir aday kendiliğinden onaylı değildir. Kurulum için ilgili `data/meb/` ve `data/soru_bankasi/` PDF'leri gerekir.

## Öğretmen cevap anahtarı

Soru denetim ekranında cevap şıkkı ayrıca seçilir ve kaynak cevap anahtarıyla karşılaştırma kutusu işaretlenir. Bu iki alan tamamlanmadan cevap şıkkı onaylı soru kaydına giremez. Öğrenci soru API'si iki alanı da döndürmez. Doğrulanmamış cevapta destekçi doğru/yanlış iddiası kurmaz. Mevcut soru PDF'sinde cevap anahtarını otomatik bağlayan güvenilir eşleme bulunmadığından toplu şık aktarımı yapılmaz.

Mevcut konuşma isteği istemciden gelen tur numarasını içerdiği için cevap anahtarı, öğrencinin seçtiği şıkkın doğru olup olmadığına dair ipucu üretmekte kullanılmaz. Bu davranış ancak sunucuda tutulan ve atlanamayan oturum adımları ile kapalı değerlendirme tamamlandığında açılabilir.

## Kaggle ince ayar deneyi

`experiments/kaggle/history_tutor_sft.py`, **öğretmenin yazdığı** kısa Türkçe destekçi diyaloglarıyla `Qwen/Qwen3-4B-Instruct-2507` üzerinde QLoRA çalıştırmak için hazırdır. Kaggle notebook ve veri kümesi private olmalıdır. `dialogues.jsonl` her satırda `question_id`, `split` (`train`/`eval`), `prompt`, `completion`, `stage`, `source_ids` alanları içerir. Eğitim ve değerlendirme soru kimlikleri ayrıdır. En az 200 eğitim ve 40 kapalı değerlendirme turu olmadan runner çalışmaz; ham PDF paragraflarından otomatik cevap etiketi üretmez. Kaggle notebook süresi ve erişimi gerçek zamanlı öğrenci konuşması için servis garantisi vermediğinden şu an canlı yol deterministik ve yereldir. Eğitilmiş adaptör, kalite eşiklerinden geçtikten sonra yerel çıkarım servisine bağlanmalıdır.

Örnek **sentetik** veri satırı:

```json
{"question_id":"synthetic-q1","split":"train","prompt":"Konu: Tarih öğrenmenin faydaları. Öğrenci: A şıkkı olabilir. Kanıt: ortak hafıza toplumsal kimliği destekler.","completion":"A şıkkındaki hangi ifade ortak hafızayla ilişkili? Kaynaktaki bilgiyle karşılaştırıp gerekçeni söyle.","stage":"justify","source_ids":["synthetic-source-1"]}
```

Modeli açma koşulları: kapalı soru bazlı değerlendirmede konu eşleştirme ve kanıt bulma, cevapsız kalma, kaynak sadakati, cevabı erken ifşa, Türkçe doğallık, TTS anlaşılırlığı ve gecikme ölçülür. Öğretmen, hatalı kanıtı ve yanıltıcı pedagojik ipucunu ayrı etiketler. Model çıktısı yalnız kısa bir destekçi sözü önerir; kaynak ID'leri ve cevap anahtarı model tarafından oluşturulmaz. Model eğitimi tamamlanmış veya bu eşikler geçilmiş gibi kabul edilmez.

## Dayanak

- Lewis ve diğerleri, [Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401): kaynağı model parametrelerinden ayrı tutma.
- Liu ve diğerleri, [Lost in the Middle](https://arxiv.org/abs/2307.03172): tüm kitabı uzun bağlam olarak vermek yerine konu ve kısa kanıt seçme.
- Asai ve diğerleri, [Self-RAG](https://arxiv.org/abs/2310.11511): uygun kanıt yokken koşulsuz üretime gitmeme.
- Education Endowment Foundation, [Metacognition and Self-Regulated Learning](https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/metacognition): öğrencinin açıklama, izleme ve gerekçelendirme adımlarını destekleme.
- [TRL SFTTrainer](https://huggingface.co/docs/trl/sft_trainer), [Qwen model kartı](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), [Kaggle Notebooks](https://www.kaggle.com/docs/notebooks): private QLoRA deneyinin araç ve işletim sınırları.
