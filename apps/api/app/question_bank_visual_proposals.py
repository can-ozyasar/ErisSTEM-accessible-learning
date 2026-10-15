"""Unreviewed editorial descriptions for eight visuals in one local PDF.

These are source-specific drafts, not a general vision model.  The extractor
uses them only when the PDF checksum matches; teacher review is mandatory.
"""

SOURCE_CHECKSUM = "532d9372bd6c1804cd6efc23d5f6eae0b94befa1131ad11961fa1e723c1dd5da"

PROPOSALS: dict[tuple[int, int, int], tuple[str, str]] = {
    (6, 7, 1): ("photo", "Eski bir gazete kupürü. Büyük başlıkta 'Dün Erzincandan 143 kişilik bir kafile geldi' yazıyor. Altında felaketzedelere yardımın sürdüğünü bildiren kısa haber ve alt bölümde birkaç kişinin siyah-beyaz fotoğrafı var."),
    (10, 7, 1): ("photo", "Kalabalık bir meydan resmi. Kadınlar, erkekler ve çocuklar bir arada; ön planda kaplar ve malzemeler, sağ tarafta atlı araba görülüyor. Bazı kişiler malzeme taşıyor veya dağıtıyor."),
    (20, 7, 1): ("table", "Türk ve Yunan kuvvetlerini karşılaştıran tablo. Sırasıyla Türk ve Yunan değerleri: subay 8.659 ve 6.564; er 199.283 ve 218.000; tüfek 100.352 ve 83.000; kılıç 5.000 ve 1.300; hafif makineli tüfek 2.025 ve 3.113; ağır makineli tüfek 839 ve 1.280; top 340 ve 418; uçak 8 ve 50."),
    (29, 1, 1): ("map", "Avrupa, Anadolu, Kuzey Afrika ve Mezopotamya'yı gösteren haritada üç renkli alan numaralandırılmış. I, Doğu Akdeniz kıyısı ile Mısır'ın kuzeyine yakın dar sarı alanda; II, Mezopotamya ve Anadolu'nun doğusuna uzanan pembe alanda; III, Batı Anadolu'da Sardes çevresindeki turuncu alanda. Akdeniz boyunca kesikli deniz yolu, Anadolu ve Mezopotamya üzerinden kara yolları gösteriliyor."),
    (31, 2, 1): ("map", "Avrupa'nın güneydoğusu, Anadolu, Mısır, Mezopotamya, İran ve Hindistan çevresini gösteren harita. Açık sarı renkle Mısır'dan Anadolu ve Mezopotamya üzerinden İran ile Hindistan'a uzanan geniş ve bitişik bir alan vurgulanmış. Mora Yarımadası ve Ege adalarının bazı bölümleri mor renkte; denizler mavi."),
    (45, 1, 1): ("diagram", "Basamaklı, çok katlı bir kerpiç yapı çizimi. Geniş dikdörtgen taban üzerinde küçülen teraslar yükseliyor; üst bölümde küçük bir yapı ve farklı seviyelere çıkan merdivenler görülüyor."),
    (46, 7, 1): ("photo", "I numaralı görsel: taş veya kil yüzeyde yatay sıralar hâlinde, kama biçimli çok sayıda kısa işaretten oluşan yazı örneği."),
    (46, 7, 2): ("photo", "II numaralı görsel: taş yüzeyde dikey bölümler içinde insan, hayvan ve nesne biçimli sembollerden oluşan yazı örneği."),
    (47, 4, 1): ("diagram", "Bir insan bedeninin yatay biçimde uzandığı tarihî tören çizimi. Bedenin çevresinde çalışan birkaç kişi, kaplar ve araçlar var; figürlerden biri çakal başlı olarak betimlenmiş."),
}


def proposal(checksum: str, page: int, question: int, visual_index: int):
    if checksum != SOURCE_CHECKSUM:
        return None
    return PROPOSALS.get((page, question, visual_index))
