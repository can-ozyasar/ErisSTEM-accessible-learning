# Yerel özel veri / Local private data

`data/meb/` yalnızca yetkili yerel MEB PDF kaynakları içindir. `data/derived/` bu kaynaklardan üretilen sayfa görselleri, ara çıktılar ve erişilebilir dışa aktarımlar içindir.

Bu dizinlerin içeriği `.gitignore` ile dışlanır; Git'e eklenmez, GitHub'a push edilmez, hata kaydı veya test çıktısına sızdırılmaz.

`data/meb/` is only for authorised, local MEB PDF source files. `data/derived/` is for page images, intermediate artefacts, and accessible exports derived from those sources.

Their contents are excluded by `.gitignore`; never add them to Git, push them to GitHub, or leak them into logs or test output.
