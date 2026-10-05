# ADR 0005: Worker sahipliği ve checksum kapısı / Worker ownership and checksum gate

Durum: Kabul edildi.

Worker yalnız `queued` durumundaki bir işi sahiplenir, `running` durumuna geçirir ve denediği sayıyı artırır. Kaynak yolu mutlak yol veya `..` içeremez; yalnız `data/meb` kökü altında göreli PDF yolu saklanır. Worker, kaynak checksum'ı kuyruktaki checksum ile uyuşmazsa çıktı yazmaz ve işi `failed/source_checksum_mismatch` durumuna getirir.

Status: Accepted. A worker only claims a `queued` job, transitions it to `running`, and increments attempts. The source is a relative PDF path beneath `data/meb`, never an absolute or traversal path. A checksum mismatch produces no output and marks the job `failed/source_checksum_mismatch`.
