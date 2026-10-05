# ADR 0001: İçerik yayını doğrulama kapısından geçer

Durum: Kabul edildi.

LLM/OCR/VLM çıktısı ders gerçeği değildir. Her öğe kaynak koordinatı, şema denetimi, güven sinyalleri ve sürümle taşınır. Formül için geçerli LaTeX/MathML ve render denetimi gerekir; düşük güvenli öğe öğretmen kuyruğuna gider. Öğrenci API'si yalnız yayımlanmış öğeleri döndürür. Öğretmen düzenlemesi audit kaydı bırakır ve onaylayıcı yayınından önce görünmez.
