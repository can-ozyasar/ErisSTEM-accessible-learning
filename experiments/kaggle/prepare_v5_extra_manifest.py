"""Prepare extra private V5 audio for stable UI phrases and history pages."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app import history_source
from app.history_speech import history_spoken_text

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / 'data/meb/tarih-9sinif-ders-kitabi_20261006.pdf'
QUESTIONS = ROOT / 'data/soru_bankasi/vip-9-sinif-tarih-soru-bankasi.pdf'
OUTPUT = ROOT / 'data/private/tts-v5-extra-input-v1'


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def interface_phrases() -> set[str]:
    phrases = {
        'Sesli keşif açık. Tab ile öğelere geç, Enter ile aç. Kaydırmalı menülerde sağ ve sol ok tuşlarını kullanabilirsin.',
        'Önceki alan, düğme', 'Sonraki alan, düğme', 'Sonraki alan, düğme, kullanılamıyor',
        'Önceki alan, düğme, kullanılamıyor', 'Önceki öğrenme alanı, düğme',
        'Sonraki öğrenme alanı, düğme', 'Önceki öğrenme alanı, düğme, kullanılamıyor',
        'Sonraki öğrenme alanı, düğme, kullanılamıyor',
        'Kütüphaneye dön, düğme', '← Kütüphaneye dön, düğme', '← Önceki, düğme',
        'Sonraki →, düğme', 'Başka sayfaya git, açılır bölüm',
        'PDF sayfası, giriş alanı', 'Sesli komutları aç, açılır bölüm',
        'Sayfadaki bölümler, başlık', 'Seçili bölümü seslendir, düğme',
        'Seslendirmeyi durdur, düğme', 'Sesli soru-cevap çalışması, başlık',
        'Soru seç, seçim alanı', 'Soruyu sesli oku, düğme', 'Yanıtım, yazı alanı',
        'Kaynak ipuçlarını göster, düğme', 'Kaynak ipuçlarını gizle, düğme',
        'Sesi durdur, düğme', 'Soruyu seslendir, düğme',
        'Ana giriş, bağlantı', 'Öğrenci, bağlantı', 'Öğretmen, bağlantı',
    }
    labels = ['Başlık', 'Kaynak', 'Metin', 'Görsel', 'Karekod', 'Soru veya yönerge', 'Çalışma alanı', 'Kaynakça']
    phrases.update(f'{label}. Sayfadaki kaynak bölümü. Tamamını dinlemek için etkinleştirin' for label in labels)
    for filename, ordinals, kind in [
        ('EntryPortal.tsx', ['İki alandan birincisi', 'İki alandan ikincisi'], 'bağlantı'),
        ('StudentLibrary.tsx', ['Üç alandan birincisi', 'Üç alandan ikincisi', 'Üç alandan üçüncüsü'], 'düğme'),
    ]:
        source = (ROOT / 'apps/web/src' / filename).read_text(encoding='utf-8').split('] as const;')[0]
        areas = re.findall(r'title: "([^\"]+)", description: "([^\"]+)"', source)
        if len(areas) != len(ordinals):
            raise ValueError(f'Unexpected menu definitions: {filename}')
        for (title, description), ordinal in zip(areas, ordinals, strict=True):
            phrases.add(f'{title}. {description} Enter tuşuyla veya dokunarak aç. {ordinal}.')
            phrases.add(f'{title}. {description}. Enter tuşuyla veya dokunarak aç., {kind}')
            phrases.add(f'{title}, ekran açıldı')
    return phrases


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError('manifest_already_exists')
    history_source.BOOK = HISTORY
    items = []
    for page in range(50, 60):
        for region in history_source._page_data(page)['regions']:
            if not region['spoken_text'] or region['kind'] == 'external_link':
                continue
            text = history_spoken_text(region['spoken_text'])
            items.append({'kind': 'history', 'id': region['id'], 'page': page, 'spoken_text': text,
                          'spoken_text_sha256': digest(text.encode()), 'contains_digits': bool(re.search(r'\d', text))})
    for text in sorted(interface_phrases()):
        if re.search(r'\d', text):
            raise ValueError('interface_text_contains_digit')
        text_hash = digest(text.encode())
        items.append({'kind': 'interface', 'id': text_hash, 'page': 0, 'spoken_text': text,
                      'spoken_text_sha256': text_hash, 'contains_digits': False})
    identities = [(i['kind'], i['id']) for i in items]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate_id')
    payload = {'schema_version': 'v5-demo-input-v1', 'history_pdf_sha256': digest(HISTORY.read_bytes()),
               'question_pdf_sha256': digest(QUESTIONS.read_bytes()), 'history_pages': list(range(50, 60)),
               'approved_questions': 0, 'items': items}
    OUTPUT.mkdir(parents=True)
    (OUTPUT / 'manifest.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'interface': sum(i['kind'] == 'interface' for i in items),
                      'history': sum(i['kind'] == 'history' for i in items),
                      'with_digits': sum(i['contains_digits'] for i in items),
                      'unique_to_generate': len({i['spoken_text_sha256'] for i in items if not i['contains_digits']})}))


if __name__ == '__main__':
    main()
