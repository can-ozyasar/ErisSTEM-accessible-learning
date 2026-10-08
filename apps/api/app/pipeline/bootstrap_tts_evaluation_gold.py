"""Create a private, original Turkish STEM pronunciation calibration Gold.

These prompts are authored for evaluation only. They are not MEB material,
student content, or a voice-training corpus.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .tts_quality import TtsGoldManifest

CALIBRATION_ITEMS = (
    ("text-01", "text", "Matematikte bir tanımı anlamak için sembolün adı ve görevi birlikte dinlenmelidir.", ["tanımı", "sembolün"]),
    ("text-02", "text", "Bir kümenin elemanlarını sıralarken tekrar eden öğeler yalnız bir kez yazılır.", ["kümenin", "elemanlarını"]),
    ("text-03", "text", "Problemi çözmeden önce verilenleri ve isteneni ayrı ayrı belirleyin.", ["verilenleri", "isteneni"]),
    ("text-04", "text", "Ondalık sayıları karşılaştırırken basamak değerlerine soldan sağa bakın.", ["ondalık", "basamak"]),
    ("text-05", "text", "Bir grafiğin başlığı, eksenleri ve birimleri birlikte yorumlanmalıdır.", ["grafiğin", "birimleri"]),
    ("text-06", "text", "Tablodaki satır başlığı ile sütun başlığını eşleştirmek doğru hücreyi buldurur.", ["satır", "sütun"]),
    ("text-07", "text", "Sonucu kontrol etmek için işlemi ters işlemle doğrulayabilirsiniz.", ["ters", "doğrulayabilirsiniz"]),
    ("text-08", "text", "Negatif sayılarda işaretin değişmesi sonucun yönünü etkiler.", ["negatif", "işaretin"]),
    ("text-09", "text", "Örnek vermek, soyut bir matematik kuralını daha anlaşılır yapar.", ["soyut", "kuralını"]),
    ("text-10", "text", "Çözüm adımlarını sırayla dinlemek hata bulmayı kolaylaştırır.", ["adımlarını", "kolaylaştırır"]),
    ("text-11", "text", "Birim yazmak, ölçülen büyüklüğün neyi anlattığını açıklar.", ["Birim", "büyüklüğün"]),
    ("text-12", "text", "Eşitliğin iki tarafına aynı işlemi uygulamak dengeyi korur.", ["Eşitliğin", "dengeyi"]),
    ("formula-01", "formula", "İki x artı üç eşittir on bir.", ["artı", "eşittir"]),
    ("formula-02", "formula", "x kare eksi dokuz eşittir sıfır.", ["kare", "eksi"]),
    ("formula-03", "formula", "A birleşim B eşittir C.", ["birleşim", "eşittir"]),
    ("formula-04", "formula", "A kesişim B boş kümedir.", ["kesişim", "boş kümedir"]),
    ("formula-05", "formula", "x elemanıdır A.", ["elemanıdır"]),
    ("formula-06", "formula", "y elemanı değildir B.", ["değildir"]),
    ("formula-07", "formula", "A, B'nin alt kümesidir.", ["alt kümesidir"]),
    ("formula-08", "formula", "Karekök içinde on altı eşittir dört.", ["Karekök", "eşittir"]),
    ("formula-09", "formula", "Üç üzeri n çarpı üç üzeri iki eşittir üç üzeri n artı iki.", ["üzeri", "çarpı"]),
    ("formula-10", "formula", "Mutlak değer içinde x eksi beş eşittir iki.", ["Mutlak", "eksi"]),
    ("formula-11", "formula", "Bir bölü iki artı bir bölü üç eşittir beş bölü altı.", ["bölü", "artı"]),
    ("formula-12", "formula", "x küçük veya eşit y.", ["küçük", "eşit"]),
    ("table-01", "table", "Tablo başlangıcı. İki sütun ve üç veri satırı vardır.", ["sütun", "satırı"]),
    ("table-02", "table", "Birinci satır, birinci sütun: sembol.", ["Birinci", "sütun"]),
    ("table-03", "table", "Birinci satır, ikinci sütun: anlamı.", ["ikinci", "anlamı"]),
    ("table-04", "table", "İkinci satır, birinci sütun: birleşim.", ["İkinci", "birleşim"]),
    ("table-05", "table", "İkinci satır, ikinci sütun: iki kümenin tüm elemanları.", ["kümenin", "elemanları"]),
    ("table-06", "table", "Üçüncü satır, birinci sütun: kesişim.", ["Üçüncü", "kesişim"]),
    ("table-07", "table", "Üçüncü satır, ikinci sütun: ortak elemanlar.", ["ortak", "elemanlar"]),
    ("table-08", "table", "Dördüncü satır, birinci sütun: boş küme.", ["Dördüncü", "boş küme"]),
    ("table-09", "table", "Dördüncü satır, ikinci sütun: hiç eleman yoktur.", ["hiç", "yoktur"]),
    ("table-10", "table", "Tabloda sonraki sütuna geçmek için sağ yön tuşunu kullanın.", ["sonraki", "sütuna"]),
    ("table-11", "table", "Tabloda önceki satıra geçmek için yukarı yön tuşunu kullanın.", ["önceki", "satıra"]),
    ("table-12", "table", "Tablo sonu. Başlıklar ve hücreler tamamlandı.", ["Başlıklar", "hücreler"]),
    ("chart-01", "chart", "Grafik başlangıcı. Yatay eksen zaman, dikey eksen sıcaklıktır.", ["Yatay", "dikey"]),
    ("chart-02", "chart", "Yatay eksen dakika birimiyle sıfırdan ona ilerler.", ["dakika", "sıfırdan"]),
    ("chart-03", "chart", "Dikey eksen derece birimiyle sıcaklığı gösterir.", ["derece", "sıcaklığı"]),
    ("chart-04", "chart", "Birinci seri başlangıçta yavaşça yükselir.", ["Birinci", "yükselir"]),
    ("chart-05", "chart", "İkinci seri beşinci dakikada en yüksek değere ulaşır.", ["beşinci", "yüksek"]),
    ("chart-06", "chart", "Grafikte iki seri aynı noktada kesişir.", ["iki", "kesişir"]),
    ("chart-07", "chart", "En düşük değer başlangıç anında görülür.", ["düşük", "başlangıç"]),
    ("chart-08", "chart", "Değerler altıncı dakikadan sonra sabit kalır.", ["altıncı", "sabit"]),
    ("chart-09", "chart", "Seriler arasındaki fark üçüncü dakikada artar.", ["arasındaki", "üçüncü"]),
    ("chart-10", "chart", "Grafik özeti: önce artış, sonra dengelenme vardır.", ["artış", "dengelenme"]),
    ("chart-11", "chart", "Bir eksenin birimi değişirse sayısal yorum da değişir.", ["birimi", "sayısal"]),
    ("chart-12", "chart", "Grafik sonu. Eksenler, seriler ve eğilim okundu.", ["Eksenler", "eğilim"]),
    ("exercise-01", "exercise", "Alıştırma: A kümesinin eleman sayısını bulun.", ["Alıştırma", "eleman"]),
    ("exercise-02", "exercise", "Alıştırma: Verilen iki kümeye ait ortak elemanları yazın.", ["ortak", "elemanları"]),
    ("exercise-03", "exercise", "Alıştırma: x artı y eşittir on iki ifadesini çözün.", ["artı", "eşittir"]),
    ("exercise-04", "exercise", "Alıştırma: Sonucu yerine yazarak kontrol edin.", ["yerine", "kontrol"]),
    ("exercise-05", "exercise", "Alıştırma: Karekök içinde yirmi beş olan sayıyı bulun.", ["Karekök", "yirmi beş"]),
    ("exercise-06", "exercise", "Alıştırma: Tabloya göre en büyük değeri belirtin.", ["Tabloya", "büyük"]),
    ("exercise-07", "exercise", "Alıştırma: Grafikte azalan aralığı söyleyin.", ["Grafikte", "azalan"]),
    ("exercise-08", "exercise", "Alıştırma: Boş kümenin eleman sayısını belirleyin.", ["Boş", "eleman"]),
    ("exercise-09", "exercise", "Alıştırma: A'nın tümleyenini sembolle ifade edin.", ["tümleyenini", "sembolle"]),
    ("exercise-10", "exercise", "Alıştırma: Küçük veya eşit ilişkisini okuyun.", ["Küçük", "eşit"]),
    ("exercise-11", "exercise", "Alıştırma: Birinci satır ile üçüncü satırı karşılaştırın.", ["Birinci", "üçüncü"]),
    ("exercise-12", "exercise", "Alıştırma: Çözümün her adımını sırayla açıklayın.", ["Çözümün", "adımını"]),
)


def calibration_gold() -> TtsGoldManifest:
    """Return the balanced calibration set and fail closed if it is changed carelessly."""
    manifest = TtsGoldManifest.model_validate(
        {
            "schema_version": "tts-gold-v1",
            "items": [
                {"id": item_id, "kind": kind, "expected_spoken_text": text, "critical_tokens": tokens}
                for item_id, kind, text, tokens in CALIBRATION_ITEMS
            ],
        }
    )
    counts = Counter(item.kind for item in manifest.items)
    if len(manifest.items) != 60 or set(counts) != {"text", "formula", "table", "chart", "exercise"} or any(count != 12 for count in counts.values()):
        raise RuntimeError("unbalanced_tts_calibration_gold")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create original private Turkish STEM TTS calibration Gold")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite existing private TTS Gold")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(calibration_gold().model_dump_json(indent=2), encoding="utf-8")
    print('{"schema_version":"tts-gold-v1","items":60,"contains_student_content":false}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
