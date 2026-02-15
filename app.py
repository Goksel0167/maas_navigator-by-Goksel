#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MaaşPro - Bordro & Finans Yönetim Sistemi
Profesyonel bordro hesaplama, tazminat analizi ve yatırım planlama uygulaması
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sqlite3


class BordroYonetim:
    """Bordro kayıtlarını yöneten sınıf"""
    
    def __init__(self, db_path: str = "maaspro.db"):
        self.db_path = db_path
        self.baglanti_olustur()
    
    def baglanti_olustur(self):
        """Veritabanı bağlantısı ve tabloları oluştur"""
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
        """Yeni bordro kaydı ekle"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Kesintileri hesapla
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
        except Exception as e:
            print(f"Hata: {e}")
            return False
    
    def bordrolari_getir(self) -> List[Dict]:
        """Tüm bordroları getir"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM bordrolar ORDER BY ay DESC')
        rows = cursor.fetchall()
        
        bordrolar = []
        for row in rows:
            bordrolar.append({
                'id': row[0],
                'ay': row[1],
                'brut': row[2],
                'net': row[3],
                'sgk_kesinti': row[4],
                'gelir_vergisi': row[5],
                'damga_vergisi': row[6],
                'eklenme_tarihi': row[7]
            })
        
        conn.close()
        return bordrolar
    
    def bordro_sil(self, bordro_id: int) -> bool:
        """Bordro kaydını sil"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM bordrolar WHERE id = ?', (bordro_id,))
            conn.commit()
            conn.close()
            return True
        except:
            return False
    
    def istatistikler(self) -> Dict:
        """Bordro istatistiklerini hesapla"""
        bordrolar = self.bordrolari_getir()
        
        if not bordrolar:
            return {
                'toplam': 0,
                'ortalama_brut': 0,
                'ortalama_net': 0,
                'toplam_kazanc': 0,
                'toplam_kesinti': 0
            }
        
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
    """Tazminat hesaplama sınıfı"""
    
    # 2026 Ocak-Haziran kıdem tazminatı tavanı
    KIDEM_TAVAN = 64948.77
    
    @staticmethod
    def calisma_suresi_hesapla(baslama: str, bitis: str) -> Tuple[int, int]:
        """Çalışma süresini yıl ve gün olarak hesapla"""
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
        """Kıdem tazminatı hesapla"""
        # Kıdem hakkı kontrolü
        kidem_hakki = cikis_sebebi in ['isverenFeshi', 'emeklilik', 'olum', 'askerlik']
        
        if not kidem_hakki or calisma_yil < 1:
            return 0.0
        
        # Tavan kontrolü
        brut_yillik = min(brut_maas, TazminatHesaplayici.KIDEM_TAVAN)
        
        # Tam yıllar için tazminat
        kidem = brut_yillik * calisma_yil
        
        # Kalan günler için
        if calisma_gun > 0:
            kidem += (brut_yillik / 365) * calisma_gun
        
        return kidem
    
    @staticmethod
    def ihbar_tazminati_hesapla(brut_maas: float, calisma_yil: float, 
                                 cikis_sebebi: str) -> float:
        """İhbar tazminatı hesapla"""
        if cikis_sebebi != 'isverenFeshi':
            return 0.0
        
        if calisma_yil < 0.5:
            return brut_maas * 2 / 4  # 2 hafta
        elif calisma_yil < 1.5:
            return brut_maas * 4 / 4  # 4 hafta
        elif calisma_yil < 3:
            return brut_maas * 6 / 4  # 6 hafta
        else:
            return brut_maas * 8 / 4  # 8 hafta
    
    @staticmethod
    def yillik_izin_ucreti_hesapla(brut_maas: float, kalan_izin: int) -> float:
        """Yıllık izin ücreti hesapla"""
        gunluk_ucret = brut_maas / 30
        return gunluk_ucret * kalan_izin
    
    @staticmethod
    def vergi_kesintileri_hesapla(toplam_brut: float) -> Dict[str, float]:
        """Vergi ve kesintileri hesapla"""
        sgk_kesinti = toplam_brut * 0.14
        vergi_matrahi = toplam_brut - sgk_kesinti
        
        # Gelir vergisi dilimleri (2025)
        if vergi_matrahi <= 110000:
            gelir_vergisi = vergi_matrahi * 0.15
        elif vergi_matrahi <= 230000:
            gelir_vergisi = 110000 * 0.15 + (vergi_matrahi - 110000) * 0.20
        elif vergi_matrahi <= 580000:
            gelir_vergisi = 110000 * 0.15 + 120000 * 0.20 + (vergi_matrahi - 230000) * 0.27
        elif vergi_matrahi <= 3000000:
            gelir_vergisi = 110000 * 0.15 + 120000 * 0.20 + 350000 * 0.27 + (vergi_matrahi - 580000) * 0.35
        else:
            gelir_vergisi = 110000 * 0.15 + 120000 * 0.20 + 350000 * 0.27 + 2420000 * 0.35 + (vergi_matrahi - 3000000) * 0.40
        
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
        """Tüm tazminat hesaplamalarını yap"""
        yil, gun = cls.calisma_suresi_hesapla(baslama, bitis)
        calisma_yil_desimal = yil + (gun / 365)
        
        kidem = cls.kidem_tazminati_hesapla(brut_maas, yil, gun, cikis_sebebi)
        ihbar = cls.ihbar_tazminati_hesapla(brut_maas, calisma_yil_desimal, cikis_sebebi)
        yillik_izin = cls.yillik_izin_ucreti_hesapla(brut_maas, kalan_izin)
        
        toplam_brut = kidem + ihbar + yillik_izin
        kesintiler = cls.vergi_kesintileri_hesapla(toplam_brut)
        net_tutar = toplam_brut - kesintiler['toplam_kesinti']
        
        return {
            'calisma_suresi': {
                'yil': yil,
                'gun': gun,
                'toplam_yil': calisma_yil_desimal
            },
            'tazminatlar': {
                'kidem': kidem,
                'ihbar': ihbar,
                'yillik_izin': yillik_izin,
                'toplam_brut': toplam_brut
            },
            'kesintiler': kesintiler,
            'net_tutar': net_tutar
        }


class AsgariUcretAnaliz:
    """Asgari ücret analizi sınıfı"""
    
    ASGARI_UCRETLER = [
        {'yil': 2020, 'donem': 1, 'brut': 2943.00, 'net': 2324.71, 'artis': 15.0},
        {'yil': 2020, 'donem': 2, 'brut': 2943.00, 'net': 2324.71, 'artis': 0.0},
        {'yil': 2021, 'donem': 1, 'brut': 3577.50, 'net': 2825.90, 'artis': 21.56},
        {'yil': 2021, 'donem': 2, 'brut': 3577.50, 'net': 2825.90, 'artis': 0.0},
        {'yil': 2022, 'donem': 1, 'brut': 4253.40, 'net': 3361.88, 'artis': 18.98},
        {'yil': 2022, 'donem': 2, 'brut': 5500.35, 'net': 4250.45, 'artis': 29.32},
        {'yil': 2023, 'donem': 1, 'brut': 8506.80, 'net': 6402.21, 'artis': 50.63},
        {'yil': 2023, 'donem': 2, 'brut': 11402.32, 'net': 8502.07, 'artis': 34.04},
        {'yil': 2024, 'donem': 1, 'brut': 17002.12, 'net': 12475.11, 'artis': 49.12},
        {'yil': 2024, 'donem': 2, 'brut': 20002.50, 'net': 14738.06, 'artis': 17.65},
        {'yil': 2025, 'donem': 1, 'brut': 26005.50, 'net': 22104.67, 'artis': 30.02},
        {'yil': 2025, 'donem': 2, 'brut': 26005.50, 'net': 22104.67, 'artis': 0.0},
        {'yil': 2026, 'donem': 1, 'brut': 33030.00, 'net': 28075.50, 'artis': 27.0}
    ]
    
    @classmethod
    def katsayi_hesapla(cls, maas: float, yil: int = 2026) -> Dict:
        """Maaşın asgari ücrete oranını hesapla"""
        guncel = [au for au in cls.ASGARI_UCRETLER if au['yil'] == yil][-1]
        
        return {
            'asgari_ucret': guncel,
            'katsayi': round(maas / guncel['brut'], 2),
            'fark': maas - guncel['brut']
        }
    
    @classmethod
    def toplam_artis(cls) -> float:
        """2020'den bugüne toplam artış oranı"""
        ilk = cls.ASGARI_UCRETLER[0]['brut']
        son = cls.ASGARI_UCRETLER[-1]['brut']
        return round(((son / ilk - 1) * 100), 2)


class ButcePlanlama:
    """50-30-20 bütçe planlama sınıfı"""
    
    @staticmethod
    def butce_hesapla(net_gelir: float) -> Dict:
        """50-30-20 kuralına göre bütçe planla"""
        ihtiyaclar = net_gelir * 0.50
        istekler = net_gelir * 0.30
        tasarruf = net_gelir * 0.20
        
        return {
            'net_gelir': net_gelir,
            'ihtiyaclar': {
                'tutar': ihtiyaclar,
                'oran': 50,
                'kategoriler': [
                    'Kira / Konut kredisi',
                    'Faturalar (elektrik, su, doğalgaz)',
                    'Market ve yiyecek',
                    'Ulaşım',
                    'Sigorta ödemeleri'
                ]
            },
            'istekler': {
                'tutar': istekler,
                'oran': 30,
                'kategoriler': [
                    'Eğlence ve hobi',
                    'Dışarıda yemek',
                    'Alışveriş',
                    'Seyahat ve tatil',
                    'Abonelikler'
                ]
            },
            'tasarruf': {
                'tutar': tasarruf,
                'oran': 20,
                'kategoriler': [
                    'Acil durum fonu',
                    'Yatırım (hisse, altın, döviz)',
                    'Emeklilik planı',
                    'Büyük harcamalar'
                ],
                'yillik_birikim': tasarruf * 12
            }
        }


class YatirimHesaplayici:
    """Yatırım ve tasarruf hesaplama sınıfı"""
    
    PORTFOY_STRATEJILERI = {
        'dusuk': [
            {'ad': 'Vadeli TL Mevduat', 'oran': 50, 'yillik_getiri': 2.5},
            {'ad': 'Devlet Tahvili', 'oran': 30, 'yillik_getiri': 2.3},
            {'ad': 'Altın', 'oran': 20, 'yillik_getiri': 1.5}
        ],
        'orta': [
            {'ad': 'Hisse Senedi Fonu', 'oran': 40, 'yillik_getiri': 3.5},
            {'ad': 'Vadeli Mevduat', 'oran': 30, 'yillik_getiri': 2.5},
            {'ad': 'Altın', 'oran': 20, 'yillik_getiri': 1.5},
            {'ad': 'Döviz', 'oran': 10, 'yillik_getiri': 2.0}
        ],
        'yuksek': [
            {'ad': 'Hisse Senedi', 'oran': 50, 'yillik_getiri': 4.5},
            {'ad': 'Kripto Para', 'oran': 20, 'yillik_getiri': 5.0},
            {'ad': 'Hisse Fonu', 'oran': 20, 'yillik_getiri': 3.5},
            {'ad': 'Altın', 'oran': 10, 'yillik_getiri': 1.5}
        ]
    }
    
    @classmethod
    def yatirim_hesapla(cls, aylik_tasarruf: float, vade_ay: int, 
                       risk_profili: str = 'orta') -> Dict:
        """Yatırım planı hesapla"""
        portfoy = cls.PORTFOY_STRATEJILERI.get(risk_profili, cls.PORTFOY_STRATEJILERI['orta'])
        
        toplam_birikim = aylik_tasarruf * vade_ay
        
        # Ortalama getiri hesapla
        ortalama_getiri = sum(y['yillik_getiri'] * y['oran'] / 100 for y in portfoy)
        
        # Bileşik getiri
        yil = vade_ay / 12
        beklenen_getiri = toplam_birikim * (pow(1 + ortalama_getiri / 100, yil) - 1)
        toplam_deger = toplam_birikim + beklenen_getiri
        
        # Dağılım
        dagilim = []
        for yatirim in portfoy:
            miktar = toplam_birikim * yatirim['oran'] / 100
            dagilim.append({
                'ad': yatirim['ad'],
                'oran': yatirim['oran'],
                'miktar': miktar,
                'getiri_orani': yatirim['yillik_getiri']
            })
        
        # Uzun vadeli projeksiyon
        projeksiyon = []
        for yil_sayisi in [1, 2, 3, 5, 10]:
            ay = yil_sayisi * 12
            birikim = aylik_tasarruf * ay
            getiri = birikim * (pow(1 + ortalama_getiri / 100, yil_sayisi) - 1)
            projeksiyon.append({
                'yil': yil_sayisi,
                'birikim': birikim,
                'getiri': getiri,
                'toplam': birikim + getiri
            })
        
        return {
            'risk_profili': risk_profili,
            'vade_ay': vade_ay,
            'aylik_tasarruf': aylik_tasarruf,
            'toplam_birikim': toplam_birikim,
            'ortalama_getiri': ortalama_getiri,
            'beklenen_getiri': beklenen_getiri,
            'toplam_deger': toplam_deger,
            'portfoy_dagilimi': dagilim,
            'uzun_vade_projeksiyon': projeksiyon
        }


class MaasZamHesaplayici:
    """Maaş zammı ve enflasyon analizi"""
    
    @staticmethod
    def zam_analizi(mevcut_brut: float, zam_orani: float, 
                    enflasyon: float) -> Dict:
        """Maaş zammı ve reel kazanç hesapla"""
        yeni_brut = mevcut_brut * (1 + zam_orani / 100)
        artis = yeni_brut - mevcut_brut
        
        # Basitleştirilmiş net hesaplama (%35 kesinti)
        mevcut_net = mevcut_brut * 0.65
        yeni_net = yeni_brut * 0.65
        net_artis = yeni_net - mevcut_net
        
        # Reel zam hesaplama
        reel_zam = ((1 + zam_orani / 100) / (1 + enflasyon / 100) - 1) * 100
        
        return {
            'mevcut_brut': mevcut_brut,
            'mevcut_net': mevcut_net,
            'zam_orani': zam_orani,
            'yeni_brut': yeni_brut,
            'yeni_net': yeni_net,
            'brut_artis': artis,
            'net_artis': net_artis,
            'enflasyon': enflasyon,
            'reel_zam': reel_zam,
            'durum': 'kazanc' if reel_zam > 0 else 'kayip',
            'yillik_net_kazanc': net_artis * 12,
            'besyillik_kazanc': net_artis * 60
        }


def para_formatla(tutar: float) -> str:
    """Türk Lirası formatında göster"""
    return f"{tutar:,.2f} TL".replace(',', '.')


def main():
    """Ana program"""
    print("=" * 80)
    print("💼 MaaşPro - Bordro & Finans Yönetim Sistemi")
    print("=" * 80)
    print()
    
    while True:
        print("\n📋 ANA MENÜ")
        print("-" * 80)
        print("1. 💰 Tazminat Hesaplama (Kıdem, İhbar, Yıllık İzin)")
        print("2. 📊 Bordro Arşivi Yönetimi")
        print("3. 📈 Asgari Ücret Analizi")
        print("4. 💳 50-30-20 Bütçe Planlaması")
        print("5. 📊 Maaş Zammı Senaryoları")
        print("6. 🎯 Yatırım Tavsiyeleri")
        print("0. ❌ Çıkış")
        print("-" * 80)
        
        secim = input("\nSeçiminiz (0-6): ").strip()
        
        if secim == "1":
            tazminat_hesapla_menu()
        elif secim == "2":
            bordro_yonetim_menu()
        elif secim == "3":
            asgari_ucret_menu()
        elif secim == "4":
            butce_menu()
        elif secim == "5":
            zam_menu()
        elif secim == "6":
            yatirim_menu()
        elif secim == "0":
            print("\n👋 MaaşPro'yu kullandığınız için teşekkürler!")
            break
        else:
            print("\n❌ Geçersiz seçim! Lütfen 0-6 arası bir değer girin.")


def tazminat_hesapla_menu():
    """Tazminat hesaplama menüsü"""
    print("\n" + "=" * 80)
    print("💰 TAZMİNAT HESAPLAMA")
    print("=" * 80)
    
    try:
        brut = float(input("\nBrüt Maaş (TL): "))
        baslama = input("İşe Başlama Tarihi (YYYY-MM-DD): ")
        bitis = input("İşten Çıkış Tarihi (YYYY-MM-DD): ")
        
        print("\nİşten Çıkış Sebebi:")
        print("1. İstifa (Kendi İsteğimle)")
        print("2. İşveren Feshi (Haklı Sebep Yok)")
        print("3. İşveren Feshi (Haklı Sebep)")
        print("4. Emeklilik")
        print("5. Ölüm")
        print("6. Askerlik")
        
        sebep_map = {
            '1': 'istifa',
            '2': 'isverenFeshi',
            '3': 'hakliSebep',
            '4': 'emeklilik',
            '5': 'olum',
            '6': 'askerlik'
        }
        
        sebep_secim = input("Seçim (1-6): ")
        cikis_sebebi = sebep_map.get(sebep_secim, 'istifa')
        
        kalan_izin = int(input("Kullanılmayan Yıllık İzin (Gün): ") or "0")
        
        sonuc = TazminatHesaplayici.tam_hesaplama(
            brut, baslama, bitis, cikis_sebebi, kalan_izin
        )
        
        print("\n" + "=" * 80)
        print("📋 HESAPLAMA SONUÇLARI")
        print("=" * 80)
        
        cs = sonuc['calisma_suresi']
        print(f"\n⏱️  Çalışma Süresi: {cs['yil']} yıl {cs['gun']} gün")
        
        print("\n💵 TAZMİNATLAR:")
        print("-" * 80)
        t = sonuc['tazminatlar']
        if t['kidem'] > 0:
            print(f"  Kıdem Tazminatı    : {para_formatla(t['kidem'])}")
        else:
            print(f"  Kıdem Tazminatı    : HAK YOK")
        
        if t['ihbar'] > 0:
            print(f"  İhbar Tazminatı    : {para_formatla(t['ihbar'])}")
        
        if t['yillik_izin'] > 0:
            print(f"  Yıllık İzin Ücreti : {para_formatla(t['yillik_izin'])}")
        
        print(f"\n  BRÜT TOPLAM        : {para_formatla(t['toplam_brut'])}")
        
        print("\n💸 KESİNTİLER:")
        print("-" * 80)
        k = sonuc['kesintiler']
        print(f"  SGK Kesintisi      : -{para_formatla(k['sgk'])}")
        print(f"  Gelir Vergisi      : -{para_formatla(k['gelir_vergisi'])}")
        print(f"  Damga Vergisi      : -{para_formatla(k['damga'])}")
        print(f"  Toplam Kesinti     : -{para_formatla(k['toplam_kesinti'])}")
        
        print("\n" + "=" * 80)
        print(f"✅ NET ÖDEME: {para_formatla(sonuc['net_tutar'])}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")


def bordro_yonetim_menu():
    """Bordro yönetim menüsü"""
    bm = BordroYonetim()
    
    while True:
        print("\n" + "=" * 80)
        print("📊 BORDRO ARŞİVİ YÖNETİMİ")
        print("=" * 80)
        print("1. Yeni Bordro Ekle")
        print("2. Bordroları Listele")
        print("3. İstatistikleri Göster")
        print("4. Bordro Sil")
        print("0. Ana Menüye Dön")
        
        secim = input("\nSeçim: ").strip()
        
        if secim == "1":
            try:
                ay = input("\nAy (YYYY-MM): ")
                brut = float(input("Brüt Maaş: "))
                net = float(input("Net Maaş: "))
                
                if bm.bordro_ekle(ay, brut, net):
                    print("\n✅ Bordro başarıyla eklendi!")
                else:
                    print("\n❌ Bordro eklenemedi!")
            except:
                print("\n❌ Geçersiz giriş!")
        
        elif secim == "2":
            bordrolar = bm.bordrolari_getir()
            if not bordrolar:
                print("\n⚠️  Henüz bordro kaydı yok.")
            else:
                print(f"\n📋 TOPLAM {len(bordrolar)} BORDRO:")
                print("-" * 80)
                for b in bordrolar:
                    print(f"\n#{b['id']} - {b['ay']}")
                    print(f"  Brüt: {para_formatla(b['brut'])} | Net: {para_formatla(b['net'])}")
        
        elif secim == "3":
            stats = bm.istatistikler()
            print("\n" + "=" * 80)
            print("📊 İSTATİSTİKLER")
            print("=" * 80)
            print(f"Toplam Bordro Sayısı : {stats['toplam']}")
            print(f"Ortalama Brüt Maaş  : {para_formatla(stats['ortalama_brut'])}")
            print(f"Ortalama Net Maaş   : {para_formatla(stats['ortalama_net'])}")
            print(f"Toplam Kazanç       : {para_formatla(stats['toplam_kazanc'])}")
            print(f"Toplam Kesinti      : {para_formatla(stats['toplam_kesinti'])}")
        
        elif secim == "4":
            try:
                bordro_id = int(input("\nSilinecek Bordro ID: "))
                if bm.bordro_sil(bordro_id):
                    print("\n✅ Bordro silindi!")
                else:
                    print("\n❌ Bordro silinemedi!")
            except:
                print("\n❌ Geçersiz ID!")
        
        elif secim == "0":
            break


def asgari_ucret_menu():
    """Asgari ücret analizi menüsü"""
    print("\n" + "=" * 80)
    print("📈 ASGARİ ÜCRET ANALİZİ (2020-2026)")
    print("=" * 80)
    
    print("\n📊 YILLARA GÖRE ASGARİ ÜCRET:")
    print("-" * 80)
    print(f"{'Yıl':<8} {'Dönem':<10} {'Brüt':>15} {'Net':>15} {'Artış':>10}")
    print("-" * 80)
    
    for au in AsgariUcretAnaliz.ASGARI_UCRETLER:
        print(f"{au['yil']:<8} {au['donem']}. Dönem  "
              f"{para_formatla(au['brut']):>15} "
              f"{para_formatla(au['net']):>15} "
              f"%{au['artis']:>8.2f}")
    
    print("\n" + "=" * 80)
    print(f"📌 2020'den bu yana TOPLAM ARTIŞ: %{AsgariUcretAnaliz.toplam_artis()}")
    print("=" * 80)
    
    try:
        maas = float(input("\nMaaşınız (Brüt TL): "))
        analiz = AsgariUcretAnaliz.katsayi_hesapla(maas)
        
        print(f"\n✅ Maaşınız 2026 asgari ücretin {analiz['katsayi']}x katıdır")
        print(f"   Asgari ücretten {para_formatla(analiz['fark'])} fazla kazanıyorsunuz")
    except:
        pass


def butce_menu():
    """Bütçe planlama menüsü"""
    print("\n" + "=" * 80)
    print("💳 50-30-20 BÜTÇE PLANLAMASI")
    print("=" * 80)
    print("\n📌 50-30-20 Kuralı:")
    print("  • %50 - İhtiyaçlar (zorunlu giderler)")
    print("  • %30 - İstekler (opsiyonel harcamalar)")
    print("  • %20 - Tasarruf ve Yatırım")
    
    try:
        net_gelir = float(input("\nAylık Net Geliriniz: "))
        butce = ButcePlanlama.butce_hesapla(net_gelir)
        
        print("\n" + "=" * 80)
        print("📊 BÜTÇE PLANI")
        print("=" * 80)
        
        print(f"\n🏠 İHTİYAÇLAR (%50): {para_formatla(butce['ihtiyaclar']['tutar'])}")
        for kat in butce['ihtiyaclar']['kategoriler']:
            print(f"   • {kat}")
        
        print(f"\n🎉 İSTEKLER (%30): {para_formatla(butce['istekler']['tutar'])}")
        for kat in butce['istekler']['kategoriler']:
            print(f"   • {kat}")
        
        print(f"\n💰 TASARRUF (%20): {para_formatla(butce['tasarruf']['tutar'])}")
        for kat in butce['tasarruf']['kategoriler']:
            print(f"   • {kat}")
        
        print(f"\n✅ 12 ayda biriktireceğiniz: {para_formatla(butce['tasarruf']['yillik_birikim'])}")
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")


def zam_menu():
    """Maaş zammı menüsü"""
    print("\n" + "=" * 80)
    print("📊 MAAŞ ZAMMI SENARYOLARI")
    print("=" * 80)
    
    try:
        mevcut = float(input("\nMevcut Brüt Maaş: "))
        zam = float(input("Zam Oranı (%): "))
        enflasyon = float(input("Enflasyon Oranı (%): "))
        
        sonuc = MaasZamHesaplayici.zam_analizi(mevcut, zam, enflasyon)
        
        print("\n" + "=" * 80)
        print("📈 ZAM ANALİZİ")
        print("=" * 80)
        
        print(f"\nMevcut Brüt: {para_formatla(sonuc['mevcut_brut'])}")
        print(f"Mevcut Net : {para_formatla(sonuc['mevcut_net'])}")
        print(f"\nZam Oranı  : %{sonuc['zam_orani']}")
        print(f"\nYeni Brüt  : {para_formatla(sonuc['yeni_brut'])}")
        print(f"Yeni Net   : {para_formatla(sonuc['yeni_net'])}")
        print(f"\nBrüt Artış : +{para_formatla(sonuc['brut_artis'])}")
        print(f"Net Artış  : +{para_formatla(sonuc['net_artis'])}")
        
        print(f"\n{'='*80}")
        print(f"Enflasyon     : %{sonuc['enflasyon']}")
        print(f"REEL ZAM      : %{sonuc['reel_zam']:.2f}")
        
        if sonuc['durum'] == 'kazanc':
            print(f"\n✅ Aldığınız zam enflasyonun üzerinde!")
            print(f"   Reel olarak kazanç sağlıyorsunuz.")
        else:
            print(f"\n⚠️  Aldığınız zam enflasyonun altında!")
            print(f"   Reel olarak kayıp yaşıyorsunuz.")
        
        print(f"\n💵 Yıllık net kazanç  : {para_formatla(sonuc['yillik_net_kazanc'])}")
        print(f"💰 5 yıllık kazanç    : {para_formatla(sonuc['besyillik_kazanc'])}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")


def yatirim_menu():
    """Yatırım tavsiyeleri menüsü"""
    print("\n" + "=" * 80)
    print("🎯 YATIRIM TAVSİYELERİ")
    print("=" * 80)
    
    try:
        tasarruf = float(input("\nAylık Tasarruf Tutarı: "))
        vade = int(input("Yatırım Süresi (Ay): "))
        
        print("\nRisk Profili:")
        print("1. Düşük Risk (Güvenli)")
        print("2. Orta Risk (Dengeli)")
        print("3. Yüksek Risk (Agresif)")
        
        risk_map = {'1': 'dusuk', '2': 'orta', '3': 'yuksek'}
        risk_secim = input("Seçim (1-3): ")
        risk = risk_map.get(risk_secim, 'orta')
        
        sonuc = YatirimHesaplayici.yatirim_hesapla(tasarruf, vade, risk)
        
        print("\n" + "=" * 80)
        print("💼 YATIRIM PORTFÖYÜ")
        print("=" * 80)
        
        print(f"\nRisk Profili       : {sonuc['risk_profili'].upper()}")
        print(f"Yatırım Süresi     : {sonuc['vade_ay']} ay")
        print(f"Aylık Tasarruf     : {para_formatla(sonuc['aylik_tasarruf'])}")
        print(f"\nToplam Birikim     : {para_formatla(sonuc['toplam_birikim'])}")
        print(f"Beklenen Getiri    : +{para_formatla(sonuc['beklenen_getiri'])}")
        print(f"Ortalama Getiri    : %{sonuc['ortalama_getiri']:.2f}")
        print(f"\n{'='*80}")
        print(f"💰 TOPLAM DEĞER: {para_formatla(sonuc['toplam_deger'])}")
        print("=" * 80)
        
        print("\n📊 ÖNERİLEN DAĞILIM:")
        print("-" * 80)
        for y in sonuc['portfoy_dagilimi']:
            print(f"{y['ad']:<25} %{y['oran']:<3} → {para_formatla(y['miktar'])}")
        
        print("\n📈 UZUN VADELİ PROJEKSİYON:")
        print("-" * 80)
        print(f"{'Süre':<10} {'Birikim':>20} {'Getiri':>20} {'Toplam':>20}")
        print("-" * 80)
        
        for p in sonuc['uzun_vade_projeksiyon']:
            print(f"{p['yil']} Yıl    "
                  f"{para_formatla(p['birikim']):>20} "
                  f"{para_formatla(p['getiri']):>20} "
                  f"{para_formatla(p['toplam']):>20}")
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")


if __name__ == "__main__":
    main()
