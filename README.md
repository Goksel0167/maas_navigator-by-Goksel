# 💼 MaaşPro - Bordro & Finans Yönetim Sistemi

Profesyonel bordro hesaplama, tazminat analizi ve yatırım planlama uygulaması.

## 🚀 Özellikler

### 1. 💰 Tazminat Hesaplama
- **Kıdem Tazminatı**: 2026 güncel tavanı (64.948,77 TL) ile hesaplama
- **İhbar Tazminatı**: Çalışma süresine göre otomatik hesaplama
- **Yıllık İzin Ücreti**: Kullanılmayan izinler için ödeme
- **Vergi & SGK**: Tam kesinti hesaplaması ile net tutar

### 2. 📊 Bordro Arşivi
- SQLite veritabanı ile güvenli kayıt
- Aylık bordro ekleme/silme
- Detaylı istatistikler
- Ortalama maaş hesaplamaları

### 3. 📈 Asgari Ücret Analizi
- 2020-2026 yılları arası karşılaştırma
- Resmi kaynaklı güncel veriler
- Maaş/Asgari ücret katsayısı
- Toplam artış oranları

### 4. 💳 50-30-20 Bütçe Planlama
- %50 İhtiyaçlar
- %30 İstekler
- %20 Tasarruf/Yatırım
- Yıllık birikim hesaplama

### 5. 📊 Maaş Zammı Senaryoları
- Brüt/Net artış hesaplama
- Enflasyon analizi
- Reel kazanç/kayıp
- Uzun vadeli projeksiyon

### 6. 🎯 Yatırım Tavsiyeleri
- 3 risk profili (Düşük/Orta/Yüksek)
- Portföy dağılım önerileri
- Bileşik getiri hesaplama
- 10 yıllık projeksiyon

## 📦 Kurulum

### Gereksinimler
```bash
Python 3.7+
```

Standart Python kütüphaneleri kullanılmaktadır, ekstra paket kurulumu gerekmez.

## 🎮 Kullanım

### Komut Satırı Uygulaması

```bash
python maaspro.py
```

Program başladığında interaktif menü ile tüm özelliklere erişebilirsiniz.

### Örnek Kullanım Senaryoları

#### 1. Tazminat Hesaplama
```
Brüt Maaş: 70200
Başlama Tarihi: 2017-01-01
Çıkış Tarihi: 2024-12-31
Çıkış Sebebi: İşveren Feshi
Kalan İzin: 14
```

#### 2. Bordro Ekleme
```
Ay: 2024-12
Brüt: 70200
Net: 55715.15
```

#### 3. Bütçe Planlama
```
Net Gelir: 55715
→ İhtiyaçlar: 27,857.50 TL
→ İstekler: 16,714.50 TL
→ Tasarruf: 11,143.00 TL
```

## 📊 Veritabanı Yapısı

Uygulama SQLite kullanır ve `maaspro.db` dosyasında verileri saklar:

```sql
CREATE TABLE bordrolar (
    id INTEGER PRIMARY KEY,
    ay TEXT NOT NULL,
    brut REAL NOT NULL,
    net REAL NOT NULL,
    sgk_kesinti REAL,
    gelir_vergisi REAL,
    damga_vergisi REAL,
    eklenme_tarihi TEXT
)
```

## 🔐 Güvenlik

- Veriler yerel SQLite veritabanında saklanır
- İnternet bağlantısı gerektirmez
- Tüm hesaplamalar lokal yapılır
- Kişisel verileriniz hiçbir yere gönderilmez

## 📋 Özellik Detayları

### Tazminat Hesaplama Formülleri

**Kıdem Tazminatı:**
```python
kıdem = min(brüt_maaş, tavan) × yıl + (min(brüt_maaş, tavan) / 365) × gün
```

**İhbar Tazminatı:**
- < 6 ay: 2 haftalık maaş
- 6 ay - 1.5 yıl: 4 haftalık maaş
- 1.5 - 3 yıl: 6 haftalık maaş
- 3+ yıl: 8 haftalık maaş

**Kesintiler:**
- SGK: %14
- Gelir Vergisi: Dilimli (2025 dilimleri)
- Damga Vergisi: %0.759

### Yatırım Stratejileri

**Düşük Risk:**
- %50 Vadeli TL Mevduat
- %30 Devlet Tahvili
- %20 Altın

**Orta Risk:**
- %40 Hisse Senedi Fonu
- %30 Vadeli Mevduat
- %20 Altın
- %10 Döviz

**Yüksek Risk:**
- %50 Hisse Senedi
- %20 Kripto Para
- %20 Hisse Fonu
- %10 Altın

## 🎯 Gelecek Özellikler (Roadmap)

- [ ] Web arayüzü (Flask/Django)
- [ ] Grafik ve görselleştirmeler
- [ ] Excel/PDF export
- [ ] Çoklu kullanıcı desteği
- [ ] Mobil uygulama
- [ ] Otomatik bordro girişi (OCR)
- [ ] E-posta bildirimleri
- [ ] Vergi optimizasyonu önerileri

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Pull request göndermekten çekinmeyin.

## 📞 İletişim

Sorularınız için issue açabilirsiniz.

## ⚠️ Yasal Uyarı

Bu uygulama bilgilendirme amaçlıdır. Resmi hesaplamalar için muhasebeci veya mali müşavirinize danışınız. Vergi ve tazminat konularında güncel mevzuatı takip ediniz.

## 📚 Kaynaklar

- [T.C. Çalışma ve Sosyal Güvenlik Bakanlığı](https://www.csgb.gov.tr/)
- [T.C. Hazine ve Maliye Bakanlığı](https://www.hmb.gov.tr/)
- [Resmi Gazete](https://www.resmigazete.gov.tr/)

---

💼 **MaaşPro** ile finansal geleceğinizi planlayın!
