# Kanıt demeti ve ilişki grafiği

Bir öğrenci oturumunda en çok dört farklı rol kullanılabilir: `primary`, `relation`, `context`, `contrast`. Her rol farklı bir onaylı MEB parçasına ve birebir kısa alıntıya bağlıdır. `primary` zorunludur; aynı kaynak veya rol ikinci kez kullanılamaz.

Grafik düğümleri kişi, olay, tarih/dönem, yer ve kavramdır. İlişki ancak iki düğüm, tür, kaynak kimliği ve kaynaktaki birebir alıntı ile öğretmen tarafından onaylandığında öğrenciye açılır. Öneri üretimi grafik kaydı oluşturmaz.

Yanlış şıklarla ilgili bilgi yalnız `contrast` rolünde sunulur. Cevap anahtarı bu kayıtlarda, öğrenci API'sinde, ses çıktısında ve Kaggle dışa aktarımında bulunmaz.

QLoRA dışa aktarımı iki kısa alıntı sınırını korur: kaynak sırası `primary`, `relation`, `context`, `contrast` olarak belirlenir. Runtime en fazla dört erişilebilir bilgi kartı gösterebilir.
