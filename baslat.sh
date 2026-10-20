#!/usr/bin/env bash
# ErişSTEM yerel geliştirme başlatıcısı.
# Kullanım: ./baslat.sh [baslat|hazirla-rag|durdur|durum|loglar]

set -euo pipefail

ACTION="${1:-baslat}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker bulunamadı. Docker Desktop veya Docker Engine'i kurup başlatın." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 kullanılamıyor. 'docker compose version' çalışmalıdır." >&2
  exit 1
fi

case "$ACTION" in
  hazirla-rag)
    echo "MEB tarih kitabı için yerel konu dizini hazırlanıyor..."
    LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" docker compose run --rm --build --no-deps worker python -m app.history_rag
    ;;
  baslat)
    echo "ErişSTEM servisleri derleniyor ve başlatılıyor..."
    LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" docker compose up -d --build
    echo
    echo "Uygulama hazır olduğunda: http://localhost:5173"
    echo "Servis durumu için: ./baslat.sh durum"
    ;;
  durdur)
    docker compose stop
    echo "Servisler durduruldu. Veritabanı verisi korunur."
    ;;
  durum)
    docker compose ps
    ;;
  loglar)
    docker compose logs --tail=120 -f
    ;;
  *)
    echo "Kullanım: ./baslat.sh [baslat|hazirla-rag|durdur|durum|loglar]" >&2
    exit 2
    ;;
esac
