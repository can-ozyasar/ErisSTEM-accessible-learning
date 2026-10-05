ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS source_relative_path VARCHAR(512);
-- Yeni üretim kurulumlarında 0001 ile birlikte NOT NULL tanımı kullanılır.
-- Eski kayıtlar için kurum yöneticisi izinli göreli yolu doldurduktan sonra uygulanır:
-- ALTER TABLE processing_jobs ALTER COLUMN source_relative_path SET NOT NULL;
