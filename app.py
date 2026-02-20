#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MaaşPro - Bordro & Finans Yönetim Sistemi
Profesyonel bordro hesaplama, tazminat analizi ve yatırım planlama uygulaması
"""

from datetime import datetime, date
from typing import Dict, List, Tuple
import sqlite3

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ─────────────────────────────────────────────
#  İŞ MANTIĞI SINIFLARI
# ─────────────────────────────────────────────

class BordroYonetim:
    """Bordro kayıtlarını yöneten sınıf"""

    def __init__(self, db_path: str = "maaspro.db"):
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
                eklenme_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def bordro_ekle(self, ay: str, brut: float, net: float) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            sgk = brut * 0.14
            damga = brut * 0.00759
            gelir_vergisi = brut - net - sgk - damga
            cursor.execute('''
                INSERT INTO bordrolar (ay, brut, net, sgk_kesinti, gelir_vergisi, damga_vergisi)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ay, brut, net, sgk, gelir_vergisi, damga))
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
                'damga_vergisi': row[6], 'eklenme_tarihi': row[7]
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

    def istatistikler(self) -> Dict:
        bordrolar = self.bordrolari_getir()
        if not bordrolar:
            return {'toplam': 0, 'ortalama_brut': 0, 'ortalama_net': 0,
                    'toplam_kazanc': 0, 'toplam_kesinti': 0}
        toplam_brut = sum(b['brut'] for b in bordrolar)
        toplam_net = sum(b['net'] for b in bordrolar)
        return {
            'toplam': len(bordrolar),
            'ortalama_brut': toplam_brut / len(bordrolar),
            'ortalama_net': toplam_net / len(bordrolar),
            'toplam_kazanc': toplam_brut,
            'toplam_kesinti': toplam_brut - toplam_net
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
    def yillik_izin_ucreti_hesapla(brut_maas: float, kalan_izin: int) -> float:
        return (brut_maas / 30) * kalan_izin

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
                      cikis_sebebi: str, kalan_izin: int = 0) -> Dict:
        yil, gun = cls.calisma_suresi_hesapla(baslama, bitis)
        calisma_yil_desimal = yil + (gun / 365)
        kidem = cls.kidem_tazminati_hesapla(brut_maas, yil, gun, cikis_sebebi)
        ihbar = cls.ihbar_tazminati_hesapla(brut_maas, calisma_yil_desimal, cikis_sebebi)
        yillik_izin = cls.yillik_izin_ucreti_hesapla(brut_maas, kalan_izin)
        toplam_brut = kidem + ihbar + yillik_izin
        if toplam_brut > 0:
            kesintiler = cls.vergi_kesintileri_hesapla(toplam_brut)
        else:
            kesintiler = {'sgk': 0, 'gelir_vergisi': 0, 'damga': 0, 'toplam_kesinti': 0}
        net_tutar = toplam_brut - kesintiler['toplam_kesinti']
        return {
            'calisma_suresi': {'yil': yil, 'gun': gun, 'toplam_yil': calisma_yil_desimal},
            'tazminatlar': {'kidem': kidem, 'ihbar': ihbar,
                            'yillik_izin': yillik_izin, 'toplam_brut': toplam_brut},
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

        cikis_secenekleri = {
            "İstifa (Kendi İsteğimle)":         "istifa",
            "İşveren Feshi (Haklı Sebep Yok)":  "isverenFeshi",
            "İşveren Feshi (Haklı Sebep)":       "hakliSebep",
            "Emeklilik":                         "emeklilik",
            "Ölüm":                              "olum",
            "Askerlik":                          "askerlik",
        }
        cikis_secim = st.selectbox("İşten Çıkış Sebebi", list(cikis_secenekleri.keys()))
        hesapla = st.form_submit_button("🔍 Hesapla", use_container_width=True)

    if hesapla:
        if bitis <= baslama:
            st.error("Çıkış tarihi, başlama tarihinden sonra olmalıdır!")
            return
        cikis_sebebi = cikis_secenekleri[cikis_secim]
        sonuc = TazminatHesaplayici.tam_hesaplama(
            brut, str(baslama), str(bitis), cikis_sebebi, int(kalan_izin)
        )
        cs = sonuc['calisma_suresi']
        t  = sonuc['tazminatlar']
        k  = sonuc['kesintiler']

        st.success(f"⏱️  Çalışma Süresi: **{cs['yil']} yıl {cs['gun']} gün**")

        col1, col2, col3 = st.columns(3)
        col1.metric("Kıdem Tazminatı",   tl(t['kidem']) if t['kidem'] > 0 else "Hak Yok")
        col2.metric("İhbar Tazminatı",   tl(t['ihbar']) if t['ihbar'] > 0 else "Hak Yok")
        col3.metric("Yıllık İzin Ücreti", tl(t['yillik_izin']))

        st.divider()
        col4, col5, col6 = st.columns(3)
        col4.metric("Brüt Toplam",   tl(t['toplam_brut']))
        col5.metric("Toplam Kesinti", f"-{tl(k['toplam_kesinti'])}")
        col6.metric("✅ NET ÖDEME",   tl(sonuc['net_tutar']))

        if t['toplam_brut'] > 0:
            fig = px.pie(
                names=['SGK Kesintisi', 'Gelir Vergisi', 'Damga Vergisi', 'Net Tutar'],
                values=[k['sgk'], k['gelir_vergisi'], k['damga'], sonuc['net_tutar']],
                title="Tazminat Dağılımı",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig, use_container_width=True)


def sayfa_bordro():
    st.header("📊 Bordro Arşivi")
    bm = BordroYonetim()

    tab1, tab2, tab3 = st.tabs(["➕ Bordro Ekle", "📋 Bordrolar", "📈 İstatistikler"])

    with tab1:
        with st.form("bordro_ekle"):
            col1, col2, col3 = st.columns(3)
            with col1:
                ay = st.text_input("Ay (YYYY-MM)", placeholder="2026-01")
            with col2:
                brut = st.number_input("Brüt Maaş (₺)", min_value=0.0,
                                        value=33030.0, step=500.0)
            with col3:
                net = st.number_input("Net Maaş (₺)", min_value=0.0,
                                       value=28075.0, step=500.0)
            ekle = st.form_submit_button("✅ Bordroyu Kaydet", use_container_width=True)
        if ekle:
            if bm.bordro_ekle(ay, brut, net):
                st.success("Bordro başarıyla eklendi!")
                st.rerun()
            else:
                st.error("Bordro eklenemedi! Ay formatını kontrol edin (YYYY-MM).")

    with tab2:
        bordrolar = bm.bordrolari_getir()
        if not bordrolar:
            st.info("Henüz bordro kaydı yok.")
        else:
            df = pd.DataFrame(bordrolar)
            df_show = df[['id', 'ay', 'brut', 'net',
                          'sgk_kesinti', 'gelir_vergisi', 'damga_vergisi']].copy()
            df_show.columns = ['ID', 'Ay', 'Brüt (₺)', 'Net (₺)',
                                'SGK (₺)', 'Gelir V. (₺)', 'Damga V. (₺)']
            st.dataframe(df_show, use_container_width=True)

            st.divider()
            sil_id = st.number_input("Silmek istediğiniz Bordro ID:", min_value=1, step=1)
            if st.button("🗑️ Seçili Bordroyu Sil"):
                if bm.bordro_sil(int(sil_id)):
                    st.success("Bordro silindi!")
                    st.rerun()
                else:
                    st.error("Bordro silinemedi!")

            fig = go.Figure()
            fig.add_trace(go.Bar(x=df['ay'], y=df['brut'],
                                  name='Brüt', marker_color='#636EFA'))
            fig.add_trace(go.Bar(x=df['ay'], y=df['net'],
                                  name='Net', marker_color='#00CC96'))
            fig.update_layout(title='Aylık Brüt / Net Maaş', barmode='group',
                               xaxis_title='Ay', yaxis_title='₺')
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        stats = bm.istatistikler()
        if stats['toplam'] == 0:
            st.info("İstatistik için önce bordro ekleyin.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Toplam Bordro",  stats['toplam'])
            c2.metric("Ort. Brüt",      tl(stats['ortalama_brut']))
            c3.metric("Ort. Net",       tl(stats['ortalama_net']))
            c4.metric("Toplam Kesinti", tl(stats['toplam_kesinti']))


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
