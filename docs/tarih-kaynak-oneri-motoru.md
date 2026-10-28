# Tarih Kaynak Öneri Motoru

Bu motor öğrenciye kaynak seçmez ve otomatik onay vermez. Amaç, öğretmenin PDF
üzerinde inceleyeceği kısa MEB kanıtlarını önceliklendirmektir.

## Puanlama

Her ham PDF parçası aşağıdaki açıklanabilir sinyallerle değerlendirilir:

- soru kökü ve şıklarda BM25 ilişkisi
- nadir ve ayırt edici kişi, yer, dönem ya da eser terimlerinin kapsanması
- soru kökü ile şıkların ayrı kapsama oranı
- test sayfasındaki konu başlığı ile MEB bölüm başlığı uyumu
- PDF'de bölünmüş sözcük, görsel açıklaması veya etkinlik yönergesi riski
- seçilmiş kanıtlarla aşırı metin benzerliği

Son seçki, aynı paragrafın yakın kopyalarını azaltan MMR benzeri çeşitlilik
kuralı kullanır. Her adayın puan bileşenleri ve gerekçeleri öğretmen ekranına
döner. review yalnız inceleme önerisidir; do_not_use_yet kaynak kalitesi
veya görsel/yönerge riski nedeniyle öğrenci RAG'ına ve Kaggle verisine kapalıdır.

## Doğrulama

Motor ayrı bir sentetik testte doğrudan kanıtı genel konu paragrafının üzerine
taşır ve görsel açıklamasını kullanılmamalı olarak işaretler. Gerçek kalite,
öğretmen tarafından oluşturulan kapalı kanıt kümesinde Recall@k, MRR@k, kanıt
kapsamı ve yanlış kanıt oranıyla ölçülür. RAG değerlendirmesinde bağlam
ilgisi, doğruluk ve kaynak kalitesi birlikte ele alınmalıdır; bu nedenle
sıralama puanı tek başına kabul ölçütü değildir. [RAG değerlendirme
derlemesi](https://link.springer.com/article/10.1007/s42979-026-05134-x)
ve [kamusal RAG değerlendirme rehberi](https://playbooks.aip.gov.sg/rag-playbook/evaluation/)
bu ayrımı destekler.

BGE-M3 yoğun getirme, RRF veya cross-encoder yeniden sıralama bu taban çizgisi
üzerinde ancak geliştirme kümesinde Recall/MRR yükselip yanlış kanıt oranını
artırmazsa etkinleştirilecektir.
