# Tarih RAG: kaynak parçası kalitesi ve araştırma

25 Ekim 2026. Öğretmen incelemesinde PDF 81'de rol oynama etkinliği adımları ders bilgisi adayı olarak göründü. Aday oluşturma, PDF metin blokları ve basit metin kuralları ile yapılır; BM25 araması bunun ardından yalnız öğretmen onaylı parçalara uygulanır. Dolayısıyla etkinlik parçasının inceleme listesine girmesi BM25'in ilgili sözcüğü seçmesinden önce gerçekleşen bir **kaynak ayıklama hatasıdır**. BM25 ayrıca onaylı parçalarda sözcük örtüşmesiyle ilgili ama kanıt açısından yetersiz metni üst sıralara getirebilir; bu ayrı ölçülmelidir.

## Araştırma ve uygulama kararları

- [Document Segmentation Matters for RAG](https://aclanthology.org/2025.findings-acl.422/) çok büyük parçaların ilgisiz içerik, çok küçük parçaların bağlam kaybı yaratabildiğini gösterir. Bu kitaptaki PDF blokları pedagojik paragraf sınırı garanti etmez; örneğin bir etkinlik metni iki ayrı bloğa bölünebilir. Buradaki çıkarım: blok kimliği ve koordinatını koruyarak paragraf devamlılığı ve bölüm/etkinlik bağlamı ayrıca gözden geçirilmelidir. Bu çalışma bizim kitaptaki optimum parçalama yöntemini kanıtlamaz.
- [HyReC-QA](https://www.sciencedirect.com/science/article/pii/S0957417426026163) ders kitabı sorularında kelime temelli ve anlamsal aramayı birleştirme ve yeniden sıralamayı inceler. Önerilen ablation: BM25, dense, hibrit RRF ve gerekirse reranker karşılaştırması; yalnız soru veya seçilmiş şıkkın gösterilmesi ürün aşamasına göre kararlaştırılır. Makaledeki sonuçlar bu Türkçe kitapta doğrulanmış sonuçlar değildir.
- [HiChunk](https://aclanthology.org/2026.acl-long.1372/) belge hiyerarşisi ve değişken kanıt granülerliğini inceler. Bunun buradaki pratik karşılığı önce bölüm/sayfa/komşu blok ilişkisini izlemek ve kaynak koordinatlarını korumaktır; pahalı hiyerarşik model uygulamasının faydası burada henüz gösterilmedi.

## Güvenli ilk düzeltme

`candidate_review_warnings` açık etkinlik adımları, bazı emir cümleleri ve olası görsel açıklamaları için öğretmen ekranında uyarı üretir. Uyarılar otomatik sınıflandırma, doğrulama veya yayın kararı değildir. Mevcut kaynak kimlikleri, dizin, onaylar ve arama davranışı değişmez. Önceden onaylanan şüpheli parçalarda kullanıcı uyarıyı görüp onayı geri alabilir; onaylı parça düzeltilmedikçe retrieval'da hâlâ kullanılabilir. Öğretmen yanlış alarmları kaynakla karşılaştırarak değerlendirmelidir.

Dizin üzerindeki kural taraması 348 adayda 5 etkinlik ve 7 olası görsel açıklaması uyarısı verdi; bu sayılar kalite, precision veya recall değildir. PDF 81'de kullanıcı tarafından gösterilen iki parçanın ikisi ve üçüncü etkinlik parçası işaretlenir. Geriye kalan hatalı parçalar bulunabilir; basit kurallar tüm belgeleri tanımaz. PDF metin katmanı bazı kelimeleri bölüyor: örneğin `cevap layınız`; bu nedenle birkaç emir için bölünmüş biçimler de işaretlenir. İlişkili parçalarda otomatik birleştirme yapılmaz: yanlış sıralama, koordinat ve onay değişimi riski önce değerlendirilmelidir.

## Bir sonraki kontrollü değerlendirme

Öğretmen, rastgele seçilmiş ve bölüm/sayfa kategorileri gözetilmiş örnekleri ders bilgisi / etkinlik / görsel başlığı / eksik bağlam / diğer olarak etiketlesin. Kör inceleme ile uyarıların precision ve recall değerlerini pay/payda ve güven aralıklarıyla hesapla; onaylanmış kaynaklardan da örnekler dahil et. İndeks güncellemesinde eski chunk ID'lerinin durumunu ve onay kaybını önceden raporla, doğrulanmış onayları otomatik taşımak veya silmek yerine sürüm ilişkisini denetle. Ayrı soru-kanit etiketleri ile BM25 ve hibrit arama için Recall@k, MRR ve yanlış kanıt oranını değerlendir; son test setini seçimde kullanma. Daha sonra öğretmen onaylı sınırları ve kaynak bağlamını koruyan parçalama prototipini yalnız karşılaştırma dizininde ölç.

## 13 bölümde kör denetim ve kimlik bütünlüğü

İlk indeksin 348 satırında 347 benzersiz parça vardır; bir PDF bloğu aynı kimlik ve tüm alanlarla iki kez kaydedilmiştir (PDF 92). `load_index` yalnız birebir aynı kayıtları bellekte tekilleştirir; aynı kimlikle farklı içerik gelirse hata verir. İndeks dosyası ve öğretmen onayları değiştirilmez. Kimlikler korunur; tekrarlı kopya BM25 belgesine veya inceleme ekranına ikinci kez girmez.

`history_rag_audit.py`, kaynak checksum'ı doğrulanan benzersiz indeksin her bölümünden sabit seed ile eşit sayıda rastgele örnek alır. `data/private/history-rag-audit-v1/sample.json`: 13 bölüm × 5 = 65 örnek; PDF'de indeks dışı kalan bloklar bu örneklemin dışındadır. Paket uyarıları göstermeden etiketlenebilir: `review-v2.html` tamamen yereldir, kaynak sayfası ve metni gösterir; farklı hata türleri ayrı seçilir. PDF'yi fiziksel PDF sayfası numarasıyla ayrıca açın, gerekiyorsa çevre sayfaya ve kaynak konumuna bakın. İnceleme kesin değilse işaretlemeden bırakın. İndirme düğmesi kısmi çalışmayı da `history-rag-reviewed.json` olarak kaydeder. Tarayıcıdaki düzenlemeler yenileme ile kaybolabilir: önce indirilmeli. Daha sonra mevcut JSON'dan `history_rag_audit_view` komutuyla yeni HTML hazırlanarak devam edilebilir. Sınıflandırma öğrenci yayını, eğitim verisi veya öğretmen kaynak onayını değiştirmez.

İncelenmiş JSON, `evaluate` komutuna verildiğinde kimlik ve içerik doğrulamasından sonra seçilen örneklerde uyarı-hata kesişimini, pay ve paydaları hesaplar. Çıktı kısmi ise yalnız mevcut gözlemlerdir; kısmi etiketlerin rasgele seçildiği varsayılmamalıdır. Farklı bölüm büyüklükleri nedeniyle bunları tüm dizine ait ağırlıklandırılmamış genel oran olarak sunmayın. Diğer inceleyenlerin kör ve bağımsız değerlendirmesiyle uyuşmazlıklar ayrıca ölçülmelidir. Uyarıların tespit oranı mevcut uyarı türlerinin bir birleşimidir; hata türü başına ve kaynak reddi gibi ölçütler ilave bir insan değerlendirmesi gerektirir.

Değerlendirme örneği (indirilen dosya `data/private/history-rag-audit-v1/reviewed.json` altına yerleştirildikten sonra):

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_audit evaluate \
  --source data/meb/tarih-9sinif-ders-kitabi_20261006.pdf --index data/derived/history-rag-v1.json \
  --sample data/private/history-rag-audit-v1/reviewed.json --output data/private/history-rag-audit-v1/report.json
```

[HiChunk](https://aclanthology.org/2026.acl-long.1372/) kanıtların ve parça sınırlarının ayrı etiketlenmesinin önemini; [AutoChunker](https://aclanthology.org/2025.acl-industry.69/) gürültü ve bağlam bütünlüğünü ayrı ölçme ihtiyacını tartışır. Bu protokol, yayınlardaki sistemlerin aynısını uygulamaz veya performanslarını varsaymaz.

## İlk yapay zekâ incelemesi (geçici)

Codex, 65 örneği PDF'deki kaynak bölgeleriyle karşılaştırarak `data/private/history-rag-audit-v1/codex-reviewed-v1.json` dosyasında etiketledi; ölçüm `codex-report-v1.json` içindedir. Bunlar öğretmen veya bağımsız uzman etiketleri değildir ve mevcut kaynak onaylarını değiştirmez. Her parçaya baskın tek sorun etiketi verilmiştir; bir parçada birden fazla sorun bulunabilir. Özellikle `extraction_error` sözcük içi istenmeyen boşlukları da kapsar: bu etiket, tarih bilgisinin yanlış olduğunu veya parçanın kesinlikle anlaşılamadığını göstermez.

Örnek dağılımı: 7 ders bilgisi, 27 çıkarım hatası, 11 eksik/bağlamı kopmuş parça, 8 görsel açıklaması veya onunla karışmış metin, 3 etkinlik, 9 diğer (ör. rubrik veya şiir). Mevcut uyarı 65 parçadan birini işaretledi; bu parça sorunlu olarak etiketlendi. Protokolün `bad` kümesine giren 58 parçanın yalnızca biri işaretlendi (1/58). 58, yanlış tarih bilgisi sayısı değildir; temkinli biçimde mevcut haliyle inceleme/düzeltme gerektirdiği düşünülen parçaların sayısıdır. Bunlar bölüm başına eşit örnekleme ilişkin betimleyici sonuçlardır; tüm indekse genellenemez. İnceleyen aynı zamanda kuralları geliştiren yapay zekâdır; kör, bağımsız uzman değerlendirmesi sayılmaz.

Bir sonraki adım: PDF yerleşimini, başlık ve paragraf sınırlarını, sözcük bölünmelerini ve metin türünü ayrı ele alan bir aday çıkarma hattı hazırlamak; bu 65 örneği geliştirme verisi olarak kullanmak ve önceden görülmemiş, bölüm büyüklüklerine göre raporlanmış ayrı bir örneklemde uzmanla doğrulamak. İndeksin dışında bırakılan ders bilgileri için PDF sayfalarından ayrıca örneklenmeden kaçırılan içerik oranı ölçülemez. Tek başına uyarı duyarlılığı, soru-cevap doğruluğu veya model başarısı değildir.

## Yerleşim incelemesi ve ikinci örneklem

`history_rag_layout_audit` deneysel araçtır. Kaynak kutusuyla kesişen PDF satırlarını inceler, yönerge/görsel işaretleri ve eksik parça sınırları için uyarı verir. Satır sonundaki görünmez tirelerin sözcükleri böldüğünü tespit eder; yalnız kaynak satırlarından üretilen metin mevcut indeks metniyle tam uyuşursa, görünmez tireyle bölünen sözcükler için düzeltme önerisi sunar. Görünür tireleri kaldırmaz. Öneri, metnin doğruluğunun kanıtı değildir; üretim indeksi veya onayları değiştirilmez.

Geliştirmede kullanılan 65 etiketli örnekte eski uyarı 1/58, deneysel uyarı 49/58 sorunlu olarak etiketlenmiş parçayı işaretledi; deneysel uyarının işaretlediği 49 parçanın tümü sorunlu olarak etiketliydi. Kurallar bu örneklere bakılarak hazırlandığından bu geliştirme sonucu bağımsız bir performans tahmini değildir.

İlk 65 parça kimliği dışlanarak, her bölümden beşer parça sabit seed ile seçildi (`holdout-v2.json`). Codex kaynak görsellerini inceleyerek bunları `holdout-codex-reviewed-v1.json` içinde etiketledi. Bu ikinci örneklemde 60 parça inceleme/düzeltme gerektiriyor olarak etiketlendi: eski uyarı 4/60, deneysel uyarı 44/60 tanesini işaretledi; sırasıyla işaretlenen 4 ve 44 parçanın tümü bu kümeye dahildi. İlk örneklemle kimlik olarak ayrık olsa da kullanıcı tarafından önceden gösterilen bir Çatalhöyük parçası bu örnekleme girdi; ayrıca aynı yapay zekâ hem kuralları geliştirdi hem etiketledi. Dolayısıyla sonuç bağımsız veya tümüyle görülmemiş uzman testi değildir. Oranlar bölüm büyüklüklerine göre ağırlıklandırılmadı; tüm kitaba, soru çözme doğruluğuna veya çıkarım dışında kalmış bloklara genellenemez. Bilgi içeren görsel açıklamaları, yalnızca metin çıkarma kusurları ve bağlam eksiklikleri de sorunlu kümesine dahildir; bu sayılar yanlış bilgi sayısı değildir.

Değerlendirme tekrarı (etiketlenmiş dosya `--holdout` olarak verilir; yeni rapor adı gerekir):

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_layout_audit \
  --source data/meb/tarih-9sinif-ders-kitabi_20261006.pdf \
  --index data/derived/history-rag-v1.json \
  --development data/private/history-rag-audit-v1/codex-reviewed-v1.json \
  --holdout data/private/history-rag-audit-v1/holdout-codex-reviewed-v1.json \
  --evaluate-holdout --output data/private/history-rag-audit-v1/holdout-report-repeat.json
```

Sonraki deney: yerleşimde tablo ve rubrik hücrelerini, alıntı kaynağını ve paragraf devamlarını açık biçimde modellemek; seçilmeyen kaynak bloklarını da örnekleyerek kapsama kaybını ölçmek. Yeni kuralları ölçmek için bu iki veri kümesinin dışında, mümkünse bağımsız uzman etiketli yeni bir test ayrılmalıdır.

## Rubrik, kaynak atfı ve indeks dışı blok deneyi

Deneysel yerleşim denetimine rubrik dili ve parçanın hemen altında görünen ancak parçaya dahil edilmemiş kaynak atfı için uyarılar eklendi. Bunlar bağlama dayalı inceleme işaretleridir; kesin sınıflandırma veya otomatik ret değildir. Daha önce incelenmiş ikinci örneklemde deneysel kuralların işaretlediği sorunlu parça sayısı 44/60'tan 48/60'a çıktı; işaretlenen 48'in tamamı Codex'in sorunlu etiketleriyle örtüştü. Yeni kurallar bu örnekte gözlenen hatalardan geliştirildiği için bu sonuç artık bağımsız test performansı değildir. Ayrıca alıntılar, görseller ve biçim kusurları bu tanımda sorunlu sayılabilir; bu, tarihsel yanlışlık demek değildir.

`history_rag_coverage_audit`, indeksin kapsadığı bölüm sayfalarında PyMuPDF'nin çıkardığı en az 40 karakterli metin bloklarını envanterler; indeks kimliğiyle eşleşmeyenlerden her bölüm için sabit tohumla 3 örnek seçer. Kod blokların koordinatlarını, metnini ve kaynak checksum'ını doğrular. OCR yapılamayan görseller, daha kısa bloklar, bölüm aralıkları dışında kalan sayfalar ve aynı bilginin başka bir indeks parçasında bulunup bulunmadığı bu çalışmanın kapsamı dışındadır. Bu nedenle sonuç doğrudan bilgi kaybı, soru cevaplama recall'u veya bütün kitap kapsamı değildir.

Codex 39 örneği kaynak görselleriyle karşılaştırdı: 6 blok bağlamı ve atfı korunarak potansiyel olarak yararlı, 29 blok mevcut kanıt amacı için uygun değil, 4 blok belirsiz olarak değerlendirildi. Yararlı örnekler kaynak alıntıları, zaman çizelgesi ve tarihsel görsel açıklaması içerir. Bunlar uzman doğrulaması veya doğrudan indekse alınma kararı değildir; alıntıların kaynağı ve bağlamı ayrıca korunmalıdır. Bölüm örnek sayıları eşit olduğundan sonuç tüm bloklara doğrudan genellenmez. Ayrıntılar `data/private/history-rag-audit-v1/omitted-codex-reviewed-v1.json` ve `omitted-codex-report-v1.json` dosyalarındadır.

Tekrar oluşturma ve etiketli örneği ölçme (yeni çıktı adları kullanın):

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_coverage_audit \
  --source data/meb/tarih-9sinif-ders-kitabi_20261006.pdf --index data/derived/history-rag-v1.json \
  --output data/private/history-rag-audit-v1/omitted-sample-repeat.json
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_coverage_audit \
  --source data/meb/tarih-9sinif-ders-kitabi_20261006.pdf --index data/derived/history-rag-v1.json \
  --reviewed data/private/history-rag-audit-v1/omitted-codex-reviewed-v1.json \
  --output data/private/history-rag-audit-v1/omitted-report-repeat.json
```

## Kaynak bağlamlı aday ve soru üzerinden mekanizma denemesi

`history_rag_candidate_experiment` üretim dışı bir aday havuzu oluşturur: mevcut 347 benzersiz parçanın deneysel sürümü ve indeks dışı örneklemde Codex'in potansiyel yararlı bulduğu 6 blok. Her adayın farklı bir deneysel kimliği, eski kimliği, kaynak checksum'ı, sayfası ve metin bölgeleri vardır; deneysel kimlik hiçbir öğretmen onayını devralmaz. Görünmez satır sonu tiresi için doğrulanabilir öneriler, geometrik olarak tek anlamlı komşu devamları ve yakın atıflar ayrı bölgeler olarak saklanır. Özellikle açık bir alıntının bitişik paragraflarını en fazla üç adım takip eder. Bu geometrik sezgiler kaynak ilişkisinin doğruluğunu kanıtlamaz; ilgisiz veya eksik bağlam ve atıf üretebilir. Adayların hiçbirini otomatik onaylamaz veya üretim indeksine yazmaz.

Son yerel üretimde 353 adayın 8'inde ek bağlam, 32'sinde olası kaynak atfı kaydedildi; bunlar doğrulanmış atıf sayıları değildir. Örneğin PDF 198'de Gök Türkler alıntısının devam paragrafları ve alttaki atfı ayrı koordinatlarla bağlandı; sayfa 104 ve 44'teki atıflar da adaylara iliştirildi. Atıflar metnin tarihsel doğruluğunu garanti etmez.

`history_rag_retrieval_probe` aynı BM25 ve bölüm kapısını kullanarak 6 elle yazılmış soruda iki araştırma havuzunu karşılaştırdı. Önceden belirlenen hedef blok, eski 347 aday havuzunda ilk üçte 0/6, genişletilen havuzda 6/6 bulundu. Bu, özellikle bu altı blok eklendikten ve sorular onların içeriğine göre yazıldıktan sonra yapılmış bir mekanizma kontrolüdür; bağımsız test, anlamsal recall, soru çözme başarısı veya genellenebilir kalite artışı değildir. Diğer ilgili kaynaklar da bulunabilir. İki havuzdaki tüm adaylar onaylıymış gibi varsayılarak arandı; dolayısıyla üretimde yalnız öğretmen onaylı parçaları kullanan sistemin sonucu değildir. Örneğin İpek Yolu sorusunda eski havuzun ilk üçünde rubrik metinleri de göründü; genişletilmiş havuzda da bazıları devam etti.

Tekrarlama (çıktı dosyaları mevcut olmamalıdır):

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_candidate_experiment \
  --source data/meb/tarih-9sinif-ders-kitabi_20261006.pdf --index data/derived/history-rag-v1.json \
  --omitted-reviewed data/private/history-rag-audit-v1/omitted-codex-reviewed-v1.json \
  --output data/private/history-rag-audit-v1/experimental-candidates-repeat.json
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_retrieval_probe \
  --source data/meb/tarih-9sinif-ders-kitabi_20261006.pdf --index data/derived/history-rag-v1.json \
  --experimental data/private/history-rag-audit-v1/experimental-candidates-v2.json \
  --cases data/private/history-rag-audit-v1/retrieval-probe-cases-v1.json \
  --output data/private/history-rag-audit-v1/retrieval-probe-repeat.json
```

Sonraki geçerli deney için örneklemden bağımsız sorular, her soru için ilgili ve ilgisiz birden çok kanıt etiketi, doğru yanıtsız kalma örnekleri ve iki sistemin öğretmen onaylı kaynaklarla aynı koşullarda karşılaştırılması gerekir. Alıntı devamları, ilişkili atıf ve düzeltilmiş sözcüklerin kaynak doğruluğu ayrıca insan tarafından kontrol edilmelidir.

## Gerçek soru PDF'siyle eşleştirilmiş ilk kanıt incelemesi

`history_rag_paired_review`, soru bankasından otomatik çıkarım ve görsel kontrollerinden geçen, tek ders bölümüyle eşleşen soruları getirme sonuçlarına bakmadan bölüm başına sabit tohumla örnekler. Her iki sistem için aynı soru metni ve aynı BM25 çalıştırılır; ilk üçteki metinler, sistem ve sıra gösterilmeden ortak inceleme havuzuna konur. Sistem-sıra eşleştirmesi ayrı dosyadadır. İnceleme dosyasındaki soru, parça, koordinat ve etiket değişiklikleri doğrulanır; kısmi incelemelerde yalnız ilgili sorusu ve tüm dönen parçaları incelenmiş koşular sayılır.

İlk denemede dört bölümden ikişer olmak üzere 8 soru, iki sürümün oluşturduğu 48 parça gösterimi incelendi. Aynı içerik düzeltme/koordinat varyantları nedeniyle tekrar sunulabilir. Codex her soruyu soru PDF'si ve her kanıtı ders kitabı PDF'siyle karşılaştırdı; `relevant` parçayı soruyu çözmeye yardımcı somut kanıt, `irrelevant` ilgisiz, `uncertain` ise yararlılığı belirsiz olarak işaretledi. Bu etiketler uzman doğrulaması, cevap anahtarı doğrulaması veya modelin doğru yanıt verdiği anlamına gelmez.

Her iki sistemde 8 sorunun 5'inde ilk üçte en az bir ilgili kanıt vardı. Her biri 24 sonuçtan 10 ilgili, 11 ilgisiz ve 3 belirsiz üretti. Bu sayımlar yalnız incelenen ilk üç sonuç içindir; bütün ilgili kaynaklar bilinmediğinden gerçek kaynak recall'u değildir. Sorular dört bölüm ve otomatik seçilebilir soru havuzuyla sınırlıdır. Aynı araştırmacı sistemi geliştirdi ve etiketledi; bağımsız kör uzman değerlendirmesi değildir. Dahası her iki havuzda onaysız adaylar kullanılabilir varsayıldı; bunlar üretimin öğretmen onaylı kaynaklarla elde edeceği sonuçlar değildir.

Dikkat çekici yönlendirme: soru PDF sayfa 37'deki Türklerde yönetme yetkisine ilişkin soru, otomatik sayfa başlığından `Eski Çağ’da Yönetenler ve Savaşanlar` bölümüne eşlendi ve iki sistem de ilgisiz Mısır/Mezopotamya metinleri getirdi. Araştırma amaçlı sonradan `Orta Çağ’daki Siyasi ve Askerî Gelişmeler` seçildiğinde deneysel havuz ilgili Gök Türk alıntısını ilk sırada getirdi. Bu tek örnek, otomatik konu eşleştirmesinin düzeltilmiş olduğunu veya tüm sorularda aynı yaklaşımın çalışacağını göstermez; manuel olarak değiştirilen konu üretim işlemi de değildir.

Örneklem: `data/private/history-rag-audit-v1/paired-sample-v1.json`; etiketler: `paired-codex-reviewed-v1.json`; sistem eşleştirmesi: `paired-mapping-v1.json`; ölçüm: `paired-report-v1.json`. Bunlar özel yerel dosyalardır. Aşağıdaki komut mevcut sonuçlara dokunmadan yeni rapor üretir:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_paired_review score \
  --sample data/private/history-rag-audit-v1/paired-sample-v1.json \
  --mapping data/private/history-rag-audit-v1/paired-mapping-v1.json \
  --reviewed data/private/history-rag-audit-v1/paired-codex-reviewed-v1.json \
  --output data/private/history-rag-audit-v1/paired-report-repeat.json
```

Sonraki deneyde farklı soru sayfalarından daha geniş, önceden ayrılmış ve uzman etiketli bir örneklem; bölüm yönlendirmesinin ayrıca puanlanması; tüm havuzda ilgili kanıtların aranması; onay durumları ve yanıtsız kalma davranışı ele alınmalıdır. Bölüm dışına serbest arama yapılması güvenlik veya doğruluk garantisi değildir ve konu eşleştirme hatalarını otomatik düzeltmek için bu pilot tek başına yeterli değildir.

## Konu yönlendirme, içerik türü ve Türkçe sözcük biçimi deneyleri

`history_rag_routing_experiment` yerel, onaysız adaylarla araştırma yapar. Önceki soru örnekleminin sekiz kimliği dışlanır; soru bankasındaki uygun örneklerden dört bölüm başına iki soru yeni sabit tohumla seçilir. Benzer veya aynı kazanımı ölçen soruların dışlanması garanti edilmediği için bu, tamamen bağımsız bir test değildir. Her üç yöntemde de **aynı deneysel aday havuzu ve tüm havuz üzerinde hesaplanan BM25** kullanıldı. Bu skorlar üretimde bölüm içi BM25 ile hesaplanan skorlardan farklıdır ve adaylar öğretmen onaylıymış varsayılmıştır.

Karşılaştırma: `topic` verilen bölümde sıralar; `quality` rubrik/etkinlik uyarılı adayın skorunu 0,25 ile çarpar; `routing_quality` en yüksek genel skor verilen bölümdeki en iyi skordan 1,25 kat fazla ve başka bölümdeyse bölümü değiştirir, sonra aynı cezayı uygular. Bu eşikler doğrulanmış model parametreleri değil, başlangıç hipotezleridir. Ortak havuzdaki soru ve kaynakları Codex PDF bölgeleriyle karşılaştırarak ilgili, ilgisiz, belirsiz olarak etiketledi. Yanıt anahtarı, tarihsel doğruluk ve uzman onayı ayrıca doğrulanmamıştır.

| Yöntem | İncelenen soru | İlk üçte en az bir ilgili | İlgili / ilgisiz / belirsiz sonuç | Dönen sonuç |
|---|---:|---:|---:|---:|
| Verilen bölüm | 8 | 3 | 4 / 14 / 5 | 23 |
| İçerik cezası | 8 | 3 | 4 / 14 / 5 | 23 |
| Bölüm değiştirme + ceza | 8 | 2 | 2 / 15 / 4 | 21 |

Bölüm üç soruda değişti; birinde önceki ilgili kaynak ilk üçten çıktı. Bu küçük ve Codex etiketli örneklemin sonucu bölüm değiştirme kuralının ürüne alınmasını desteklemez. İçerik cezası ilgili adayların bu örnekteki sıralamasını değiştirmedi. Kısa sorulardan birinde üç yerine iki sonuç döndü; bütün ilgili kanıtlar etiketlenmediği için bunlar gerçek recall veya yanıt doğruluğu değildir. Dosyalar `routing-sample-v1.json`, `routing-codex-reviewed-v1.json`, `routing-mapping-v1.json`, `routing-report-v1.json` adlarıyla yerel özel klasördedir.

Sözcük biçimi için ayrı araştırma: `history_rag_morphology_probe` en az yedi karakterli Türkçe kelimelerden `-lar/-ler` çoğulunu basitçe kaldırır. İlk örnekte `Babiller` sorgusu mevcut tam kelime BM25 ile iki ilgisiz yönerge döndürürken, deneysel normalizasyon aynı bölümde `Babil` içeren bir metni de getirdi. Bu örnek önceki değerlendirmeden sonra seçilmiştir; bağımsız doğrulama değildir. Kural Türkçe kök çözümleyici değildir, tesadüfen bu eklerle biten sözcükleri bozabilir ve yanlış eşleşme üretebilir. Onay veya konu sınırını aşmaz; üretimde kullanılmaz. Seçenekleri sorguya topluca ekleme denemesinde de çeldiricilere ait metinlerin öne gelebildiği görüldü; seçeneklerdeki iddialar kanıt kabul edilmemelidir.

Raporu yeniden hesaplama:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_routing_experiment score \
 --sample data/private/history-rag-audit-v1/routing-sample-v1.json \
 --mapping data/private/history-rag-audit-v1/routing-mapping-v1.json \
 --reviewed data/private/history-rag-audit-v1/routing-codex-reviewed-v1.json \
 --output data/private/history-rag-audit-v1/routing-report-repeat.json
```

İlerleme için uygun adım: dilsel normalizasyonu ayrı bir gelişim kümesinde ve önceden ayrılmış uzman etiketli sorularda karşılaştırmak; konu hatalarını tek skorla bölümü değiştirmek yerine aday bölüm önerisi ve belirsizlik olarak ölçmek; doğru ve yanlış seçeneklerden kaynaklanan sorgu sapmalarını ayrı test etmek. Hiçbir deney otomatik üretim kararı vermez.

## Türkçe çoğul normalleştirme: yeni soru örneklemi

`history_rag_morphology_review` mevcut bölüm içi BM25 ile Türkçe `-lar/-ler` için basit normalleştirmeyi aynı deneysel aday havuzunda karşılaştırır. Üçüncü kol normalleştirilmiş skorlara rubrik/etkinlik cezası ekler. Önceki iki soru örneklemindeki 16 soru kimliği dışlanarak dört bölümden ikişer yeni soru sabit tohumla seçildi. Kimlik dışlama benzer soruları veya aynı bilgiye ilişkin soruları dışlamaz; örneklem bağımsız uzman testi değildir. Sorular sonuçlar gösterilmeden seçildi, kanıtlar ortak havuzda sistem adı ve sıra gösterilmeden Codex tarafından PDF bölgeleriyle karşılaştırıldı. Gösterim sırası gizli olsa da aynı araştırmacının kuralları geliştirmesi incelemeyi bağımsız uzman değerlendirmesi yapmaz. Etiketler yalnız getirilen kanıtlara ilişkindir ve öğretmen onayı veya yanıt anahtarı kontrolü değildir.

| Yöntem | İncelenen soru | İlk üçte en az bir ilgili | İlgili / ilgisiz / belirsiz | Sonuç |
|---|---:|---:|---:|---:|
| Tam kelime BM25 | 8 | 4 | 6 / 12 / 6 | 24 |
| Çoğul normalleştirme | 8 | 4 | 6 / 10 / 8 | 24 |
| Normalleştirme + içerik cezası | 8 | 4 | 6 / 10 / 8 | 24 |

Bu örnekte ilgili kanıt bulunan soru sayısı değişmedi. İki sonuç ilgisizden belirsiz olarak değerlendirilen başka metinlere değişti; bu tek başına kalite iyileşmesi değildir. Yalnız 28 farklı gösterimlik havuz incelendi; başka ilgili kanıtlar bulunabilir ve değerlendirme korpus recall'u değildir. Tüm adaylar onaylı gibi kullanıldığından canlı sistemin ölçümü değildir. Kelimenin sonundaki harfleri silmek gerçek Türkçe kök çözümlemesi değildir; hatalı birleştirme riskini ve canlı sistemin mevcut onay kapısını göz önüne alarak bu yöntem üretime eklenmedi.

Dosyalar: `data/private/history-rag-audit-v1/morphology-sample-v1.json`, `morphology-codex-reviewed-v1.json`, `morphology-mapping-v1.json`, `morphology-report-v1.json`. Eşleştirme dosyasındaki iç isimler mevcut puanlama doğrulayıcısıyla uyumludur: `topic` tam kelime, `quality` çoğul normalleştirme, `routing_quality` normalleştirme ve içerik cezası anlamına gelir; bu deneyde yönlendirme değişmez.

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_morphology_review score \
 --sample data/private/history-rag-audit-v1/morphology-sample-v1.json \
 --mapping data/private/history-rag-audit-v1/morphology-mapping-v1.json \
 --reviewed data/private/history-rag-audit-v1/morphology-codex-reviewed-v1.json \
 --output data/private/history-rag-audit-v1/morphology-report-repeat.json
```

Bir sonraki değerlendirme, yakın kopya soruları ve kaynak sayfalarını kümelere ayırmalı; ilgili/ilgisiz kanıtlarla birlikte doğru yanıtlanamama durumlarını uzman tarafından değerlendirmeli ve hem sözcüksel hem anlamsal getirme yöntemlerini aynı kapalı testte karşılaştırmalıdır.

## Sayfa bazında değerlendirme bölmesi

`history_rag_question_splits`, soru PDF'sindeki otomatik olarak uygun ve bir ders bölümüyle eşleşen 130 adayın her birini soru PDF checksum'ı, fiziksel sayfa numarası ve sabit tohum üzerinden eğitim/geliştirme/test bölmesine atar. Aynı sayfadaki bütün sorular aynı bölmededir. Bu, sayfa içi veri sızıntısını azaltır; farklı sayfalardaki aynı kazanım veya yakın kopyaları ve ortak ders kitabı kaynaklarını ayırmaz. İçerik otomatik çıkarılmıştır ve uzman incelemesi yapılmamıştır.

Bu başlangıç atamasında 76 eğitim, 30 geliştirme ve 24 test sorusu vardır. Önceki üç karşılaştırma örnekleminde görülen soru kimlikleri ve sayfaları ayrıca işaretlendi; bu üç örneklemdeki sayfalara denk gelmeyenler 24/18/9'dur. Bunların daha eski çalışmalarda görülmediği doğrulanmamıştır; bağımsız kapalı test oldukları iddia edilemez. Ayrıca mevcut atamada 2.5 bölümünde hiç test sorusu yoktur; bütün bölümleri kapsayan bir karşılaştırma için daha iyi bir plan ve yeni soru kaynakları gerekir. Dosya `data/private/history-rag-audit-v1/question-splits-v2.json`; bu bir eğitim veri kümesi veya uzman etiketli test değildir.

## Soru benzerliği ve sızıntı kontrolü

`history_rag_question_clusters` aynı sayfadaki soruları ve yüksek kelime/dört karakterli parça benzerliği bulunan farklı sayfalardaki soruları aynı grupta toplar. İlk sıkı eşikler (kelime Jaccard ≥ 0,60 ve karakter dörtlüsü Jaccard ≥ 0,70) bölmeler arasında hiçbir yüksek benzerlik çifti göstermedi; bu, tekrarların olmadığı anlamına gelmez. Daha düşük, yalnız inceleme amacıyla kullanılan eşikler (≥ 0,28 ve ≥ 0,30) bölmeler arasında 10 aday çift üretti. Bu eşikler ampiriktir; anlamsal deduplikasyon değildir.

Codex çıkarılmış soru metinlerini inceledi: 3 çift aynı bilgi metnini paylaşıyor, 6 çift farklı bilgi içeren benzer bir soru şablonu, 1 çift belirsiz olarak işaretlendi. Bu aşamada soru görselleriyle bağımsız uzman kontrolü yapılmadı. `history_rag_cluster_review`, aynı bilgi metni ve belirsiz çiftleri birleştirerek aynı kümede tutar; gruptaki bir soru önceki üç pilotta görülmüş bir sayfadaysa grup da işaretlenir. Önceki üç pilot dışındaki geçmiş incelemeler, farklı biçimlerdeki paraphrase ve aynı ders kaynağının kullanımı takip edilmiş değildir.

Son geçici dağılım 92 eğitim, 14 geliştirme, 24 testtir. 2.3 bölümünde geliştirme ve 2.5 bölümünde test sorusu yoktur; bu yüzden bölümler arası dengeli bir karşılaştırma için uygun değildir. İlgili kaynakları genişletmek, konu ve anlam bazlı grupları uzmanla kontrol etmek ve bölmeleri sonuçları optimize etmeden önceden sabitlemek gerekir. Özel veriler: `question-clusters-v2.json`, `question-cluster-codex-review-v1.json`, `question-clusters-reviewed-v1.json`.

## BGE-M3 Kaggle sentetik işlev kontrolü

`experiments/kaggle/history_rag_dense_synthetic_probe.py` BGE-M3 modelini sabit `5617a9f61b028005a4858fdac845db406aefb181` revision ile özel Kaggle GPU oturumunda yükleyip tamamen uydurma beş Türkçe soru ve beş metinde BM25, yoğun vektör ve RRF akışlarını dener. Kullanıcı verisi, MEB metni, soru bankası veya etiketler Kaggle'a yüklenmez. Deneme model yükleme, GPU kullanımı ve hesaplama mekanizması içindir; sonucu Türkçe eğitim kalitesi, gerçek RAG doğruluğu veya gecikme yüzdelikleri olarak kullanılmaz. [BGE-M3 model kartı](https://huggingface.co/BAAI/bge-m3) yoğun vektörün yanı sıra başka getirme kipleri de tanımlar; bu smoke testi bunların tümünü test etmez.

`history_rag_dense_compare` yerel olarak önceden üretilmiş sayısal vektörlerle BM25, cosine yoğun sıralama ve RRF'yi aynı konu filtresi ve açıkça verilen onaylı parça kümesi üzerinde karşılaştırır. Eksik, hatalı veya sıfır normlu vektörlerde hata verir; kaynağı onaylamaz ve model indirmez. Yoğun arama, ilgili bir kaynak bulunmasa bile en yakın komşuyu döndürebilir; ayrı bir kanıt yeterliliği/yanıtsız kalma değerlendirmesi olmadan bu sıralamalar güvenli yanıt oluşturma kararı değildir. Bu karşılaştırma aracı henüz gerçek embedding veya uzman etiketli sınama sonucuyla doğrulanmamıştır.

Kaggle sonucu: private `history-rag-bge-smoke-v1` koşusu tamamlandı. Ortam iki Tesla T4 gördü; model tek `cuda` aygıtında yüklendi. 1024 boyutlu vektörler üretildi; yükleme tepe bellek 2,115 GiB, sentetik getirme sırasında 2,130 GiB. Beş metnin toplu vektörlemesi 1,436 sn, beş sorgunun toplu vektörlemesi 0,047 sn sürdü; bunlar çok küçük ve sıcaklık koşulları ayrılmamış ölçümlerdir, üretim gecikmesi olarak kullanılamaz. Elle hazırlanmış beş sentetik vakada ilk üçte hedef sayıları BM25 4/5, yoğun 5/5, RRF 5/5 idi. Bunlar deneyci yapımı kurgu metinlerin mekanik sonuçlarıdır; gerçek soru ve kanıtlarla model seçimini doğrulamaz. Ham rapor `data/private/history-rag-bge-smoke-v1/history_rag_dense_probe.json`.

## Gerçek kaynaklarla küçük geliştirme pilotu

Kaggle özel veri kümesine (`muhammedcanozyasar/history-rag-sealed-pilot-v1`, sürüm 2) dört gerçek soru kökü ve 101 araştırma adayı yüklendi; cevap anahtarı ve uygunluk etiketleri yüklenmedi. Özel oturum `history-rag-sealed-eval-v2`, 2.1, 2.2, 2.3 ve 2.5 bölümlerinde BM25, BGE-M3 yoğun vektör ve RRF'yi aynı bölüm filtresi ve adaylarla karşılaştırdı. Model `BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181`, 512 token sınırı, `sentence-transformers` 3.4.1 ve tek Tesla T4 kullanıldı. Girdilerde kesilme raporlanmadı. Tepe GPU belleği 2,265 GiB; 101 metnin toplu vektörlemesi 3,021 sn, dört sorgununkisi 0,132 sn sürdü. Bunlar küçük toplu iş ölçümleridir; kullanıcı gecikmesi veya üretim kapasitesi değildir.

Dört sorunun üç yöntemde ilk üç sıraya giren toplam 21 farklı aday gösterimi Codex tarafından soru ve ders kitabındaki PDF bölgeleriyle karşılaştırıldı. `relevant`, sorudaki en az bir çıkarıma somut destek; `uncertain`, kısmi veya yetersiz ayırt edici destek; `irrelevant`, çözüm için somut destek bulunmaması anlamına gelir. Destek bir sorunun tamamen yanıtlanabildiği anlamına gelmez. Kaynak görseli kontrolü tarihsel doğruluğun bağımsız doğrulaması veya öğretmen onayı değildir. Aynı araştırmacı sistemi geliştirip değerlendirdi ve sıralama çıktısına erişti; etiketler bağımsız veya kör uzman değerlendirmesi değildir.

| Getirme yöntemi | Soru | İlk üçte en az bir ilgili parça bulunan soru | İlgili / ilgisiz / belirsiz gösterim | Toplam gösterim |
|---|---:|---:|---:|---:|
| BM25 | 4 | 2 | 2 / 8 / 2 | 12 |
| BGE-M3 yoğun | 4 | 2 | 5 / 6 / 1 | 12 |
| BM25 + yoğun RRF | 4 | 2 | 4 / 6 / 2 | 12 |

BGE-M3 bu çok küçük havuzda daha çok ilgili gösterim buldu, fakat ilgili sonuç bulunan soru sayısı artmadı. Sonuçlar sadece getirilen havuz için geçerlidir; korpus recall'u, doğru cevap oranı veya model üstünlüğü olarak yorumlanamaz. Özellikle yönetim biçimi sorusunda aynı konudan söz eden metinler tanımı vermiyor; benzer veya yinelenen parça da görülebiliyor. Konu bilgisi kanıt yeterliliği yerine geçmez.

Bu çalışma dosya ve kod adlarında `sealed` geçse de **bağımsız, kapalı test değildir**: soru grupları yalnız önceki üç pilotun sayfalarına göre işaretlendi; 2.5 sorusunun sayfası daha önce görülmüştü ve 2.2 sorusu da önceki başka bir incelemede gösterilmişti. Yakın kopya kontrolü tam değildir. İncelenmiş soru kümeleri kitabın 13 bölümünden yalnız dördünü kapsıyor; 2.5 için tamamen yeni grup bulunmadı. Adayların hiçbiri bu çalışmayla öğretmen tarafından onaylanmadı. Veritabanında öğretmen onaylı 16 parçanın tamamı 2.1 bölümündeydi; burada araştırma için kullanılan diğer adaylar canlı sistemin izinli korpusunu temsil etmez. Üretim davranışı değiştirilmedi ve fine-tuning yapılmadı.

Özel yerel dosyalar: `data/private/history-rag-sealed-pilot-v1/input.json` (SHA-256 `b43bd8c386915aad60c5842d4e77200eb073666ca84229d6ff32d0585527d5b5`), `data/private/history-rag-sealed-result-v2/history_rag_sealed_rankings.json`, `review-sample.json`, `review-mapping.json`, `review-codex-v1.json` ve `review-report-v1.json`. Sonuç doğrulayıcı kaynak checksum'larını, bölüm filtresini ve uzak BM25 sıralamasının yerel hesapla eşitliğini kontrol eder. Puanlama yeniden çalıştırılabilir:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_sealed_review score \
 --sample data/private/history-rag-sealed-result-v2/review-sample.json \
 --mapping data/private/history-rag-sealed-result-v2/review-mapping.json \
 --reviewed data/private/history-rag-sealed-result-v2/review-codex-v1.json \
 --output data/private/history-rag-sealed-result-v2/review-report-repeat.json
```

İlerleme ölçütü: yeni, geçmişte görülmemiş ve daha geniş bölüm kapsamlı sorular ile kaynak parçaları hazırlamak; soru gruplarını ve yanıtsız kalma örneklerini önceden ayırmak; bağımsız uzmanların kanıt yeterliliği ve cevapları etiketlemesini sağlamak. Bölüm kapsaması, yinelenen parçalar, yetersiz kanıtta yanıt vermeme ve uçtan uca doğruluk ayrıca ölçülmeden üretime taşıma veya CV'de performans iddiası yapılmamalı.

## Kaynak yeterliliği ve daha sıkı aday ayrımı

`history_rag_independent_eval freeze`, mevcut yerel pilot ve inceleme JSON'larındaki soru sayfalarını, önceki benzerlik incelemesinde gösterilmiş soru çiftlerini ve Kaggle pilotundaki soruları dışlar; bir grubun herhangi bir sayfası görünmüşse grubun tamamını dışarıda tutar. Sabit tohumla grup bazında geliştirme ve test adaylarını ayırır. Önceki kayıtların tamamını ve anlamsal paraphrase'leri kapsadığı garanti edilmediğinden bu küme kesinlikle bağımsız kabul edilmez; dosya adı bu garantiyi ifade etmez. 23 görülmüş sayfa ve 40 soru kimliği saptanmıştır. Kalan 14 adayın tamamı 2.2 bölümündedir: 8 geliştirme, 6 test; diğer 12 bölümde aday yoktur. Test grubu inceleme sayfasına veya geliştirme paketine konmamıştır. Test soruları ve yanıtları henüz kaynak/uzman kontrolünden geçmemiştir.

`answerability-development-v1.json`, geliştirme bölümündeki sekiz sorunun her birine, yalnız araştırma için kullanılan onaysız adaylardan BM25 ile getirilen en fazla üç parçayı ekler; her sorunun bir de hiç kanıt gösterilmeyen kontrolü vardır. Toplam 16 vaka, aynı 8 sorunun iki sürümüdür; bağımsız 16 soru değildir. Boş kontrol örnekleri yapaydır ve doğal ortamda yetersiz kanıt görülme sıklığını veya model güvenliğini tahmin etmek için kullanılamaz. Daha zor, konuya benzeyen fakat yetersiz kanıt örnekleri ayrıca uzmanla hazırlanmalıdır.

Özel yerel `answerability-development-review-v1.html` sayfası her soru ve kanıt için PDF bağlantıları, yeterli/yetersiz/belirsiz seçimi ve kaynak kontrolü sunar. Çıktısı hiçbir parçayı üretimde onaylamaz. Yeterli etiketi yalnız verilen kanıtlarla tek doğru seçeneğe güvenle ulaşılabiliyorsa kullanılmalı; yalnız aynı konuda olması yeterli değildir. Kod inceleyen kimliğinin gerçek bir uzman olduğunu doğrulayamaz. Aynı araştırmacının kendi etiketleri bağımsız uzman etiketleri sayılmaz.

`history_rag_independent_eval score` sabit paket checksum'ı ile vaka kimliklerini doğrular; bütün vakalarda kaynak kontrolü ve inceleyen kodu ister. Yeterli/yetersiz/belirsiz ile cevap/çekimser durumlarının sayılarını ayrı raporlar. Doğru seçenek yalnız yeterli diye etiketlenmiş ve yanıtlanmış örneklerde değerlendirilir; bu, gerekçenin kaynağa dayandığını veya uçtan uca öğrenci başarısını kanıtlamaz. Boş etiket şablonları veya sentetik testler gerçek öğretmen değerlendirmesi sayılmaz. Bu aşamada gerçek uzman etiketi ve modele ait cevap/çekimser çıktıları olmadığı için herhangi bir başarı oranı hesaplanmamıştır.

Dosyalar `data/private/history-rag-audit-v1/independent-candidates-v1.json`, `answerability-development-v1.json` ve `answerability-development-review-v1.html` içindedir. Etiketler ve tahminler mevcut olduğunda puanlama:

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -m app.pipeline.history_rag_independent_eval score \
 --bundle data/private/history-rag-audit-v1/answerability-development-v1.json \
 --labels /path/to/teacher-reviewed.json --predictions /path/to/model-predictions.json \
 --output data/private/history-rag-audit-v1/answerability-development-report.json
```

Diğer bölümler için kullanma izni olan yeni soru kaynakları, geniş kapsamlı doğrulanmış kanıtlar ve bağımsız öğretmen incelemesi gerekir. Model karşılaştırmasında sadece cevap doğruluğu değil, yetersiz kanıtta yanlışlıkla cevap verme, yeterli kanıtta gereksiz çekimserlik ve belirsiz değerlendirmeler de ayrı gösterilmelidir.

### Geliştirme vakalarının Codex ön incelemesi

Sekiz geliştirme sorusunun PDF bölgesi ve getirilen üçer kaynak parçasının bütün kaynak segmentleri, PDF sayfalarıyla karşılaştırıldı. Dış kaynağın tek bir seçeneği desteklemesi ölçütüyle iki getirilmiş kanıt kümesi yeterli, dördü yetersiz ve ikisi belirsiz olarak ön etiketlendi. Sekiz boş kaynak kontrolü, dış kaynak zorunluluğu bulunan bu deney protokolünde yetersizdir. Bazı soru köklerinin kendisi çok bilgi taşır; kökten çözülebilirlik, dış kaynakla doğrulanabilirlikten ayrılmalıdır. Soru metni dış kaynak kanıtı olarak kabul edildiğinde bazı etiketler değişebilir. Özellikle iki sınır durumunun belirsiz bırakılması bu nedenle önemlidir.

Etiketler `answerability-development-codex-v1.json` dosyasındadır; PDF görsel kontrolü içerir ancak bağımsız öğretmen/alan uzmanı değerlendirmesi veya yayınevi cevap anahtarı doğrulaması değildir. Kaynak doğrulaması, kaynakta yazanın tarihsel olarak doğru olduğunun bağımsız doğrulaması anlamına gelmez. RAG adayları üretimde onaylanmamıştır. Bu etiketler test kümesi değildir ve üretim performansı için kullanılmamalıdır.

### Qwen3-14B çekimserlik geliştirme deneyi

Özel Kaggle veri kümesi `muhammedcanozyasar/history-rag-answerability-input-v1` yalnız geliştirme soru ve gösterilecek kaynaklarını içerir; Codex etiketleri yüklenmemiştir. `experiments/kaggle/history_rag_answerability_qwen14b.py`, özel `history-answerability-qwen14b-v1` notebook'unda `Qwen/Qwen3-14B` revision `40c069824f4251a91eefaf281ebe4c544efd3e18`, 4-bit NF4, tek Tesla T4 ve deterministik üretim ile çalıştı. Modele dış kaynak yeterli değilse çekimser kalması söylendi; yalnız eylem ve seçenek şeklinde çıktı istendi. İnceleme paketi checksum'ı, 16 vaka kimliği ve geçerli çıktı biçimi doğrulandı. Dört bitlik bu taban model fine-tune edilmemiştir.

Codex ön etiketlerine göre sonuçlar:

| Gösterilen kaynak | Ön etiket | Cevap | Çekimser |
|---|---|---:|---:|
| Getirilen kaynak | Yeterli | 2 | 0 |
| Getirilen kaynak | Yetersiz | 3 | 1 |
| Getirilen kaynak | Belirsiz | 2 | 0 |
| Yapay boş kontrol | Yetersiz | 2 | 6 |

İki yeterli vakada modelin seçeneği Codex ön etiketiyle eşleşti. Bununla birlikte cevap anahtarı bağımsız doğrulanmamış, gerekçe ve kaynak atıfları üretilip değerlendirilmemiştir; sonuçlar destekli açıklama doğruluğu değildir. İki belirsiz vaka doğru/yanlış hesabına katılmaz. Aynı sekiz sorunun iki varyantından oluşan küçük, tek bölümlük bir geliştirme deneyi ve yapay boş kontroller, bağımsız test veya üretim performansı değildir. Üç getirilmiş yetersiz kaynakta ve iki boş kaynakta cevap verilmesi, bu protokol altında talimatın yeterli çekimserlik sağlamadığını gösterir; gerçek kullanıcı hatası oranı tahmin edilemez. Modelin kendi bilgisini kullandığı veya hangi kaynaktan yararlandığı sadece cevap biçiminden kanıtlanamaz.

Ham kimlik ve eylem tahminleri `data/private/history-answerability-qwen14b-v1-output/history_rag_answerability_predictions.json`, eşleşen ön etiketler `data/private/history-rag-audit-v1/answerability-development-codex-v1.json`, doğrulanmış skor `answerability-development-qwen14b-report-v1.json` içindedir. Sekiz sorunun da kaynak PDF'leri gözle kontrol edildi; başka uzman/öğretmen incelemesi yapılmadı. Deney çıktısı üretim ayarlarını veya kaynak onaylarını değiştirmez.

### Ayrı kaynak kapısı, alıntı ve açıklama deneyi

Aynı geliştirme paketi ve aynı `Qwen/Qwen3-14B` 4-bit model ile önce kaynak yeterliliği, ardından geçildiğinde kaynak numarası, birebir alıntı ve açıklama üreten iki aşamalı bir deney gerçekleştirildi. Boş kaynakta model çağrılmadan çekimser kalındı. Yerel `history_rag_grounded_gate` doğrulayıcısı kaynak numarasının gösterilen aralıkta olmasını, en az 12 karakterlik alıntının boşluk normalizasyonu dışında kaynak metninde birebir geçmesini, iki aşamanın seçeneğinin eşleşmesini ve açıklamanın bulunmasını kontrol eder. Hata olduğunda çekimser kalır. Bu kurallar **alıntının iddiayı desteklediğini doğrulamaz**.

Codex ön etiketli aynı sekiz gerçek kaynak vakasında: yeterli iki vakadan birinde cevap, birinde çekimserlik; yetersiz dört vakadan ikisinde cevap, ikisinde çekimserlik; belirsiz iki vakada çekimserlik görüldü. Sekiz yapay boş kaynak kontrolünün hepsinde kod çekimser kaldı. İlk aşama, gerçek kaynaklı sekiz vakanın hepsinde model olarak yeterli kararı verdi; sonraki biçim kontrolü ve seçenek uyuşmazlığı bazılarını engelledi. Bu nedenle kaynak kapısının kendisi güvenilir bir anlamsal yeterlilik denetimi olduğunu göstermedi.

Birebir alıntı kontrolünü geçen üç cevap Codex tarafından incelendi: birinde etkinlik yönergesi tarihsel iddiaya kanıt gösterildi; birinde seçenek ile açıklama birbirine karşılık gelmedi; üçüncüde kaynak doğru seçeneğe kısmen destek verse de açıklamada kaynak metninde bulunmayan iddialar yer aldı. `grounded-gate-semantic-codex-v1.json` bu ön incelemeyi kaydeder; bağımsız uzman değerlendirmesi değildir. Başka bir yeterli vakada PDF metin çıkarımındaki satır sonu/heceleme ile modelin düzelttiği alıntı uyuşmadığından sistem çekimser kaldı: sıkı doğrulama güvenliği artırırken yararlı cevabı da engelleyebilir. Kaynağın doğruluğu ve açıklamanın bütün iddiaları ayrı değerlendirilmelidir.

Yapısal kapının sonuçları `grounded-gate-development-predictions-v1.json` ve `grounded-gate-development-report-v1.json`, Kaggle ham çıktısı `data/private/history-grounded-gate-qwen-v1-output/history_rag_grounded_gate_raw.json` dosyalarındadır. Bunlar küçük, aynı araştırmacı tarafından önceden etiketlenmiş geliştirme vakalarıdır; bağımsız test veya üretim güvenliği kanıtı değildir. Canlı uygulamaya bağlanmamıştır.

### Ayrı anlamsal model denetçisi

Yapısal kontrolden geçen üç yanıt, yalnız kendi soru metni, seçeneği, açıklaması, atfı ve atıf yapılan kaynak ile `history-semantic-judge-qwen-v1` özel Kaggle koşusunda aynı Qwen3-14B modeline üç ayrı kontrol için verildi: açıklama-seçenek tutarlılığı, kaynağın cevabı desteklemesi ve açıklamadaki iddiaların kaynak desteği. Kod, üç kontrolün tamamı `yes` olmadığında veya sonuç şeması bozuk olduğunda çekimser kalır. Kaynak metinleri ve cevaplar özel `history-rag-semantic-judge-input-v1` veri kümesinde tutuldu; ön değerlendirme etiketleri yüklenmedi. Aynı modelin kendi çıktısını denetlemesi bağımsız denetçi veya uzman doğrulaması değildir.

Model üç cevabın tamamını en az bir kontrolde `no` veya `uncertain` olarak işaretledi: ilgisiz etkinlik yönergesi kaynak desteği sağlamadı, Lidya açıklamasında kaynak dışı ayrıntılar belirsiz kaldı, Roma açıklaması/Yunan seçeneği uyuşmazlığı saptandı. Anlamsal aşama sonrası 16 durumun tamamında çekimserlik oluştu: dört yetersiz getirilmiş kaynak, sekiz yapay boş kontrol, iki belirsiz vaka ve iki yeterli vaka. Yetersiz durumlarda yanlış cevap verilmemesi, yeterli iki sorunun da cevapsız kalması pahasına gerçekleşti. Bu yalnız aynı örnekler üzerinde geliştirilmiş çok küçük deneydir; üretimde güvenilirlik, doğru cevap veya kapsama oranı olarak kullanılamaz. Otomatik denetçi bu örnekte olumlu gözükse bile farklı ifadelerde başarısız olabilir ve bağımsız değerlendirilmemiştir.

Ham yargılar `data/private/history-semantic-judge-qwen-v1-output/history_rag_semantic_judge_raw.json`, yerel kapı çıktısı `data/private/history-rag-audit-v1/semantic-gate-development-predictions-v1.json`, skor `semantic-gate-development-report-v1.json` içindedir. Sonraki deney, alıntı çıkarımında PDF satır bölünmesi hatalarını kaynakla izlenebilir biçimde düzeltmeli; doğru cevapların kanıtlanmasını ve yanlış iddiaların engellenmesini ayrı ölçmelidir. Soru kökündeki verilen bilgilerin ne ölçüde kabul edildiği de sabit rubrikle belirlenmelidir. Uygulamaya aktarma öncesi yeni ve bağımsız uzman etiketli geliştirme/test örnekleri gereklidir.
