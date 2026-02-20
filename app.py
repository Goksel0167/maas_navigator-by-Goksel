#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MaaşPro - Bordro & Finans Yönetim Sistemi
Profesyonel bordro hesaplama, tazminat analizi ve yatırım planlama uygulaması
"""

from datetime import datetime, date
from typing import Dict, List, Tuple
import sqlite3
import os
import shutil

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────────
#  KALICI VERİTABANI YOLU
# ─────────────────────────────────────────────
def _db_yolu() -> str:
    """Veritabanını kullanıcının AppData/Local altında sabit bir dizine koyar.
    Böylece proje klasörü taşınsa veya silinse bile kayıtlar kaybolmaz."""
    appdata = os.environ.get('LOCALAPPDATA',
                 os.path.join(os.path.expanduser('~'), 'AppData', 'Local'))
    dizin = os.path.join(appdata, 'MaasNavigator')
    os.makedirs(dizin, exist_ok=True)
    return os.path.join(dizin, 'maaspro.db')

def _otomatik_yedekle(db_yolu: str):
    """Her gün bir kez (gün değişince) DB'nin yedeğini aynı dizinde saklar,
    en fazla 30 günlük yedek tutar."""
    try:
        dizin = os.path.dirname(db_yolu)
        bugun = datetime.now().strftime('%Y-%m-%d')
        yedek_yolu = os.path.join(dizin, f'maaspro_yedek_{bugun}.db')
        if not os.path.exists(yedek_yolu) and os.path.exists(db_yolu):
            shutil.copy2(db_yolu, yedek_yolu)
        # 30 günden eski yedekleri sil
        for dosya in os.listdir(dizin):
            if dosya.startswith('maaspro_yedek_') and dosya.endswith('.db'):
                tam_yol = os.path.join(dizin, dosya)
                try:
                    tarih_str = dosya.replace('maaspro_yedek_', '').replace('.db', '')
                    tarih = datetime.strptime(tarih_str, '%Y-%m-%d')
                    if (datetime.now() - tarih).days > 30:
                        os.remove(tam_yol)
                except Exception:
                    pass
    except Exception:
        pass

DB_YOLU = _db_yolu()
_otomatik_yedekle(DB_YOLU)


# ─────────────────────────────────────────────
#  İŞ MANTIĞI SINIFLARI
# ─────────────────────────────────────────────

class BordroYonetim:
    """Bordro kayıtlarını yöneten sınıf"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = DB_YOLU
        self.db_path = db_path
        self.baglanti_olustur()

    def baglanti_olustur(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bordrolar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ay TEXT NOT NULL,
                brut REAL NOT NULL,
                net REAL NOT NULL,
                sgk_kesinti REAL,
                gelir_vergisi REAL,
                damga_vergisi REAL,
                eklenme_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
                satis_primi REAL DEFAULT 0
            )
        ''')
        # Eski veritabanları için satis_primi sütununu ekle
        try:
            cursor.execute('ALTER TABLE bordrolar ADD COLUMN satis_primi REAL DEFAULT 0')
        except Exception:
            pass  # Sütun zaten varsa geç
        conn.commit()
        conn.close()

    def bordro_ekle(self, ay: str, brut: float, net: float,
                     satis_primi: float = 0.0) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            sgk = brut * 0.14
            damga = brut * 0.00759
            gelir_vergisi = brut - net - sgk - damga
            cursor.execute('''
                INSERT INTO bordrolar
                    (ay, brut, net, sgk_kesinti, gelir_vergisi, damga_vergisi, satis_primi)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ay, brut, net, sgk, gelir_vergisi, damga, satis_primi))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def bordrolari_getir(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bordrolar ORDER BY ay DESC')
        rows = cursor.fetchall()
        bordrolar = []
        for row in rows:
            bordrolar.append({
                'id': row[0], 'ay': row[1], 'brut': row[2], 'net': row[3],
                'sgk_kesinti': row[4], 'gelir_vergisi': row[5],
                'damga_vergisi': row[6], 'eklenme_tarihi': row[7],
                'satis_primi': row[8] if len(row) > 8 else 0.0
            })
        conn.close()
        return bordrolar

    def bordro_sil(self, bordro_id: int) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM bordrolar WHERE id = ?', (bordro_id,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def bordro_guncelle(self, bordro_id: int, sabit_brut: float,
                         satis_primi: float, net: float) -> bool:
        try:
            toplam_brut = sabit_brut + satis_primi
            sgk = toplam_brut * 0.14
            damga = toplam_brut * 0.00759
            gelir_vergisi = toplam_brut - net - sgk - damga
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bordrolar
                SET brut=?, net=?, sgk_kesinti=?, gelir_vergisi=?,
                    damga_vergisi=?, satis_primi=?
                WHERE id=?
            ''', (toplam_brut, net, sgk, gelir_vergisi, damga,
                  satis_primi, bordro_id))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def istatistikler(self) -> Dict:
        bordrolar = self.bordrolari_getir()
        if not bordrolar:
            return {'toplam': 0, 'ortalama_brut': 0, 'ortalama_net': 0,
                    'toplam_kazanc': 0, 'toplam_kesinti': 0}
        toplam_brut = sum(b['brut'] for b in bordrolar)
        toplam_net = sum(b['net'] for b in bordrolar)
        toplam_prim = sum(b.get('satis_primi', 0) or 0 for b in bordrolar)
        return {
            'toplam': len(bordrolar),
            'ortalama_brut': toplam_brut / len(bordrolar),
            'ortalama_net': toplam_net / len(bordrolar),
            'toplam_kazanc': toplam_brut,
            'toplam_kesinti': toplam_brut - toplam_net,
            'toplam_satis_primi': toplam_prim
        }


class TazminatHesaplayici:
    KIDEM_TAVAN = 64948.77

    @staticmethod
    def calisma_suresi_hesapla(baslama: str, bitis: str) -> Tuple[int, int]:
        baslama_tarih = datetime.strptime(baslama, '%Y-%m-%d')
        bitis_tarih = datetime.strptime(bitis, '%Y-%m-%d')
        fark = bitis_tarih - baslama_tarih
        toplam_gun = fark.days
        yil = toplam_gun // 365
        gun = toplam_gun % 365
        return yil, gun

    @staticmethod
    def kidem_tazminati_hesapla(brut_maas: float, calisma_yil: int,
                                 calisma_gun: int, cikis_sebebi: str) -> float:
        kidem_hakki = cikis_sebebi in ['isverenFeshi', 'emeklilik', 'olum', 'askerlik']
        if not kidem_hakki or calisma_yil < 1:
            return 0.0
        brut_yillik = min(brut_maas, TazminatHesaplayici.KIDEM_TAVAN)
        kidem = brut_yillik * calisma_yil
        if calisma_gun > 0:
            kidem += (brut_yillik / 365) * calisma_gun
        return kidem

    @staticmethod
    def ihbar_tazminati_hesapla(brut_maas: float, calisma_yil: float,
                                 cikis_sebebi: str) -> float:
        if cikis_sebebi != 'isverenFeshi':
            return 0.0
        if calisma_yil < 0.5:
            return brut_maas * 2 / 4
        elif calisma_yil < 1.5:
            return brut_maas * 4 / 4
        elif calisma_yil < 3:
            return brut_maas * 6 / 4
        else:
            return brut_maas * 8 / 4

    @staticmethod
    def yillik_izin_ucreti_hesapla(brut_maas: float, kalan_izin: int,
                                    calisilan_gun: int = 22) -> Dict:
        """30/çalışılan_gün katsayısı ile düzeltilmiş günlük brüt hesabı"""
        gunluk_brut  = brut_maas / 30
        carpan       = 30 / calisilan_gun if calisilan_gun > 0 else 1.0
        duzgun       = carpan * kalan_izin          # düzeltilmiş gün sayısı
        izin_brut    = duzgun * gunluk_brut
        return {
            'gunluk_brut':   gunluk_brut,
            'carpan':        round(carpan, 4),
            'duzeltilmis_gun': round(duzgun, 4),
            'brut':          izin_brut,
        }

    @staticmethod
    def vergi_kesintileri_hesapla(toplam_brut: float) -> Dict[str, float]:
        sgk_kesinti = toplam_brut * 0.14
        vergi_matrahi = toplam_brut - sgk_kesinti
        if vergi_matrahi <= 110000:
            gelir_vergisi = vergi_matrahi * 0.15
        elif vergi_matrahi <= 230000:
            gelir_vergisi = 110000 * 0.15 + (vergi_matrahi - 110000) * 0.20
        elif vergi_matrahi <= 580000:
            gelir_vergisi = 110000 * 0.15 + 120000 * 0.20 + (vergi_matrahi - 230000) * 0.27
        elif vergi_matrahi <= 3000000:
            gelir_vergisi = (110000 * 0.15 + 120000 * 0.20 + 350000 * 0.27
                             + (vergi_matrahi - 580000) * 0.35)
        else:
            gelir_vergisi = (110000 * 0.15 + 120000 * 0.20 + 350000 * 0.27
                             + 2420000 * 0.35 + (vergi_matrahi - 3000000) * 0.40)
        damga_vergisi = toplam_brut * 0.00759
        return {
            'sgk': sgk_kesinti,
            'gelir_vergisi': gelir_vergisi,
            'damga': damga_vergisi,
            'toplam_kesinti': sgk_kesinti + gelir_vergisi + damga_vergisi
        }

    @classmethod
    def tam_hesaplama(cls, brut_maas: float, baslama: str, bitis: str,
                      cikis_sebebi: str, kalan_izin: int = 0,
                      calisilan_gun: int = 22) -> Dict:
        yil, gun = cls.calisma_suresi_hesapla(baslama, bitis)
        calisma_yil_desimal = yil + (gun / 365)
        kidem = cls.kidem_tazminati_hesapla(brut_maas, yil, gun, cikis_sebebi)
        ihbar = cls.ihbar_tazminati_hesapla(brut_maas, calisma_yil_desimal, cikis_sebebi)

        # ─ Yıllık izin: (30/çalışılan_gün) × kalan_izin × günlük_brüt ────────────────
        yi = cls.yillik_izin_ucreti_hesapla(brut_maas, kalan_izin, calisilan_gun)
        yillik_izin_brut = yi['brut']
        if yillik_izin_brut > 0:
            yi_kes = cls.vergi_kesintileri_hesapla(yillik_izin_brut)
        else:
            yi_kes = {'sgk': 0, 'gelir_vergisi': 0, 'damga': 0, 'toplam_kesinti': 0}
        yillik_izin_net = yillik_izin_brut - yi_kes['toplam_kesinti']

        # ─ Kıdem + İhbar kendi toplamı üzerine vergilendirilir ─
        ki_brut = kidem + ihbar
        if ki_brut > 0:
            ki_kes = cls.vergi_kesintileri_hesapla(ki_brut)
        else:
            ki_kes = {'sgk': 0, 'gelir_vergisi': 0, 'damga': 0, 'toplam_kesinti': 0}
        ki_net = ki_brut - ki_kes['toplam_kesinti']

        toplam_brut = ki_brut + yillik_izin_brut
        kesintiler = {
            'sgk': ki_kes['sgk'] + yi_kes['sgk'],
            'gelir_vergisi': ki_kes['gelir_vergisi'] + yi_kes['gelir_vergisi'],
            'damga': ki_kes['damga'] + yi_kes['damga'],
            'toplam_kesinti': ki_kes['toplam_kesinti'] + yi_kes['toplam_kesinti']
        }
        net_tutar = ki_net + yillik_izin_net

        return {
            'calisma_suresi': {'yil': yil, 'gun': gun, 'toplam_yil': calisma_yil_desimal},
            'tazminatlar': {
                'kidem': kidem, 'ihbar': ihbar,
                'yillik_izin_brut':      yillik_izin_brut,
                'yillik_izin_net':       yillik_izin_net,
                'yillik_izin_detay':     yi,          # gunluk_brut, carpan, duzeltilmis_gun
                'toplam_brut': toplam_brut,
            },
            'kesintiler': kesintiler,
            'net_tutar': net_tutar
        }


class AsgariUcretAnaliz:
    ASGARI_UCRETLER = [
        {'yil': 2020, 'donem': 1, 'brut': 2943.00,  'net': 2324.71,  'artis': 15.0},
        {'yil': 2020, 'donem': 2, 'brut': 2943.00,  'net': 2324.71,  'artis': 0.0},
        {'yil': 2021, 'donem': 1, 'brut': 3577.50,  'net': 2825.90,  'artis': 21.56},
        {'yil': 2021, 'donem': 2, 'brut': 3577.50,  'net': 2825.90,  'artis': 0.0},
        {'yil': 2022, 'donem': 1, 'brut': 4253.40,  'net': 3361.88,  'artis': 18.98},
        {'yil': 2022, 'donem': 2, 'brut': 5500.35,  'net': 4250.45,  'artis': 29.32},
        {'yil': 2023, 'donem': 1, 'brut': 8506.80,  'net': 6402.21,  'artis': 50.63},
        {'yil': 2023, 'donem': 2, 'brut': 11402.32, 'net': 8502.07,  'artis': 34.04},
        {'yil': 2024, 'donem': 1, 'brut': 17002.12, 'net': 12475.11, 'artis': 49.12},
        {'yil': 2024, 'donem': 2, 'brut': 20002.50, 'net': 14738.06, 'artis': 17.65},
        {'yil': 2025, 'donem': 1, 'brut': 26005.50, 'net': 22104.67, 'artis': 30.02},
        {'yil': 2025, 'donem': 2, 'brut': 26005.50, 'net': 22104.67, 'artis': 0.0},
        {'yil': 2026, 'donem': 1, 'brut': 33030.00, 'net': 28075.50, 'artis': 27.0},
    ]

    @classmethod
    def katsayi_hesapla(cls, maas: float, yil: int = 2026) -> Dict:
        guncel = [au for au in cls.ASGARI_UCRETLER if au['yil'] == yil][-1]
        return {
            'asgari_ucret': guncel,
            'katsayi': round(maas / guncel['brut'], 2),
            'fark': maas - guncel['brut']
        }

    @classmethod
    def toplam_artis(cls) -> float:
        ilk = cls.ASGARI_UCRETLER[0]['brut']
        son = cls.ASGARI_UCRETLER[-1]['brut']
        return round((son / ilk - 1) * 100, 2)


class ButcePlanlama:
    @staticmethod
    def butce_hesapla(net_gelir: float) -> Dict:
        return {
            'net_gelir': net_gelir,
            'ihtiyaclar': {
                'tutar': net_gelir * 0.50, 'oran': 50,
                'kategoriler': ['Kira / Konut kredisi', 'Faturalar (elektrik, su, doğalgaz)',
                                'Market ve yiyecek', 'Ulaşım', 'Sigorta ödemeleri']
            },
            'istekler': {
                'tutar': net_gelir * 0.30, 'oran': 30,
                'kategoriler': ['Eğlence ve hobi', 'Dışarıda yemek', 'Alışveriş',
                                'Seyahat ve tatil', 'Abonelikler']
            },
            'tasarruf': {
                'tutar': net_gelir * 0.20, 'oran': 20,
                'kategoriler': ['Acil durum fonu', 'Yatırım (hisse, altın, döviz)',
                                'Emeklilik planı', 'Büyük harcamalar'],
                'yillik_birikim': net_gelir * 0.20 * 12
            }
        }


class YatirimHesaplayici:
    PORTFOY_STRATEJILERI = {
        'dusuk': [
            {'ad': 'Vadeli TL Mevduat', 'oran': 50, 'yillik_getiri': 2.5},
            {'ad': 'Devlet Tahvili',     'oran': 30, 'yillik_getiri': 2.3},
            {'ad': 'Altın',              'oran': 20, 'yillik_getiri': 1.5},
        ],
        'orta': [
            {'ad': 'Hisse Senedi Fonu', 'oran': 40, 'yillik_getiri': 3.5},
            {'ad': 'Vadeli Mevduat',    'oran': 30, 'yillik_getiri': 2.5},
            {'ad': 'Altın',             'oran': 20, 'yillik_getiri': 1.5},
            {'ad': 'Döviz',             'oran': 10, 'yillik_getiri': 2.0},
        ],
        'yuksek': [
            {'ad': 'Hisse Senedi', 'oran': 50, 'yillik_getiri': 4.5},
            {'ad': 'Kripto Para',  'oran': 20, 'yillik_getiri': 5.0},
            {'ad': 'Hisse Fonu',   'oran': 20, 'yillik_getiri': 3.5},
            {'ad': 'Altın',        'oran': 10, 'yillik_getiri': 1.5},
        ],
    }

    @classmethod
    def yatirim_hesapla(cls, aylik_tasarruf: float, vade_ay: int,
                        risk_profili: str = 'orta') -> Dict:
        portfoy = cls.PORTFOY_STRATEJILERI.get(risk_profili,
                                                cls.PORTFOY_STRATEJILERI['orta'])
        toplam_birikim = aylik_tasarruf * vade_ay
        ortalama_getiri = sum(y['yillik_getiri'] * y['oran'] / 100 for y in portfoy)
        yil = vade_ay / 12
        beklenen_getiri = toplam_birikim * (pow(1 + ortalama_getiri / 100, yil) - 1)
        toplam_deger = toplam_birikim + beklenen_getiri

        dagilim = [
            {'ad': y['ad'], 'oran': y['oran'],
             'miktar': toplam_birikim * y['oran'] / 100,
             'getiri_orani': y['yillik_getiri']}
            for y in portfoy
        ]

        projeksiyon = []
        for yil_sayisi in [1, 2, 3, 5, 10]:
            birikim = aylik_tasarruf * yil_sayisi * 12
            getiri = birikim * (pow(1 + ortalama_getiri / 100, yil_sayisi) - 1)
            projeksiyon.append({'yil': yil_sayisi, 'birikim': birikim,
                                'getiri': getiri, 'toplam': birikim + getiri})

        return {
            'risk_profili': risk_profili, 'vade_ay': vade_ay,
            'aylik_tasarruf': aylik_tasarruf, 'toplam_birikim': toplam_birikim,
            'ortalama_getiri': ortalama_getiri, 'beklenen_getiri': beklenen_getiri,
            'toplam_deger': toplam_deger, 'portfoy_dagilimi': dagilim,
            'uzun_vade_projeksiyon': projeksiyon
        }


class MaasZamHesaplayici:
    @staticmethod
    def zam_analizi(mevcut_brut: float, zam_orani: float,
                    enflasyon: float) -> Dict:
        yeni_brut = mevcut_brut * (1 + zam_orani / 100)
        artis = yeni_brut - mevcut_brut
        mevcut_net = mevcut_brut * 0.65
        yeni_net = yeni_brut * 0.65
        net_artis = yeni_net - mevcut_net
        reel_zam = ((1 + zam_orani / 100) / (1 + enflasyon / 100) - 1) * 100
        return {
            'mevcut_brut': mevcut_brut, 'mevcut_net': mevcut_net,
            'zam_orani': zam_orani, 'yeni_brut': yeni_brut, 'yeni_net': yeni_net,
            'brut_artis': artis, 'net_artis': net_artis, 'enflasyon': enflasyon,
            'reel_zam': reel_zam, 'durum': 'kazanc' if reel_zam > 0 else 'kayip',
            'yillik_net_kazanc': net_artis * 12, 'besyillik_kazanc': net_artis * 60
        }


# ─────────────────────────────────────────────
#  YARDIMCI FONKSİYON
# ─────────────────────────────────────────────

def tl(tutar: float) -> str:
    """₺ formatında göster"""
    return f"₺{tutar:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


# ─────────────────────────────────────────────
#  STREAMLIT SAYFALAR
# ─────────────────────────────────────────────

def sayfa_tazminat():
    st.header("💰 Tazminat Hesaplama")
    st.caption("Kıdem · İhbar · Yıllık İzin tazminatlarını hesaplayın")

    with st.form("tazminat_form"):
        col1, col2 = st.columns(2)
        with col1:
            brut = st.number_input("Brüt Maaş (₺)", min_value=0.0,
                                    value=50000.0, step=1000.0)
            baslama = st.date_input("İşe Başlama Tarihi", value=date(2020, 1, 1))
        with col2:
            bitis = st.date_input("İşten Çıkış Tarihi", value=date.today())
            kalan_izin = st.number_input("Kullanılmayan Yıllık İzin (Gün)",
                                          min_value=0, value=0, step=1)
            calisilan_gun = st.number_input(
                "Aylık Çalışılan Gün Sayısı",
                min_value=1, max_value=31, value=22, step=1,
                help="İzinlerin hesaplanacağı aylık çalışılan gün sayısı (genellikle 22)"
            )

        cikis_secenekleri = {
            "İstifa (Kendi İsteğimle)":         "istifa",
            "İşveren Feshi (Haklı Sebep Yok)":  "isverenFeshi",
            "İşveren Feshi (Haklı Sebep)":       "hakliSebep",
            "Emeklilik":                         "emeklilik",
            "Ölüm":                              "olum",
            "Askerlik":                          "askerlik",
        }
        col_sebep, col_paket = st.columns([3, 1])
        with col_sebep:
            cikis_secim = st.selectbox("İşten Çıkış Sebebi", list(cikis_secenekleri.keys()))
        with col_paket:
            paket_sayisi = st.number_input(
                "Anlaşma Paketi (adet)",
                min_value=0, value=0, step=1,
                help="İşveren feshinde anlaşılan paket sayısı. 1 paket = 1 net maaş."
            )
        hesapla = st.form_submit_button("🔍 Hesapla", use_container_width=True)

    if hesapla:
        if bitis <= baslama:
            st.error("Çıkış tarihi, başlama tarihinden sonra olmalıdır!")
            return
        cikis_sebebi = cikis_secenekleri[cikis_secim]
        sonuc = TazminatHesaplayici.tam_hesaplama(
            brut, str(baslama), str(bitis), cikis_sebebi,
            int(kalan_izin), int(calisilan_gun)
        )
        cs = sonuc['calisma_suresi']
        t  = sonuc['tazminatlar']
        k  = sonuc['kesintiler']

        st.success(f"⏱️  Çalışma Süresi: **{cs['yil']} yıl {cs['gun']} gün**")

        col1, col2, col3 = st.columns(3)
        col1.metric("Kıdem Tazminatı",        tl(t['kidem']) if t['kidem'] > 0 else "Hak Yok")
        col2.metric("İhbar Tazminatı",        tl(t['ihbar']) if t['ihbar'] > 0 else "Hak Yok")
        col3.metric("Yıllık İzin Ücreti (Net)",
                    tl(t['yillik_izin_net']) if t['yillik_izin_net'] > 0 else "-")

        if t['yillik_izin_brut'] > 0:
            yd = t['yillik_izin_detay']
            st.caption(
                f"📋 Yıllık İzin Hesabı: "
                f"Günlük brüt = {tl(yd['gunluk_brut'])} · "
                f"Katsayı = 30÷{calisilan_gun} = **{yd['carpan']:.4f}** · "
                f"Düzeltilmiş gün = {yd['carpan']:.4f}×{kalan_izin} = **{yd['duzeltilmis_gun']:.2f}** gün · "
                f"Brüt = **{tl(yd['brut'])}**"
            )

        st.divider()
        col4, col5, col6 = st.columns(3)
        col4.metric("Brüt Toplam",   tl(t['toplam_brut']))
        col5.metric("Toplam Kesinti", f"-{tl(k['toplam_kesinti'])}")
        col6.metric("✅ NET ÖDEME",   tl(sonuc['net_tutar']))

        # ── Anlaşma Paketi (sadece işveren feshinde) ───────────────────────
        if cikis_sebebi == 'isverenFeshi' and paket_sayisi > 0:
            kesinti_aylik = TazminatHesaplayici.vergi_kesintileri_hesapla(brut)
            net_maas = brut - kesinti_aylik['toplam_kesinti']
            paket_tutari = net_maas * paket_sayisi
            toplam_paketli = sonuc['net_tutar'] + paket_tutari

            st.divider()
            st.subheader("🤝 Anlaşma Paketi")
            st.caption("İşveren ile mutabık kalınan paket ödemesi (yasal tazminata ek)")
            col7, col8, col9 = st.columns(3)
            col7.metric("Net Aylık Maaş", tl(net_maas))
            col8.metric(f"Paket Tutarı ({paket_sayisi} × net maaş)", tl(paket_tutari))
            col9.metric("💰 Tazminat + Paket (Net)", tl(toplam_paketli))

        # ── Pasta grafik ─────────────────────────────────────────────────────
        if t['toplam_brut'] > 0:
            pie_names  = ['SGK Kesintisi', 'Gelir Vergisi', 'Damga Vergisi', 'Net Tutar']
            pie_values = [k['sgk'], k['gelir_vergisi'], k['damga'], sonuc['net_tutar']]
            if cikis_sebebi == 'isverenFeshi' and paket_sayisi > 0:
                pie_names.append(f'Anlaşma Paketi ({paket_sayisi}x)')
                pie_values.append(paket_tutari)
            fig = px.pie(
                names=pie_names,
                values=pie_values,
                title="Tazminat Dağılımı",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig, use_container_width=True)


def _vergi_dilimi(brut_aylik: float) -> str:
    """Aylık brüt maaşa göre hangi gelir vergisi dilimine girdiğini göster"""
    # Yıllık matrah tahmini (12 ay, SGK sonrası)
    yillik = brut_aylik * 12 * 0.86   # SGK %14 düşülmüş yaklaşık matrah
    if yillik <= 110000:
        return "%15 (1. Dilim)"
    elif yillik <= 230000:
        return "%20 (2. Dilim)"
    elif yillik <= 580000:
        return "%27 (3. Dilim)"
    elif yillik <= 3000000:
        return "%35 (4. Dilim)"
    else:
        return "%40 (5. Dilim)"

def _dilim_rengi(dilim: str) -> str:
    return {"1": "🟢", "2": "🟡", "3": "🟠", "4": "🔴", "5": "🟣"}.get(
        dilim.split(".")[0].replace("%15 (", "").replace("%20 (", "")
        .replace("%27 (", "").replace("%35 (", "").replace("%40 (", "")
        .replace(" Dilim)", "").strip(), "⚪")

def sayfa_bordro():
    st.header("📊 Bordro Arşivi")
    bm = BordroYonetim()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "➕ Bordro Ekle",
        "📅 Yıllara Göre",
        "📊 Maaş Zammı Analizi",
        "🧮 Vergi Dilimi Karşılaştırması",
        "💰 Satış Primi Analizi",
        "📈 İstatistikler"
    ])

    # ── TAB 1: BORDRO EKLE ────────────────────────────────────────────────
    with tab1:
        with st.form("bordro_ekle"):
            col1, col2 = st.columns(2)
            with col1:
                ay = st.text_input("Ay (YYYY-MM)", placeholder="2026-01")
            with col2:
                net = st.number_input("Net Maaş (₺)", min_value=0.0,
                                       value=28075.0, step=500.0)
            col3, col4 = st.columns(2)
            with col3:
                sabit_brut = st.number_input("Sabit Brüt Maaş (₺)", min_value=0.0,
                                              value=33030.0, step=500.0)
            with col4:
                satis_primi = st.number_input("Satış Primi (₺)", min_value=0.0,
                                               value=0.0, step=500.0,
                                               help="Varsa o aya ait satış primini ayrıca girin")
            toplam_brut = sabit_brut + satis_primi
            if satis_primi > 0:
                st.info(f"💡 Toplam Brüt: {tl(sabit_brut)} (sabit) + {tl(satis_primi)} (prim) "
                        f"= **{tl(toplam_brut)}**")
            ekle = st.form_submit_button("✅ Bordroyu Kaydet", use_container_width=True)
        if ekle:
            if bm.bordro_ekle(ay, toplam_brut, net, satis_primi):
                st.success("Bordro başarıyla eklendi!")
                st.rerun()
            else:
                st.error("Bordro eklenemedi! Ay formatını kontrol edin (YYYY-MM).")

        st.divider()

        # Kalıcı depolama bilgisi
        with st.expander("💾 Veri Güvenliği & Yedekler", expanded=False):
            db_dizin = os.path.dirname(DB_YOLU)
            st.success(f"✅ Bordro kayıtlarınız kalıcı olarak saklanıyor:\n\n`{DB_YOLU}`")
            st.caption("Proje klasörü taşınsa veya silinse bile bu konumdaki veriler güvende kalır.")
            st.divider()
            st.caption("📦 Otomatik Günlük Yedekler")
            yedekler = sorted([
                f for f in os.listdir(db_dizin)
                if f.startswith('maaspro_yedek_') and f.endswith('.db')
            ], reverse=True)
            if yedekler:
                for y in yedekler[:10]:
                    tam = os.path.join(db_dizin, y)
                    boyut = os.path.getsize(tam) / 1024
                    st.write(f"📁 `{y}` — {boyut:.1f} KB")
                if len(yedekler) > 10:
                    st.caption(f"...ve {len(yedekler)-10} yedek daha (son 30 gün saklanır)")
            else:
                st.info("Henüz yedek yok — uygulama her yeni gün açıldığında otomatik yedek alınır.")

            st.divider()
            st.caption("🗑️ Bordro Sil")
            sil_id = st.number_input("Silmek istediğiniz Bordro ID:", min_value=1, step=1)
            if st.button("🗑️ Seçili Bordroyu Sil"):
                if bm.bordro_sil(int(sil_id)):
                    st.success("Bordro silindi!")
                    st.rerun()
                else:
                    st.error("Bordro silinemedi!")

    # ── TAB 2: YILLARA GÖRE ───────────────────────────────────────────────
    with tab2:
        bordrolar = bm.bordrolari_getir()
        if not bordrolar:
            st.info("Henüz bordro kaydı yok.")
        else:
            df = pd.DataFrame(bordrolar)
            df['yil'] = df['ay'].str[:4]
            yillar = sorted(df['yil'].unique(), reverse=True)

            secili_yil = st.selectbox("Yıl Seç", yillar)

            df_yil = df[df['yil'] == secili_yil].sort_values('ay').reset_index(drop=True)
            df_yil['satis_primi'] = df_yil['satis_primi'].fillna(0)
            df_yil['sabit_brut']  = df_yil['brut'] - df_yil['satis_primi']

            # Özet metrikler
            toplam_prim_yil = df_yil['satis_primi'].sum()
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric(f"{secili_yil} Toplam Kayıt", len(df_yil))
            c2.metric("Ort. Brüt", tl(df_yil['brut'].mean()))
            c3.metric("Ort. Net",  tl(df_yil['net'].mean()))
            c4.metric("Toplam Kazanç", tl(df_yil['brut'].sum()))
            c5.metric("Toplam Prim", tl(toplam_prim_yil),
                      delta=f"%{toplam_prim_yil / df_yil['brut'].sum() * 100:.1f} brütün" if df_yil['brut'].sum() > 0 else None,
                      delta_color="off")

            st.divider()

            # ── Satır bazlı düzenle / sil ────────────────────────────────
            duz_key = 'duz_bordro_id'
            if duz_key not in st.session_state:
                st.session_state[duz_key] = None

            basliklar = st.columns([1.2, 1.8, 1.8, 1.8, 1.8, 1.8, 1, 1])
            for h, lbl in zip(basliklar, ['Ay', 'Sabit Brüt', 'Prim', 'Toplam Brüt', 'Net', 'Kesinti', '✏️', '🗑️']):
                h.markdown(f"**{lbl}**")

            for _, satir in df_yil.iterrows():
                rid       = int(satir['id'])
                kesinti   = satir['sgk_kesinti'] + satir['gelir_vergisi'] + satir['damga_vergisi']
                duzenle_aktif = (st.session_state[duz_key] == rid)

                if duzenle_aktif:
                    # ── Düzenleme formu (satır genişliğinde) ────────────
                    with st.form(key=f'form_{rid}', border=True):
                        st.markdown(f"**✏️ {satir['ay']} — Düzenleniyor**")
                        fc1, fc2, fc3 = st.columns(3)
                        yeni_sabit = fc1.number_input(
                            "Sabit Brüt (₺)", value=float(satir['sabit_brut']),
                            min_value=0.0, step=500.0, key=f's_{rid}')
                        yeni_prim  = fc2.number_input(
                            "Satış Primi (₺)", value=float(satir['satis_primi']),
                            min_value=0.0, step=500.0, key=f'p_{rid}')
                        yeni_net   = fc3.number_input(
                            "Net (₺)", value=float(satir['net']),
                            min_value=0.0, step=500.0, key=f'n_{rid}')
                        toplam_preview = yeni_sabit + yeni_prim
                        st.caption(f"Toplam Brüt: **{tl(toplam_preview)}** "
                                   f"| Kesinti (tahmini): **{tl(toplam_preview - yeni_net)}**")
                        bf1, bf2 = st.columns(2)
                        kaydet = bf1.form_submit_button("💾 Kaydet", use_container_width=True)
                        iptal  = bf2.form_submit_button("❌ İptal",  use_container_width=True)
                    if kaydet:
                        if bm.bordro_guncelle(rid, yeni_sabit, yeni_prim, yeni_net):
                            st.success(f"{satir['ay']} güncellendi!")
                            st.session_state[duz_key] = None
                            st.rerun()
                        else:
                            st.error("Güncelleme başarısız!")
                    if iptal:
                        st.session_state[duz_key] = None
                        st.rerun()
                else:
                    # ── Normal satır görünümü ────────────────────────────
                    cols = st.columns([1.2, 1.8, 1.8, 1.8, 1.8, 1.8, 1, 1])
                    cols[0].write(satir['ay'])
                    cols[1].write(tl(satir['sabit_brut']))
                    cols[2].write(tl(satir['satis_primi']))
                    cols[3].write(tl(satir['brut']))
                    cols[4].write(tl(satir['net']))
                    cols[5].write(tl(kesinti))
                    if cols[6].button("✏️", key=f'duz_{rid}', help="Düzenle"):
                        st.session_state[duz_key] = rid
                        st.rerun()
                    if cols[7].button("🗑️", key=f'sil_{rid}', help="Sil"):
                        if bm.bordro_sil(rid):
                            st.success(f"{satir['ay']} silindi!")
                            st.rerun()

            # ── Grafik ───────────────────────────────────────────────────
            st.divider()
            ay_labels = df_yil['ay'].tolist()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=ay_labels, y=df_yil['sabit_brut'],
                                  name='Sabit Brüt', marker_color='#636EFA'))
            fig.add_trace(go.Bar(x=ay_labels, y=df_yil['satis_primi'],
                                  name='Satış Primi', marker_color='#FFA15A'))
            fig.add_trace(go.Bar(x=ay_labels, y=df_yil['net'],
                                  name='Net', marker_color='#00CC96'))
            fig.update_layout(title=f'{secili_yil} — Aylık Brüt Dağılımı & Net',
                               barmode='stack', xaxis_title='Ay', yaxis_title='₺')
            st.plotly_chart(fig, use_container_width=True)

            # Tüm yıllar özet
            st.divider()
            st.subheader("📋 Tüm Yıllar Özeti")
            ozet_rows = []
            for y in sorted(yillar):
                dy = df[df['yil'] == y]
                dy_prim = dy['satis_primi'].fillna(0)
                ozet_rows.append({
                    'Yıl': y,
                    'Kayıt':           len(dy),
                    'Ort. Brüt':       dy['brut'].mean(),
                    'Ort. Net':        dy['net'].mean(),
                    'Toplam Brüt':     dy['brut'].sum(),
                    'Toplam Prim':     dy_prim.sum(),
                    'Toplam Kesinti':  (dy['brut'] - dy['net']).sum()
                })
            df_ozet = pd.DataFrame(ozet_rows)
            for col in ['Ort. Brüt', 'Ort. Net', 'Toplam Brüt', 'Toplam Prim', 'Toplam Kesinti']:
                df_ozet[col] = df_ozet[col].apply(tl)
            st.dataframe(df_ozet, use_container_width=True, hide_index=True)

    # ── TAB 3: MAAŞ ZAMMI ANALİZİ ────────────────────────────────────────
    with tab3:
        bordrolar = bm.bordrolari_getir()
        if not bordrolar:
            st.info("Henüz bordro kaydı yok.")
        else:
            df = pd.DataFrame(bordrolar)
            df['yil']  = df['ay'].str[:4].astype(int)
            df['ay_no'] = df['ay'].str[5:7].astype(int)

            st.info("📌 Her yılın **Şubat** bordrosu baz alınır. Şubat yoksa yılın ilk ayı kullanılır.")

            # Her yıl için temsil bordrosu: önce Şubat, yoksa en küçük ay
            baz_rows = []
            for yil, grp in df.groupby('yil'):
                sub = grp[grp['ay_no'] == 2]
                if sub.empty:
                    sub = grp.sort_values('ay_no').head(1)
                row = sub.sort_values('ay_no').iloc[0]
                baz_rows.append({
                    'yil': yil,
                    'ay':  row['ay'],
                    'brut': row['brut'],
                    'net':  row['net'],
                    'sgk':  row['sgk_kesinti'],
                    'gv':   row['gelir_vergisi'],
                    'dv':   row['damga_vergisi'],
                })
            df_baz = pd.DataFrame(baz_rows).sort_values('yil').reset_index(drop=True)

            # Yıllık zam hesapla
            df_baz['brut_zam_%']  = df_baz['brut'].pct_change() * 100
            df_baz['net_zam_%']   = df_baz['net'].pct_change()  * 100
            df_baz['kesinti_%']   = (df_baz['sgk'] + df_baz['gv'] + df_baz['dv']) / df_baz['brut'] * 100

            # Kart gösterimi
            for i, row in df_baz.iterrows():
                onceki = df_baz.iloc[i - 1] if i > 0 else None
                with st.expander(
                    f"{'📅' if row['ay'].endswith('-02') else '📌'} "
                    f"{row['yil']} — Baz: {row['ay']} | "
                    f"Brüt: {tl(row['brut'])} | Net: {tl(row['net'])}", expanded=(i == len(df_baz)-1)
                ):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Brüt Maaş", tl(row['brut']),
                              delta=f"%{row['brut_zam_%']:.1f}" if onceki is not None else None)
                    c2.metric("Net Maaş",  tl(row['net']),
                              delta=f"%{row['net_zam_%']:.1f}" if onceki is not None else None)
                    c3.metric("Toplam Kesinti",
                              tl(row['sgk'] + row['gv'] + row['dv']),
                              delta=f"%{row['kesinti_%']:.1f} oran" if onceki is not None else None,
                              delta_color="inverse")
                    c4.metric("Vergi Dilimi", _vergi_dilimi(row['brut']))

            st.divider()
            # Karşılaştırma grafiği
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(
                    x=df_baz['yil'].astype(str), y=df_baz['brut'],
                    mode='lines+markers+text', name='Brüt',
                    text=df_baz['brut'].apply(tl), textposition='top center',
                    line=dict(color='#636EFA', width=3)))
                fig1.add_trace(go.Scatter(
                    x=df_baz['yil'].astype(str), y=df_baz['net'],
                    mode='lines+markers+text', name='Net',
                    text=df_baz['net'].apply(tl), textposition='bottom center',
                    line=dict(color='#00CC96', width=3)))
                fig1.update_layout(title='Yıllık Brüt / Net Trend (Şubat Baz)',
                                   xaxis_title='Yıl', yaxis_title='₺')
                st.plotly_chart(fig1, use_container_width=True)

            with col_g2:
                df_zam = df_baz.dropna(subset=['brut_zam_%'])
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    x=df_zam['yil'].astype(str), y=df_zam['brut_zam_%'].round(1),
                    name='Brüt Zam %', marker_color='#636EFA',
                    text=df_zam['brut_zam_%'].round(1).astype(str) + '%',
                    textposition='outside'))
                fig2.add_trace(go.Bar(
                    x=df_zam['yil'].astype(str), y=df_zam['net_zam_%'].round(1),
                    name='Net Zam %', marker_color='#00CC96',
                    text=df_zam['net_zam_%'].round(1).astype(str) + '%',
                    textposition='outside'))
                fig2.update_layout(title='Yıllık Zam Oranları (%)',
                                   barmode='group', xaxis_title='Yıl', yaxis_title='%')
                st.plotly_chart(fig2, use_container_width=True)

    # ── TAB 4: VERGİ DİLİMİ KARŞILAŞTIRMASI ─────────────────────────────
    with tab4:
        bordrolar = bm.bordrolari_getir()
        if not bordrolar:
            st.info("Henüz bordro kaydı yok.")
        else:
            df = pd.DataFrame(bordrolar)
            df['yil']   = df['ay'].str[:4].astype(int)
            df['ay_no'] = df['ay'].str[5:7].astype(int)

            # Her yıl için Şubat/ilk ay baz
            dilim_rows = []
            for yil, grp in df.groupby('yil'):
                sub = grp[grp['ay_no'] == 2]
                if sub.empty:
                    sub = grp.sort_values('ay_no').head(1)
                row = sub.iloc[0]
                kesinti = row['sgk_kesinti'] + row['gelir_vergisi'] + row['damga_vergisi']
                efektif_oran = kesinti / row['brut'] * 100
                dilim_rows.append({
                    'Yıl':              str(yil),
                    'Baz Ay':           row['ay'],
                    'Brüt':             row['brut'],
                    'SGK Kesintisi':    row['sgk_kesinti'],
                    'Gelir Vergisi':    row['gelir_vergisi'],
                    'Damga Vergisi':    row['damga_vergisi'],
                    'Toplam Kesinti':   kesinti,
                    'Efektif Oran %':   round(efektif_oran, 2),
                    'Vergi Dilimi':     _vergi_dilimi(row['brut']),
                })
            df_dilim = pd.DataFrame(dilim_rows).sort_values('Yıl').reset_index(drop=True)

            # Tablo
            df_tablo = df_dilim.copy()
            for col in ['Brüt', 'SGK Kesintisi', 'Gelir Vergisi', 'Damga Vergisi', 'Toplam Kesinti']:
                df_tablo[col] = df_tablo[col].apply(tl)
            st.dataframe(df_tablo, use_container_width=True, hide_index=True)

            st.divider()

            col_v1, col_v2 = st.columns(2)
            with col_v1:
                # Kesinti bileşenleri yıllara göre stacked bar
                fig3 = go.Figure()
                fig3.add_trace(go.Bar(
                    x=df_dilim['Yıl'], y=df_dilim['SGK Kesintisi'],
                    name='SGK (%14)', marker_color='#EF553B'))
                fig3.add_trace(go.Bar(
                    x=df_dilim['Yıl'], y=df_dilim['Gelir Vergisi'],
                    name='Gelir Vergisi', marker_color='#FF7F0E'))
                fig3.add_trace(go.Bar(
                    x=df_dilim['Yıl'], y=df_dilim['Damga Vergisi'],
                    name='Damga Vergisi', marker_color='#9467BD'))
                fig3.update_layout(
                    title='Yıllık Kesinti Bileşenleri (Şubat Baz)',
                    barmode='stack', xaxis_title='Yıl', yaxis_title='₺')
                st.plotly_chart(fig3, use_container_width=True)

            with col_v2:
                # Efektif vergi oranı trend
                fig4 = go.Figure()
                fig4.add_trace(go.Scatter(
                    x=df_dilim['Yıl'], y=df_dilim['Efektif Oran %'],
                    mode='lines+markers+text',
                    text=df_dilim['Efektif Oran %'].astype(str) + '%',
                    textposition='top center',
                    line=dict(color='#EF553B', width=3),
                    fill='tozeroy', fillcolor='rgba(239,85,59,0.1)',
                    name='Efektif Kesinti Oranı'))
                fig4.update_layout(
                    title='Toplam Efektif Kesinti Oranı Trendi (%)',
                    xaxis_title='Yıl', yaxis_title='%',
                    yaxis=dict(range=[0, 60]))
                st.plotly_chart(fig4, use_container_width=True)

            # Dilim değişim özeti
            st.subheader("🔄 Vergi Dilimi Değişim Özeti")
            prev_dilim = None
            for _, row in df_dilim.iterrows():
                icon = "🔺" if prev_dilim and row['Vergi Dilimi'] != prev_dilim else ("✅" if prev_dilim else "📌")
                st.write(f"{icon} **{row['Yıl']}** — {row['Vergi Dilimi']} | "
                         f"Brüt: {tl(row['Brüt'])}" if isinstance(row['Brüt'], float)
                         else f"{icon} **{row['Yıl']}** — {row['Vergi Dilimi']} | Brüt: {row['Brüt']}")
                prev_dilim = row['Vergi Dilimi']

    # ── TAB 5: SATIŞ PRİMİ ANALİZİ ──────────────────────────────────────
    with tab5:
        bordrolar = bm.bordrolari_getir()
        if not bordrolar:
            st.info("Henüz bordro kaydı yok.")
        else:
            df = pd.DataFrame(bordrolar)
            df['satis_primi'] = df['satis_primi'].fillna(0)
            df['yil'] = df['ay'].str[:4].astype(int)
            df['ay_no'] = df['ay'].str[5:7].astype(int)
            df['sabit_brut'] = df['brut'] - df['satis_primi']

            # ── Yıllık özet ────────────────────────────────────────────
            st.subheader("📅 Yıllık Prim Özeti")
            yil_ozet = []
            for yil, grp in df.groupby('yil'):
                toplam_brut   = grp['brut'].sum()
                toplam_prim   = grp['satis_primi'].sum()
                sabit_toplam  = grp['sabit_brut'].sum()
                prim_oran     = toplam_prim / toplam_brut * 100 if toplam_brut > 0 else 0
                primli_ay     = (grp['satis_primi'] > 0).sum()
                yil_ozet.append({
                    'Yıl':            str(yil),
                    'Toplam Brüt':    toplam_brut,
                    'Sabit Maaş Top.': sabit_toplam,
                    'Toplam Prim':    toplam_prim,
                    'Prim Oranı %':   round(prim_oran, 2),
                    'Primli Ay':      int(primli_ay),
                    'Ort. Aylık Prim': toplam_prim / len(grp),
                })
            df_yiloz = pd.DataFrame(yil_ozet)
            df_yiloz_show = df_yiloz.copy()
            for c in ['Toplam Brüt', 'Sabit Maaş Top.', 'Toplam Prim', 'Ort. Aylık Prim']:
                df_yiloz_show[c] = df_yiloz_show[c].apply(tl)
            st.dataframe(df_yiloz_show, use_container_width=True, hide_index=True)

            st.divider()

            # ── Grafikler ──────────────────────────────────────────────
            col_p1, col_p2 = st.columns(2)

            with col_p1:
                # Yıllık sabit vs prim stacked bar
                fig_p1 = go.Figure()
                fig_p1.add_trace(go.Bar(
                    x=df_yiloz['Yıl'], y=df_yiloz['Sabit Maaş Top.'],
                    name='Sabit Brüt', marker_color='#636EFA'))
                fig_p1.add_trace(go.Bar(
                    x=df_yiloz['Yıl'], y=df_yiloz['Toplam Prim'],
                    name='Satış Primi', marker_color='#FFA15A'))
                fig_p1.update_layout(
                    title='Yıllık Sabit Maaş vs Satış Primi',
                    barmode='stack', xaxis_title='Yıl', yaxis_title='₺')
                st.plotly_chart(fig_p1, use_container_width=True)

            with col_p2:
                # Prim oranı % trend
                fig_p2 = go.Figure()
                fig_p2.add_trace(go.Bar(
                    x=df_yiloz['Yıl'], y=df_yiloz['Prim Oranı %'],
                    marker_color='#FFA15A', name='Prim Oranı',
                    text=df_yiloz['Prim Oranı %'].astype(str) + '%',
                    textposition='outside'))
                fig_p2.update_layout(
                    title='Yıllık Prim / Brüt Oranı (%)',
                    xaxis_title='Yıl', yaxis_title='%')
                st.plotly_chart(fig_p2, use_container_width=True)

            # ── Aylık prim detayı ──────────────────────────────────────
            st.subheader("🗓️ Aylık Prim Detayı")
            secili_yil_prim = st.selectbox("Yıl Seç", sorted(df['yil'].unique(),
                                            reverse=True), key='prim_yil')
            df_ay = df[df['yil'] == secili_yil_prim].sort_values('ay')
            prim_var = df_ay[df_ay['satis_primi'] > 0]

            if prim_var.empty:
                st.info(f"{secili_yil_prim} yılı için kayıtlı satış primi bulunamadı.")
            else:
                fig_p3 = go.Figure()
                fig_p3.add_trace(go.Bar(
                    x=df_ay['ay'], y=df_ay['sabit_brut'],
                    name='Sabit Brüt', marker_color='#636EFA'))
                fig_p3.add_trace(go.Bar(
                    x=df_ay['ay'], y=df_ay['satis_primi'],
                    name='Satış Primi', marker_color='#FFA15A'))
                fig_p3.update_layout(
                    title=f'{secili_yil_prim} — Aylık Sabit Brüt + Satış Primi',
                    barmode='stack', xaxis_title='Ay', yaxis_title='₺')
                st.plotly_chart(fig_p3, use_container_width=True)

                # Prim olan aylara özet tablo
                df_prim_show = prim_var[['ay', 'sabit_brut', 'satis_primi', 'brut']].copy()
                df_prim_show['prim_oran_%'] = (
                    df_prim_show['satis_primi'] / df_prim_show['brut'] * 100).round(1)
                df_prim_show.columns = ['Ay', 'Sabit Brüt', 'Satış Primi',
                                         'Toplam Brüt', 'Primdeki Pay %']
                for c in ['Sabit Brüt', 'Satış Primi', 'Toplam Brüt']:
                    df_prim_show[c] = df_prim_show[c].apply(tl)
                st.dataframe(df_prim_show, use_container_width=True, hide_index=True)

    # ── TAB 6: İSTATİSTİKLER ─────────────────────────────────────────────
    with tab6:
        stats = bm.istatistikler()
        if stats['toplam'] == 0:
            st.info("İstatistik için önce bordro ekleyin.")
        else:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Toplam Bordro",  stats['toplam'])
            c2.metric("Ort. Brüt",      tl(stats['ortalama_brut']))
            c3.metric("Ort. Net",       tl(stats['ortalama_net']))
            c4.metric("Toplam Kesinti", tl(stats['toplam_kesinti']))
            c5.metric("Toplam Prim",    tl(stats['toplam_satis_primi']))


def sayfa_asgari_ucret():
    st.header("📈 Asgari Ücret Analizi (2020–2026)")

    df = pd.DataFrame(AsgariUcretAnaliz.ASGARI_UCRETLER)
    df['Dönem'] = df['yil'].astype(str) + "-" + df['donem'].astype(str) + ".D"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Dönem'], y=df['brut'],
                              mode='lines+markers', name='Brüt',
                              line=dict(color='#636EFA', width=3)))
    fig.add_trace(go.Scatter(x=df['Dönem'], y=df['net'],
                              mode='lines+markers', name='Net',
                              line=dict(color='#00CC96', width=3)))
    fig.update_layout(title='Asgari Ücret Tarihsel Trend',
                      xaxis_title='Dönem', yaxis_title='₺', hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)

    artis_df = df[df['artis'] > 0].copy()
    fig2 = px.bar(artis_df, x='Dönem', y='artis',
                  title='Dönemsel Artış Oranları (%)',
                  color='artis', color_continuous_scale='RdYlGn', text='artis')
    fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig2, use_container_width=True)

    st.info(f"📌 **2020'den bu yana toplam artış: %{AsgariUcretAnaliz.toplam_artis()}**")

    st.divider()
    st.subheader("Maaş Katsayısı Analizi")
    maas = st.number_input("Brüt Maaşınız (₺)", min_value=0.0,
                            value=50000.0, step=1000.0)
    if maas > 0:
        analiz = AsgariUcretAnaliz.katsayi_hesapla(maas)
        col1, col2 = st.columns(2)
        col1.metric("Asgari Ücret Katsayısı", f"{analiz['katsayi']}x")
        col2.metric("Asgari Ücretten Fark", tl(analiz['fark']))


def sayfa_butce():
    st.header("💳 50-30-20 Bütçe Planlaması")
    st.info("**50-30-20 Kuralı:** %50 İhtiyaçlar · %30 İstekler · %20 Tasarruf")

    net_gelir = st.number_input("Aylık Net Geliriniz (₺)", min_value=0.0,
                                 value=28075.0, step=500.0)

    if net_gelir > 0:
        butce = ButcePlanlama.butce_hesapla(net_gelir)

        col1, col2, col3 = st.columns(3)
        col1.metric("🏠 İhtiyaçlar (%50)", tl(butce['ihtiyaclar']['tutar']))
        col2.metric("🎉 İstekler (%30)",    tl(butce['istekler']['tutar']))
        col3.metric("💰 Tasarruf (%20)",    tl(butce['tasarruf']['tutar']))

        fig = px.pie(
            names=['İhtiyaçlar', 'İstekler', 'Tasarruf'],
            values=[butce['ihtiyaclar']['tutar'],
                    butce['istekler']['tutar'],
                    butce['tasarruf']['tutar']],
            title="Bütçe Dağılımı",
            color_discrete_sequence=['#EF553B', '#636EFA', '#00CC96']
        )
        st.plotly_chart(fig, use_container_width=True)

        col4, col5 = st.columns(2)
        with col4:
            st.subheader("🏠 İhtiyaçlar")
            for k in butce['ihtiyaclar']['kategoriler']:
                st.write(f"• {k}")
        with col5:
            st.subheader("🎉 İstekler")
            for k in butce['istekler']['kategoriler']:
                st.write(f"• {k}")

        st.divider()
        st.success(
            f"✅ 12 ayda biriktireceğiniz: "
            f"**{tl(butce['tasarruf']['yillik_birikim'])}**"
        )


def sayfa_zam():
    st.header("📊 Maaş Zammı Senaryoları")

    with st.form("zam_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            mevcut = st.number_input("Mevcut Brüt Maaş (₺)", min_value=0.0,
                                      value=50000.0, step=1000.0)
        with col2:
            zam = st.number_input("Zam Oranı (%)", min_value=0.0,
                                   value=30.0, step=0.5)
        with col3:
            enflasyon = st.number_input("Enflasyon Oranı (%)", min_value=0.0,
                                         value=45.0, step=0.5)
        hesapla = st.form_submit_button("📈 Hesapla", use_container_width=True)

    if hesapla:
        sonuc = MaasZamHesaplayici.zam_analizi(mevcut, zam, enflasyon)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Öncesi")
            st.metric("Brüt", tl(sonuc['mevcut_brut']))
            st.metric("Net (~)", tl(sonuc['mevcut_net']))
        with col2:
            st.subheader("Sonrası")
            st.metric("Brüt", tl(sonuc['yeni_brut']),
                      delta=f"+{tl(sonuc['brut_artis'])}")
            st.metric("Net (~)", tl(sonuc['yeni_net']),
                      delta=f"+{tl(sonuc['net_artis'])}")

        st.divider()
        reel = sonuc['reel_zam']
        if sonuc['durum'] == 'kazanc':
            st.success(f"✅ Reel Zam: **%{reel:.2f}** — Aldığınız zam enflasyonun üzerinde!")
        else:
            st.warning(f"⚠️ Reel Zam: **%{reel:.2f}** — Aldığınız zam enflasyonun altında!")

        col3, col4 = st.columns(2)
        col3.metric("Yıllık Net Kazanç",   tl(sonuc['yillik_net_kazanc']))
        col4.metric("5 Yıllık Net Kazanç", tl(sonuc['besyillik_kazanc']))

        fig = go.Figure(go.Bar(
            x=['Zam Oranı', 'Enflasyon', 'Reel Zam'],
            y=[zam, enflasyon, reel],
            marker_color=['#636EFA', '#EF553B',
                          '#00CC96' if reel > 0 else '#EF553B'],
            text=[f"%{v:.1f}" for v in [zam, enflasyon, reel]],
            textposition='outside'
        ))
        fig.update_layout(title='Zam vs Enflasyon vs Reel Zam', yaxis_title='%')
        st.plotly_chart(fig, use_container_width=True)


def sayfa_yatirim():
    st.header("🎯 Yatırım Tavsiyeleri")

    with st.form("yatirim_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            tasarruf = st.number_input("Aylık Tasarruf (₺)", min_value=0.0,
                                        value=5000.0, step=500.0)
        with col2:
            vade = st.number_input("Yatırım Süresi (Ay)", min_value=1,
                                    value=36, step=1)
        with col3:
            risk_map = {
                "Düşük Risk (Güvenli)":  "dusuk",
                "Orta Risk (Dengeli)":   "orta",
                "Yüksek Risk (Agresif)": "yuksek",
            }
            risk_label = st.selectbox("Risk Profili", list(risk_map.keys()), index=1)
        hesapla = st.form_submit_button("💼 Hesapla", use_container_width=True)

    if hesapla:
        risk = risk_map[risk_label]
        sonuc = YatirimHesaplayici.yatirim_hesapla(tasarruf, int(vade), risk)

        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Birikim",   tl(sonuc['toplam_birikim']))
        col2.metric("Beklenen Getiri", f"+{tl(sonuc['beklenen_getiri'])}")
        col3.metric("💰 Toplam Değer", tl(sonuc['toplam_deger']))

        col4, col5 = st.columns(2)
        with col4:
            df_dag = pd.DataFrame(sonuc['portfoy_dagilimi'])
            fig = px.pie(df_dag, names='ad', values='oran',
                         title=f"{risk_label} — Portföy Dağılımı",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, use_container_width=True)

        with col5:
            df_proj = pd.DataFrame(sonuc['uzun_vade_projeksiyon'])
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=df_proj['yil'].astype(str) + " Yıl",
                y=df_proj['birikim'], name='Birikim', marker_color='#636EFA'))
            fig2.add_trace(go.Bar(
                x=df_proj['yil'].astype(str) + " Yıl",
                y=df_proj['getiri'], name='Getiri', marker_color='#00CC96'))
            fig2.update_layout(title='Uzun Vadeli Projeksiyon', barmode='stack',
                               xaxis_title='Süre', yaxis_title='₺')
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📊 Önerilen Dağılım Tablosu")
        df_tablo = df_dag.copy()
        df_tablo['miktar'] = df_tablo['miktar'].apply(tl)
        df_tablo.columns = ['Yatırım Aracı', 'Oran (%)', 'Tutar', 'Yıllık Getiri (%)']
        st.dataframe(df_tablo, use_container_width=True)


# ─────────────────────────────────────────────
#  ANA UYGULAMA
# ─────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="MaaşPro – Bordro & Finans",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.sidebar.title("💼 MaaşPro")
    st.sidebar.caption("Bordro & Finans Yönetim Sistemi")
    st.sidebar.divider()

    menu = {
        "💰 Tazminat Hesaplama":    sayfa_tazminat,
        "📊 Bordro Arşivi":         sayfa_bordro,
        "📈 Asgari Ücret Analizi":  sayfa_asgari_ucret,
        "💳 50-30-20 Bütçe Planı":  sayfa_butce,
        "📊 Maaş Zammı Senaryoları": sayfa_zam,
        "🎯 Yatırım Tavsiyeleri":   sayfa_yatirim,
    }

    secim = st.sidebar.radio("Menü", list(menu.keys()))
    st.sidebar.divider()
    st.sidebar.caption("by Göksel · 2026")

    menu[secim]()


if __name__ == "__main__":
    main()
