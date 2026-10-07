# ADR 0013: Kaggle API yükleme koruması / Kaggle API upload guard

Durum: Kabul edildi.

Private Kaggle Dataset'leri tekrarlanabilir benchmark için yararlıdır; ancak API token, ham MEB içeriği veya yanlış klasörün uzaktaki bir Dataset'e gönderilmesi kabul edilemez. Token yalnız kullanıcının yerel Kaggle kimlik deposunda kalır. Operasyon aracı yalnız `data/private/` altındaki klasörleri kabul eder, checksum manifesti ve private işlem kaydı üretir, varsayılan olarak uzak değişiklik yapmaz. Dataset yüklemesi için açık `upload-dataset --apply` onayı gerekir.

Status: Accepted.

Private Kaggle Datasets are useful for reproducible benchmarks, but an API token, raw MEB content, or an unintended folder must never be sent to a remote Dataset. The token remains only in the user's local Kaggle credential store. The operation tool accepts directories under `data/private/` only, creates a checksum manifest and a private operation record, and performs no remote mutation by default. A Dataset upload requires explicit `upload-dataset --apply` confirmation.
