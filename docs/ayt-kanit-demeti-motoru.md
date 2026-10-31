# AYT kanıt demeti motoru

## Amaç

Bir soru ile aynı sözcükleri taşıyan paragraf, o sorunun çözüm kanıtı değildir. Tarih sorusu; temel olguya ek olarak kişi–olay, tarih–olay, yer–olay, kronoloji, neden–sonuç ya da şıkta karışan kapsam bilgisini ayrı bir yerde gerektirebilir.

Bu motor, tek sorgu için sabit sayıda sonuç kesmek yerine önce **kanıt planı** kullanır. Planın her zorunlu iddiası ayrı aranır; bir iddia için uygun aday bulunamazsa sonuç `insufficient_evidence` olur. Bu durumda model tahminle tamamlamaz.

## Private kanıt planı

Plan yalnız `data/private` içinde tutulur. Agent tarafından taslak olarak yazılabilir, fakat kaynak onayı değildir. Her soru için şu alanlar tutulur:

- `topic_labels`: soru ve ders kitabı başlıklarını bağlayan konu etiketleri
- `evidence_claims`: temel olgu, ilişki, bağlam veya karıştırılan bilgiyi ayırma amacı taşıyan kanıt iddiaları
- `claim_type`: `fact`, `definition`, `person_event`, `date_event`, `place_event`, `chronology`, `cause_effect` veya `scope`
- `entities` ve `relation_type`: ilişki uçları ile ilişki türü
- `option_discriminators`: şıklardan hangisini ayırt eden tarih, kişi, yer, sıra, neden veya kapsam bilgisi
- `support_requirements`: mutlaka kaynakla desteklenmesi gereken iddia ve ayırıcılar
- `evidence_policy`: öğrenciye verilecek demetin sınırı
- `abstain_gate`: kanıt, erişilebilirlik veya kaynak sürümü yetersiz olduğunda dönüş biçimi

Plan cevap anahtarı, doğru şık veya öğrencinin kişisel verisini taşımaz.

## Getirme ve demet kurma

1. Her zorunlu iddia `all_of` ve gerekiyorsa `any_of` ile ayrı sorgulanır. Tüm zorunlu terimleri taşımayan parça, genel soru sözcüklerini tekrar etse de aday olamaz.
2. Bölüm başlığı eşleşmesi ve soru terimi örtüşmesi yalnız aynı iddia adaylarını sıralayan açıklanabilir bağ kırıcı sinyallerdir.
3. Aynı PDF sayfasındaki yakın kopyalar azaltılır. Her iddianın inceleme kuyruğuna çeşitli sayfalardan alternatifler girer.
4. Bir parça birden fazla iddiayı kapsıyorsa tek kartta bütün `claim_ids` saklanır. Böylece ilişki grafiğinde varsayım yerine açık kanıt kapsamı görülür.
5. İnceleme kuyruğu için sabit üç kart sınırı yoktur. Varsayılan öğrenci demeti `primary + relation/context + isteğe bağlı contrast` ile en fazla üç karttır; gerçekten bağımsız üçüncü ilişki gerektiği insan incelemesiyle gösterilirse dört karta çıkar. QLoRA dışa aktarımında yine yalnız iki kısa alıntı kullanılır: önce `primary + relation`, ilişki yoksa `primary + context`.

`contrast` ilk ipucuna veya QLoRA bağlamına girmez. Öğrenci kendi tercihini gösterdikten sonraki şık eleme aşamasında kullanılabilir.

## Kaynak ve insan denetimi

Agent kararı öğrenciye yayın yapmaz. Her kartta PDF checksum'ı, sayfa, koordinat, birebir alıntı, kaynak türü, kalite uyarıları, inceleyen ve PDF kırpımı kontrolü bulunur.

- `primary`: Kökün çözümü için gerekli olguyu/ilişkiyi kesit kendi başına açıkça söyler.
- `relation`: İlişkinin iki ucunu birlikte kanıtlar.
- `context`: Hatırlamayı başlatan çerçevedir; primary yerine geçmez.
- `contrast`: Öğrencinin karıştırdığı bilgiyi kaynakla ayırır; yanlış bilgiyi desteklemez.

Kart düzeyinde `irrelevant`, `unsafe` ve `duplicate` kararları; soru düzeyinde `reretrieve`, `insufficient` ve `blocked` kararları ayrı tutulur. `context` kartı, eksik primary kanıtını telafi edemez.

## Ölçüm

BM25, dense, RRF ve reranker deneylerinden önce PDF kırpımıyla onaylanmış altın kanıt gerekir. Klasik `Recall@1/@3`, `MRR@3`, `nDCG@3`, top-1 yanlış kanıt oranı ve gecikmeye ek olarak şunlar raporlanır:

- `primary_coverage@k`
- ilişki ve contrast kapsamı
- rol macro-F1
- zorunlu çekimser kalma doğruluğu
- checksum, sayfa, koordinat ve kırpım eşleşmesi (%100 beklenir)

Bu metrikler, kaynak bulmayı modelin güzel yanıt üretmesinden ayrı ölçer. Bir retrieval yöntemi geliştirme kümesinde kabul kapılarını geçmeden öğrenci çalışma akışına eklenmez.

## Agent taslağını güvenli biçimde iyileştirme

Agent denetimi, kaynak rolü ya da onayı vermez. Bir yanlış negatif denetiminden sonra `ayt_evidence_plan_patch` yalnız arama eş anlamlarını, bölüm ipuçlarını, iddia bölme/birleştirme kurallarını ve hedefli sorgu stratejisini uygular. Yama:

- cevap anahtarı erişimi veya öğretmen onayı taşıyamaz,
- bilinmeyen soru/iddia kimliğine bağlanamaz,
- PDF kırpımı, checksum ve primary zorunluluğunu kaldıramaz.

İki sürüm aynı corpus ve soru checksum'ına bağlıyken `ayt_evidence_bundle_eval compare` şu tanısal farkı üretir: zorunlu iddia kapsamı, eksik iddia sayısı, sıkı aday sayısı ve yanlışlıkla onaylanmış kaynak sayısı. Son değer daima sıfır olmalıdır; bu araç kaynak onayı üretmez.

İlk 9 soruluk private pilotta yama, eksik zorunlu iddia sayısını 23'ten 17'ye indirdi ve bir sıkı inceleme adayı oluşturdu. Bu doğruluk, retrieval kabulü veya model başarısı değildir. Bağımsız tarih agentı bu adayın Hicaz–Medine ilişkisi için yalnız PDF kırpım inceleme önceliği taşıdığını; alias ve iki kesitli ilişki nedeniyle öğrenci RAG'ı, altın etiket ve QLoRA dışında kalması gerektiğini raporladı.
