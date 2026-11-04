# Kanıt demeti ve ilişki grafiği

Bir öğrenci oturumunda en çok dört onaylı MEB parçası kullanılabilir. Roller
`primary`, `relation`, `context`, `contrast` olarak kalır; aynı role birden
fazla parça atanabilir. `primary` zorunludur; aynı kaynak ikinci kez
kullanılamaz. Her parça birebir kısa alıntı taşır.

Grafik düğümleri kişi, olay, tarih/dönem, yer ve kavramdır. İlişki ancak iki düğüm, tür, kaynak kimliği ve kaynaktaki birebir alıntı ile öğretmen tarafından onaylandığında öğrenciye açılır. Öneri üretimi grafik kaydı oluşturmaz.

Yanlış şıklarla ilgili bilgi yalnız `contrast` rolünde sunulur. Cevap anahtarı bu kayıtlarda, öğrenci API'sinde, ses çıktısında ve Kaggle dışa aktarımında bulunmaz.

QLoRA dışa aktarımı iki kısa alıntı sınırını korur: kaynak sırası `primary`, `relation`, `context`, `contrast` olarak belirlenir. Runtime en fazla dört erişilebilir bilgi kartı gösterebilir.
