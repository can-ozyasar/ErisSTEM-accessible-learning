# ADR 0006: Geliştirme rol başlığı üretimde engellenir / Development role header is blocked in production

Durum: Kabul edildi.

`X-Role` yalnız yerel geliştirme ve test kolaylığıdır; her istekte zorunludur ve varsayılan öğrenci rolü yoktur. `APP_ENV=production` olduğunda API bu başlığı kabul ederek çalışmaz; OIDC doğrulanmış claim entegrasyonu yapılmadan 503 döner.

Status: Accepted. `X-Role` is local development/test convenience only. It is required on every request and has no implicit student default. When `APP_ENV=production`, the API returns 503 until verified OIDC claims are integrated.
