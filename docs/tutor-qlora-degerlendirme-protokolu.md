# Tarih Koçu QLoRA Değerlendirme Protokolü

Bu çalışma bir doğru-şık tahmin modeli değildir. Bu nedenle doğruluk, ROC-AUC veya
üretim kaybı tek başına kabul ölçütü değildir.

## Bölünmeler ve karşılaştırma

120 soru grubu soru bazında sabit tohumla ayrılır: 84 eğitim, 18 geliştirme, 18
kapalı test. Bir sorunun altı koçluk durumu aynı bölümde kalır. Qwen3-14B taban
modeli, 1e-4 ve 5e-5 QLoRA adayları aynı geliştirme istemleriyle çalıştırılır.
Geliştirme sonucu yalnız aday seçer; son raporda kapalı test yalnız bir kez kullanılır.

Kaggle'a yalnız eğitim ve geliştirme örnekleri girer. Kapalı test, cevap anahtarı
ve PDF yerel ve private kalır.

## Ölçümler

| Alan | Birincil ölçüm | Neden |
|---|---|---|
| Retrieval | Recall@1, Recall@3, MRR@3, yanlış kanıt oranı | Kanıt doğru kaynaktan gelmeli |
| Koç davranışı | aşama doğruluğu, hata türü macro-F1, erken ifşa oranı, kaynak bağlılık oranı | Şık doğruluğu koçun amacı değildir |
| Öğrenci dili | insan incelemesinde sade/doğal Türkçe ve pedagojik yararlılık oranı | Üretimin kullanılabilirliğini ölçer |
| Güvenlik | kaynak dışı iddia, erken cevap ve gereksiz yanıtsız kalma oranları | Kritik ihlaller kabul kapısıdır |
| Gecikme | ilk token ve ilk ses p50/p95, toplam yanıt p50/p95 | Gerçek zamanlı erişilebilirlik hedefini ölçer |

Oranlar soru grubuna göre kümelenmiş yüzde 95 bootstrap güven aralığıyla
raporlanır. 18 kapalı test grubu küçük olduğundan mutlak yüzde farkı ve güven
aralığı, tek başına p-değerinden daha anlamlıdır.

Macro-F1, insanın verdiği hata türü ve aşama etiketleri için uygundur. ROC-AUC
yalnız ayrı bir olasılıklı güven/yanıtsız kalma sınıflandırıcısı kurulursa
raporlanır; serbest metin üreten koç için uygun bir ana başarı ölçütü değildir.
Üretim kaybı eğitim sağlığı sinyalidir, pedagojik kalite kanıtı değildir.

## Kabul kapısı

Adaptör ancak şu koşulların tümü sağlanırsa kullanılabilir:

1. Kapalı testte erken cevap ifşası ve kaynak dışı iddia sıfırdır.
2. Geliştirme setinde taban modelden kaynak bağlılık, aşama doğruluğu veya
   hata türü macro-F1 bakımından gerilemez.
3. İnsan incelemesinde doğal Türkçe ve pedagojik yararlılık gerilemez.
4. İlk ses p95 süresi yerel GPU hedefi olan üç saniye için raporlanır.
5. Kaynak kanıtı yetersiz vakalarda doğru yanıtsız kalma oranı raporlanır.

Koçluk sırası, geri çağırma ve düzeltici geri bildirime dayanır:
[retrieval practice sınıf derlemesi](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2019.00005/full),
[okul ortamında sistematik derleme](https://eric.ed.gov/?id=EJ1319572) ve
[hatalardan öğrenme derlemesi](https://doi.org/10.1146/annurev-psych-010416-044022).
SFT tarafında yalnız hedef koç yanıtının kayba girmesi için TRL'nin
[completion-only loss](https://huggingface.co/docs/trl/sft_trainer) ayarı kullanılır.
