# Dashboard Analiz ve Grafik Dokumantasyonu

Bu dokuman, TBB (Turkiye Bankalar Birligi) Dashboard sayfasinda yer alan tum grafiklerin ve analizlerin nasil yapildigini aciklamaktadir.

---

## Genel Mimari

- **Veri Kaynaklari**: TBB web sitesinden (tbb.org.tr, verisistemi.tbb.org.tr) scrape edilen veriler
- **Veritabanlari**:
  - **PostgreSQL**: Banka bilgileri, sube bilgileri, ATM bilgileri, tarihce (yapisal/statik veriler)
  - **ClickHouse**: Finansal tablolar, bolgesel istatistikler, risk merkezi verileri (buyuk hacimli analitik veriler)
- **Onbellekleme**: Redis (finansal veriler 1 saat, bolgesel veriler 6 saat, banka verileri 24 saat TTL)
- **Backend**: FastAPI (async) + ClickHouse driver + asyncpg
- **Frontend**: React + TypeScript + Ant Design + ECharts (echarts-for-react) + TanStack Query

---

## 1. KPI Kartlari

Dashboard'in en ust satirinda 4 adet ozet istatistik karti yer alir.

### 1.1 Banka Sayisi

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Statistic (sayi karti) |
| **Veri Kaynagi** | PostgreSQL `bank_info` tablosu |
| **API Endpoint** | `GET /api/banks/` |
| **Hesaplama** | Frontend'de `banks.length` - toplam kayit sayisi |
| **Aciklama** | TBB'ye kayitli tum bankalarin sayisi (mevduat, kalkinma/yatirim bankalari dahil) |

### 1.2 Sube Sayisi

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Statistic (sayi karti) |
| **Veri Kaynagi** | PostgreSQL `branch_info` tablosu |
| **API Endpoint** | `GET /api/banks/dashboard-stats` |
| **SQL Sorgusu** | `SELECT COUNT(*) FROM branch_info` |
| **Aciklama** | Turkiye genelindeki toplam banka subesi sayisi |

### 1.3 ATM Sayisi

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Statistic (sayi karti) |
| **Veri Kaynagi** | PostgreSQL `atm_info` tablosu |
| **API Endpoint** | `GET /api/banks/dashboard-stats` |
| **SQL Sorgusu** | `SELECT COUNT(*) FROM atm_info` |
| **Aciklama** | Turkiye genelindeki toplam ATM sayisi |

### 1.4 Toplam Aktifler

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Statistic (sayi karti, formatli) |
| **Veri Kaynagi** | ClickHouse `tbb.financial_statements` tablosu |
| **API Endpoint** | `GET /api/financial/summary` |
| **SQL Sorgusu** | `SELECT main_statement, sum(amount_total) as total, count() as cnt FROM tbb.financial_statements FINAL GROUP BY main_statement ORDER BY total DESC` |
| **Hesaplama** | `main_statement` alanlari icinde "aktif" veya "varlik" iceren kaydin `total` degeri |
| **Format** | T TL (trilyon), B TL (milyar), M TL (milyon) biciminde kisaltilir |
| **Aciklama** | Turkiye bankacilik sektorunun toplam aktif buyuklugu |

---

## 2. Banka Dagilim Grafikleri

Iki pasta grafik yan yana gosterilir. Veriler frontend'de client-side olarak hesaplanir.

### 2.1 Banka Grubu Dagilimi (Pie Chart)

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Pasta grafik (ECharts Pie) |
| **Veri Kaynagi** | PostgreSQL `bank_info` tablosu |
| **API Endpoint** | `GET /api/banks/` |
| **Hesaplama (Client-side)** | `useMemo` ile banka listesi `bank_group` alanina gore gruplanir ve her gruptaki banka sayisi hesaplanir |

```
Algoritma:
1. Tum bankalar cekilir (useBanks hook)
2. Her bankanin bank_group alani okunur
3. Ayni gruba ait bankalar sayilir
4. {name: grup_adi, value: banka_sayisi} dizisi olusturulur
```

| **Ornek Gruplar** | Mevduat Bankalari, Kalkinma ve Yatirim Bankalari, vb. |
|---|---|
| **Aciklama** | Bankalarin ana grup bazinda dagilimini gosterir (kamu, ozel, yabanci sermayeli vb.) |

### 2.2 Alt Grup Dagilimi (Donut Chart)

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Donut grafik (ECharts Pie, radius: ['40%', '70%']) |
| **Veri Kaynagi** | PostgreSQL `bank_info` tablosu |
| **API Endpoint** | `GET /api/banks/` |
| **Hesaplama (Client-side)** | Ayni mantik, ancak `sub_bank_group` alanina gore gruplama yapilir |
| **Aciklama** | Bankalarin alt grup bazinda daha detayli dagilimini gosterir |

---

## 3. Cografi Dagilim Grafikleri

Iki yatay bar grafik yan yana gosterilir.

### 3.1 Illere Gore Sube Sayisi (Top 15)

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Yatay bar grafik (ECharts Bar, horizontal) |
| **Veri Kaynagi** | PostgreSQL `branch_info` tablosu |
| **API Endpoint** | `GET /api/banks/dashboard-stats` |
| **SQL Sorgusu** | `SELECT city, COUNT(*) AS count FROM branch_info WHERE city IS NOT NULL GROUP BY city ORDER BY count DESC LIMIT 15` |
| **Aciklama** | En fazla subeye sahip 15 il. Backend'de aggregasyon yapilir (50.000+ sube verisi client'a cekilemez) |

### 3.2 Illere Gore ATM Sayisi (Top 15)

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Yatay bar grafik (ECharts Bar, horizontal) |
| **Veri Kaynagi** | PostgreSQL `atm_info` tablosu |
| **API Endpoint** | `GET /api/banks/dashboard-stats` |
| **SQL Sorgusu** | `SELECT city, COUNT(*) AS count FROM atm_info WHERE city IS NOT NULL GROUP BY city ORDER BY count DESC LIMIT 15` |
| **Aciklama** | En fazla ATM'ye sahip 15 il. Backend'de aggregasyon yapilir |

---

## 4. Kredi / Mevduat Orani (Loan-to-Deposit Ratio) Analizi

Bolgesel bazda kredi-mevduat dengesini gosteren temel bankacilik metrigi.

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Yatay bar grafik (ECharts Bar, horizontal) |
| **Veri Kaynagi** | ClickHouse `tbb.region_statistics` tablosu |
| **API Endpoint** | `GET /api/regions/loan-deposit-ratio?year={year}` |
| **Filtreler** | Yil secici dropdown |

### Hesaplama Formulu

```
Kredi/Mevduat Orani = Toplam Kredi / Toplam Mevduat
```

### SQL Sorgusu (ClickHouse Conditional Aggregation)

```sql
SELECT
    region,
    sumIf(value, metric IN (
        'Iht.Disi Krediler',
        'Iht.Kred./ Denizcilik', 'Iht.Kred./ Diger',
        'Iht.Kred./ Gayrimenkul', 'Iht.Kred./ Mesleki',
        'Iht.Kred./ Tarim', 'Iht.Kred./ Turizm'
    )) AS total_credit,
    sumIf(value, metric IN (
        'Tasarruf Mevduati', 'Bankalar Mevduati',
        'Ticari Kuruluslar Mevduati', 'Doviz Tevdiat Hesaplari',
        'Resmi Kuruluslar Mevduati', 'Diger Mevduat',
        'Altin Depo Hesabi'
    )) AS total_deposit
FROM tbb.region_statistics FINAL
WHERE year_id = {year}
  AND region NOT IN ('Tum Bolgeler', 'Yabanci Ulkeler', 'Iller Bankasi', 'Kibris')
GROUP BY region
HAVING total_deposit > 0
ORDER BY total_credit / total_deposit DESC
```

### Kredi Bilesenleri (7 metrik)
1. Ihtisas Disi Krediler
2. Ihtisas Kredisi / Denizcilik
3. Ihtisas Kredisi / Diger
4. Ihtisas Kredisi / Gayrimenkul
5. Ihtisas Kredisi / Mesleki
6. Ihtisas Kredisi / Tarim
7. Ihtisas Kredisi / Turizm

### Mevduat Bilesenleri (7 metrik)
1. Tasarruf Mevduati
2. Bankalar Mevduati
3. Ticari Kuruluslar Mevduati
4. Doviz Tevdiat Hesaplari
5. Resmi Kuruluslar Mevduati
6. Diger Mevduat
7. Altin Depo Hesabi

### Yorumlama
- **Oran > 1**: Bolge net kredi vericisi (mevduattan fazla kredi kullandiriyor, baska bolgelerden fon akisi var)
- **Oran < 1**: Bolge net mevduat toplayicisi (toplanan mevduat baska bolgelere kredi olarak aktariliyor)
- **Oran = 1**: Kredi ve mevduat dengede

### Teknik Detaylar
- Top 20 bolge gosterilir (grafik okunabilirligi icin)
- `null` ratio'lu bolgeler filtrelenir
- Haric tutulan bolgeler: Tum Bolgeler, Yabanci Ulkeler, Iller Bankasi, Kibris (aggregate/ozel satirlar)

---

## 5. Kredi Sektorel Yogunlasma (HHI - Herfindahl-Hirschman Endeksi) Analizi

Bolgesel bazda kredi portfoyunun sektorel yogunlasmasini olcer.

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Yigili yatay bar grafik (ECharts Bar, horizontal + stacked) |
| **Veri Kaynagi** | ClickHouse `tbb.region_statistics` tablosu |
| **API Endpoint** | `GET /api/regions/credit-hhi?year={year}` |
| **Filtreler** | Yil secici dropdown + Coklu sektor secici (multi-select) |

### Hesaplama Formulu

```
HHI = SUM(sektor_payi_yuzde ^ 2)    her sektor icin

Sektor Payi (%) = (Sektor Kredi Tutari / Toplam Kredi) * 100
```

### Analiz Edilen 6 Kredi Sektoru
1. **Denizcilik** (Iht.Kred./ Denizcilik)
2. **Diger** (Iht.Kred./ Diger)
3. **Gayrimenkul** (Iht.Kred./ Gayrimenkul)
4. **Mesleki** (Iht.Kred./ Mesleki)
5. **Tarim** (Iht.Kred./ Tarim)
6. **Turizm** (Iht.Kred./ Turizm)

### HHI Hesaplama Algoritmasi (Backend)

```
1. Her bolge icin 6 sektorun kredi tutarlari cekilir
2. Bolge toplam kredisi hesaplanir: toplam = sum(tum_sektorler)
3. Her sektorun payi hesaplanir: pay = (sektor_tutari / toplam) * 100
4. HHI = sum(pay^2)   (tum sektorler icin)
5. Baskin sektor = en yuksek tutara sahip sektor belirlenir
6. Sonuclar HHI'ye gore azalan sirada siralanir
```

### Frontend Sektor Filtreleme

Kullanici secili sektorleri degistirdiginde:
```
1. Secili sektorlerin paylari filtrelenir
2. Her bolge icin filtrelenmis toplam pay hesaplanir
3. Toplami > 0 olan bolgeler kalir
4. Top 20 bolge gosterilir
```

### Yorumlama
- **HHI < 1500**: Dusuk yogunlasma (cok cesitli kredi portfoyu)
- **HHI 1500-2500**: Orta yogunlasma
- **HHI > 2500**: Yuksek yogunlasma (kredi portfoyu bir veya iki sektore bagimli)
- **HHI = 10000**: Tam yogunlasma (tek sektore %100 kredi)

### Grafik Yapisi
- X ekseni: Sektorel paylarin yigilmis yuzdesi (%)
- Y ekseni: Bolge adi + HHI degeri (ornek: "Ankara (HHI: 3250)")
- Her renk bir sektoru temsil eder
- Bar'larin toplam uzunlugu %100'e yakindir

---

## 6. Finansal Oran Analizi

Banka bazinda 6 temel finansal oranin karsilastirmali analizi.

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Yatay bar grafik (ECharts Bar, horizontal) |
| **Veri Kaynagi** | ClickHouse `tbb.financial_statements` tablosu |
| **API Endpoint** | `GET /api/financial/ratios?year={year}&month={month}` |
| **Filtreler** | Donem (yil/ay) secici + Oran turu secici dropdown |

### Genel Hesaplama Yaklasimi

Tek bir ClickHouse sorgusu ile tum oranlar icin gerekli bilesenler cekilir:

```sql
SELECT
    bank_name,
    sumIf(amount_total, main_statement='1. VARLIKLAR'
        AND child_statement='XI. VARLIKLAR TOPLAMI') AS total_assets,
    sumIf(amount_total, main_statement='2. YUKUMLULUKLER'
        AND child_statement='XVI. OZKAYNAKLAR') AS equity,
    sumIf(amount_total, main_statement='4. GELIR-GIDER TABLOSU'
        AND child_statement='XXV. DONEM NET KARI/ZARARI (XIX+XXIV)') AS net_profit,
    sumIf(amount_total, main_statement='4. GELIR-GIDER TABLOSU'
        AND child_statement='III. NET FAIZ GELIRI/GIDERI (I - II)') AS net_interest_income,
    sumIf(amount_total, main_statement='1. VARLIKLAR'
        AND child_statement='2.1. Krediler') AS total_loans,
    sumIf(amount_total, main_statement='1. VARLIKLAR'
        AND child_statement='2.5 Beklenen Zarar Karsiliklari (-) (TFRS 9)') AS credit_provisions,
    sumIf(amount_fc, main_statement='1. VARLIKLAR'
        AND child_statement='XI. VARLIKLAR TOPLAMI') AS assets_fc,
    sumIf(amount_fc, main_statement='2. YUKUMLULUKLER'
        AND child_statement='XVII. YUKUMLULUKLER TOPLAMI') AS liabilities_fc
FROM tbb.financial_statements FINAL
WHERE year_id = {year} AND month_id = {month}
  AND bank_name NOT IN (aggregate_kategoriler)
GROUP BY bank_name
HAVING total_assets > 0
ORDER BY total_assets DESC
```

Haric tutulan aggregate kategoriler:
- Turkiye Bankacilik Sistemi
- Mevduat Bankalari
- Kamusal Sermayeli Mevduat Bankalari
- Ozel Sermayeli Mevduat Bankalari
- Yabanci Sermayeli Bankalar
- Kalkinma ve Yatirim Bankalari
- Tasarruf Mevduati Sigorta Fonuna Devredilen Bankalar

### 6.1 ROA - Aktif Karlilik Orani (Return on Assets)

| Ozellik | Deger |
|---------|-------|
| **Formul** | `(Net Kar / Toplam Aktif) * 100` |
| **Pay** | `XXV. DONEM NET KARI/ZARARI (XIX+XXIV)` (Gelir-Gider Tablosu) |
| **Payda** | `XI. VARLIKLAR TOPLAMI` (Bilanconun aktif tarafi) |
| **Birim** | Yuzde (%) |

**Yorumlama**: Bankanin toplam varliklarinin ne kadar verimli kullanildigini gosterir. Yuksek ROA, aktif yonetiminde basariyi ifade eder.
- Sektor ortalamasi genelde %1-3 arasindadir
- Negatif ROA zarar anlamina gelir

### 6.2 ROE - Ozkaynak Karlilik Orani (Return on Equity)

| Ozellik | Deger |
|---------|-------|
| **Formul** | `(Net Kar / Ozkaynaklar) * 100` |
| **Pay** | `XXV. DONEM NET KARI/ZARARI (XIX+XXIV)` (Gelir-Gider Tablosu) |
| **Payda** | `XVI. OZKAYNAKLAR` (Bilanco pasif tarafi) |
| **Birim** | Yuzde (%) |

**Yorumlama**: Hissedar sermayesinin ne kadar karliligi oldugunu olcer. Yatirimci perspektifinden en onemli metriklerden biridir.
- Sektor ortalamasi genelde %15-25 arasindadir
- ROE > ROA farki kaldirac etkisini gosterir

### 6.3 NIM - Net Faiz Marji (Net Interest Margin)

| Ozellik | Deger |
|---------|-------|
| **Formul** | `(Net Faiz Geliri / Toplam Aktif) * 100` |
| **Pay** | `III. NET FAIZ GELIRI/GIDERI (I - II)` (Gelir-Gider Tablosu) |
| **Payda** | `XI. VARLIKLAR TOPLAMI` (Bilanconun aktif tarafi) |
| **Birim** | Yuzde (%) |

**Yorumlama**: Bankanin temel faaliyetinden (kredi-mevduat faiz farki) ne kadar gelir elde ettigini gosterir.
- Net Faiz Geliri = Faiz Gelirleri - Faiz Giderleri
- Yuksek NIM genis faiz marjini (spread) gosterir
- Yatirim bankalari genelde daha yuksek NIM'e sahiptir

### 6.4 Karsilik Orani (Provision Rate / Coverage Ratio)

| Ozellik | Deger |
|---------|-------|
| **Formul** | `(|Beklenen Zarar Karsiliklari| / Toplam Krediler) * 100` |
| **Pay** | `2.5 Beklenen Zarar Karsiliklari (-) (TFRS 9 uygulayan b.)` - mutlak deger alinir |
| **Payda** | `2.1. Krediler` (Bilanco aktif tarafi) |
| **Birim** | Yuzde (%) |

**Yorumlama**: Kredi portfoyunun ne kadarinin beklenen kayip olarak karsiliga ayrildigini gosterir.
- TFRS 9 kapsaminda tum bankalar beklenen zarar modeli kullanir
- Yuksek oran yuksek kredi riski algisini gosterir
- Karsiliklar bilancoda negatif deger olarak yer alir, bu yuzden mutlak deger kullanilir
- Genelde %2-6 arasinda seyreder

**Not**: Klasik TGA (Takipteki / Donuk Alacak) orani yerine TFRS 9 karsilik orani kullanilmistir. Cunku TBB verilerinde tum bankalar TFRS 9 raporlamasi yapmaktadir ve "Donuk Alacaklar (TFRS 9 uygulamayan b.)" alani tum bankalarda sifir donmektedir.

### 6.5 Kaldirac Orani (Leverage / Capital Adequacy)

| Ozellik | Deger |
|---------|-------|
| **Formul** | `(Ozkaynaklar / Toplam Aktif) * 100` |
| **Pay** | `XVI. OZKAYNAKLAR` (Bilanco pasif tarafi) |
| **Payda** | `XI. VARLIKLAR TOPLAMI` (Bilanco aktif tarafi) |
| **Birim** | Yuzde (%) |

**Yorumlama**: Bankanin sermaye gucunu ve borcluluk seviyesini gosterir.
- Dusuk oran = yuksek kaldirac (daha fazla borcla finanse edilmis)
- Yuksek oran = guclu sermaye yapisi
- Duzenleme alt siniri genelde %3-5 civarindadir
- Sektor ortalamasi %8-12 arasindadir
- Kalkinma/yatirim bankalari genelde daha yuksek orana sahiptir

### 6.6 YP Aktif Payi (FX Asset Share)

| Ozellik | Deger |
|---------|-------|
| **Formul** | `(Yabanci Para Aktifler / Toplam Aktif) * 100` |
| **Pay** | `XI. VARLIKLAR TOPLAMI` tablosundaki `amount_fc` (Foreign Currency) degeri |
| **Payda** | `XI. VARLIKLAR TOPLAMI` tablosundaki `amount_total` degeri |
| **Birim** | Yuzde (%) |

**Yorumlama**: Bankanin aktif yapisinin ne kadarinin doviz cinsinden oldugunu gosterir.
- Yuksek YP payi kur riskine acikligi gosterir
- Doviz pozisyon riski yonetimi acisindan onemlidir
- TBB verileri her kalem icin TP (Turk Parasi), YP (Yabanci Para) ve Toplam ayrimi sunar
- Sektor ortalamasi genelde %35-40 arasindadir

---

## 7. Bolgesel Karsilastirma Analizi

Herhangi bir bolgesel metrigin tum bolgeler arasinda karsilastirmali gosterimi.

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Dikey bar grafik (ECharts Bar) |
| **Veri Kaynagi** | ClickHouse `tbb.region_statistics` tablosu |
| **API Endpoint** | `GET /api/regions/comparison?metric={metric}&year={year}` |
| **Filtreler** | Metrik secici dropdown + Yil secici dropdown |

### SQL Sorgusu

```sql
SELECT region, value
FROM tbb.region_statistics FINAL
WHERE metric = {metric} AND year_id = {year}
ORDER BY value DESC
```

### Kullanilabilir Metrikler (Ornekler)
- Tasarruf Mevduati
- Bankalar Mevduati
- Ticari Kuruluslar Mevduati
- Doviz Tevdiat Hesaplari
- Ihtisas Disi Krediler
- Ihtisas Kredisi turleri (Denizcilik, Gayrimenkul, Tarim, Turizm, Mesleki, Diger)
- Resmi Kuruluslar Mevduati
- Diger Mevduat
- Altin Depo Hesabi

### Aciklama
- Varsayilan olarak ilk metrik ve ilk yil secili gelir
- Kullanici dropdown'lardan farkli metrik/yil secebilir
- Tum bolgeler gosterilir, buyukten kucuge siralanir

---

## 8. Sektor Toplam Trend Analizi

Turkiye bankacilik sektorunun zaman icerisindeki buyume trendini gosterir.

| Ozellik | Deger |
|---------|-------|
| **Grafik Turu** | Cizgi grafik (ECharts Line) |
| **Veri Kaynagi** | ClickHouse `tbb.financial_statements` tablosu |
| **API Endpoint** | `GET /api/financial/time-series?bank_name=Turkiye+Bankacilik+Sistemi` |

### SQL Sorgusu

```sql
SELECT year_id, month_id, sum(amount_total) as amount_total
FROM tbb.financial_statements FINAL
WHERE bank_name = 'Turkiye Bankacilik Sistemi'
GROUP BY year_id, month_id
ORDER BY year_id, month_id
```

### Aciklama
- X ekseni: Donem (Yil/Ay formatinda, ornek: 2025/3, 2025/6, 2025/9)
- Y ekseni: Toplam tutar (TL)
- "Turkiye Bankacilik Sistemi" adli aggregate kayit kullanilir
- Tum main_statement'larin amount_total degerleri toplanir
- Sektorun genel buyume/kuculme trendini gosterir

---

## Teknik Notlar

### Veri Akisi

```
TBB Web Sitesi
    |
    v
Scrapers (Airflow DAG'lari ile zamanlanir)
    |
    v
Transformers (veri temizleme, normalizasyon)
    |
    v
Loaders (PostgreSQL + ClickHouse'a yazma)
    |
    v
FastAPI Backend (async servisler + Redis cache)
    |
    v
React Frontend (TanStack Query ile veri cekme + ECharts gorsellestirme)
```

### ClickHouse Ozel Notlari
- Tum sorgularda `FINAL` anahtar kelimesi kullanilir (ReplacingMergeTree tutarliligi icin)
- `sumIf()` fonksiyonu ile tek sorguda birden fazla kosullu aggregasyon yapilir
- Finansal tablolarda `amount_tc` (TP), `amount_fc` (YP), `amount_total` (Toplam) ayrik tutulur

### Frontend Optimizasyonlari
- `useMemo` ile client-side aggregasyonlar onbellekelenir (pie chart gruplama, HHI filtreleme)
- `React.useEffect` ile varsayilan filtre degerleri data yuklendiginde atanir
- `enabled` flagi ile gereksiz API cagrilari engellenir (ornek: yil secilmeden ratio sorgusu yapilmaz)
- TanStack Query staleTime ile gereksiz yeniden yukleme onlenir

### Onbellekleme Sureler (Redis TTL)
| Veri Turu | TTL | Aciklama |
|-----------|-----|----------|
| Banka bilgileri | 24 saat | Nadiren degisir |
| Bolgesel istatistikler | 6 saat | Gunluk guncellenir |
| Finansal tablolar | 1 saat | Ceyreklik guncellenir |
| Dashboard stats | 24 saat | Nadiren degisir |
