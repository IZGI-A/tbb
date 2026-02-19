# TBB Veri Platformu - API Endpoint Dokumantasyonu

Base URL: `http://localhost:3000/api` (Nginx proxy) veya `http://localhost:8000/api` (dogrudan FastAPI)

Toplam **38 endpoint** - tumu GET metodu kullanir.

---

## Saglik Kontrolu

### `GET /health`

Uygulamanin calisip calismadigini kontrol eder.

**Yanit**: `{"status": "ok"}`

---

## Financial (Mali Tablolar)

Prefix: `/api/financial`
Veri Kaynagi: ClickHouse `tbb.financial_statements`
Cache TTL: 1 saat

### `GET /api/financial/statements`

Finansal tablo kayitlarini filtreli ve sayfalanmis olarak getirir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Hayir | - | Yil filtresi (ornek: 2025) |
| month | int | Hayir | - | Ay filtresi (ornek: 9) |
| bank_name | string | Hayir | - | Banka adi (tam eslesme) |
| accounting_system | string | Hayir | - | Muhasebe sistemi (LIKE filtre: SOLO, KONSOLİDE) |
| main_statement | string | Hayir | - | Ana kalem (ornek: "1. VARLIKLAR") |
| child_statement | string | Hayir | - | Alt kalem (ornek: "XI. VARLIKLAR TOPLAMI") |
| limit | int | Hayir | 100 | Sayfa basi kayit (1-1000) |
| offset | int | Hayir | 0 | Baslangic kayit indeksi |

**Yanit**:
```json
{
  "data": [
    {
      "accounting_system": "TFRS9-SOLO-BANKALARCA KAMUYA ACIKLANACAK...",
      "main_statement": "1. VARLIKLAR",
      "child_statement": "XI. VARLIKLAR TOPLAMI",
      "bank_name": "Ziraat Bankasi A.S.",
      "year_id": 2025,
      "month_id": 9,
      "amount_tc": 1234567890.12,
      "amount_fc": 987654321.00,
      "amount_total": 2222222211.12
    }
  ],
  "total": 802103,
  "limit": 100,
  "offset": 0
}
```

---

### `GET /api/financial/summary`

Ana kalem bazinda toplam tutarlarin ozetini getirir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Hayir | - | Yil filtresi |
| metric | string | Hayir | - | Metrik filtresi |
| accounting_system | string | Hayir | - | Muhasebe sistemi (LIKE filtre) |

**Yanit**:
```json
[
  { "metric": "1. VARLIKLAR", "total": 98765432100.50, "count": 12500 },
  { "metric": "2. YUKUMLULUKLER", "total": 87654321000.25, "count": 11000 }
]
```

---

### `GET /api/financial/periods`

Mevcut donem (yil/ay) kombinasyonlarini getirir.

**Parametre**: Yok

**Yanit**:
```json
[
  { "year_id": 2025, "month_id": 9 },
  { "year_id": 2025, "month_id": 6 },
  { "year_id": 2025, "month_id": 3 }
]
```

---

### `GET /api/financial/bank-names`

Finansal tablolardaki benzersiz banka isimlerini getirir.

**Parametre**: Yok

**Yanit**:
```json
["Akbank T.A.S.", "Denizbank A.S.", "Garanti BBVA Bankasi A.S.", "..."]
```

---

### `GET /api/financial/main-statements`

Benzersiz ana kalem isimlerini getirir.

**Parametre**: Yok

**Yanit**:
```json
["1. VARLIKLAR", "2. YUKUMLULUKLER", "3. BILANCODISI YUKUMLULUKLER", "4. GELIR-GIDER TABLOSU"]
```

---

### `GET /api/financial/child-statements`

Alt kalem isimlerini getirir. Istege bagli olarak ana kaleme gore filtrelenir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| main_statement | string | Hayir | - | Ana kalem filtresi |

**Yanit**:
```json
["2.1. Krediler", "2.5 Beklenen Zarar Karsiliklari (-) (TFRS 9 uygulayan b.)", "..."]
```

---

### `GET /api/financial/ratio-types`

Hesaplanabilen finansal oran tiplerinin tanimlarini getirir.

**Parametre**: Yok

**Yanit**:
```json
[
  { "key": "ROA", "label": "ROA (Aktif Karliligi) %", "desc": "Net Kar / Toplam Aktif" },
  { "key": "ROE", "label": "ROE (Ozkaynak Karliligi) %", "desc": "Net Kar / Ozkaynaklar" },
  { "key": "NIM", "label": "NIM (Net Faiz Marji) %", "desc": "Net Faiz Geliri / Toplam Aktif" },
  { "key": "PROVISION", "label": "Karsilik Orani %", "desc": "Beklenen Zarar Karsiliklari / Toplam Kredi" },
  { "key": "LEVERAGE", "label": "Kaldirac (Ozkaynak/Aktif) %", "desc": "Ozkaynaklar / Toplam Aktif" },
  { "key": "FX_SHARE", "label": "YP Aktif Payi %", "desc": "YP Aktifler / Toplam Aktif" }
]
```

---

### `GET /api/financial/ratios`

Belirli bir donem icin banka bazinda 6 finansal orani hesaplayip getirir. Aggregate kategoriler (Turkiye Bankacilik Sistemi, Mevduat Bankalari vb.) haric tutulur.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Evet | - | Yil |
| month | int | Evet | - | Ay |
| accounting_system | string | Hayir | - | Muhasebe sistemi (LIKE filtre) |

**Yanit**:
```json
[
  {
    "bank_name": "Turkiye Cumhuriyeti Ziraat Bankasi A.S.",
    "total_assets": 5123456789000.00,
    "ROA": 1.85,
    "ROE": 22.41,
    "NIM": 3.12,
    "PROVISION": 4.56,
    "LEVERAGE": 8.25,
    "FX_SHARE": 35.67
  }
]
```

**Hesaplama Detaylari**:
- `ROA` = Net Kar / Toplam Aktif * 100
- `ROE` = Net Kar / Ozkaynaklar * 100
- `NIM` = Net Faiz Geliri / Toplam Aktif * 100
- `PROVISION` = |Beklenen Zarar Karsiliklari| / Toplam Krediler * 100
- `LEVERAGE` = Ozkaynaklar / Toplam Aktif * 100
- `FX_SHARE` = YP Aktifler / Toplam Aktif * 100

---

### `GET /api/financial/time-series`

Belirli bir banka icin donemsel toplam tutarlari zaman serisi olarak getirir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| bank_name | string | Evet | - | Banka adi |
| statement | string | Hayir | - | Ana kalem filtresi |
| from_year | int | Hayir | - | Baslangic yili |
| to_year | int | Hayir | - | Bitis yili |
| accounting_system | string | Hayir | - | Muhasebe sistemi (LIKE filtre) |

**Yanit**:
```json
[
  { "year_id": 2025, "month_id": 3, "amount_total": 98765432100.50 },
  { "year_id": 2025, "month_id": 6, "amount_total": 101234567890.25 },
  { "year_id": 2025, "month_id": 9, "amount_total": 105678901234.75 }
]
```

---

## Regions (Bolgesel Istatistikler)

Prefix: `/api/regions`
Veri Kaynagi: ClickHouse `tbb.region_statistics`
Cache TTL: 6 saat

### `GET /api/regions/stats`

Bolgesel istatistik kayitlarini filtreli olarak getirir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| region | string | Hayir | - | Bolge adi |
| metric | string | Hayir | - | Metrik adi |
| year | int | Hayir | - | Yil filtresi |

**Yanit**:
```json
[
  { "region": "Istanbul", "metric": "Tasarruf Mevduati", "year_id": 2024, "value": 1234567890.50 }
]
```

---

### `GET /api/regions/periods`

Bolgesel veriler icin mevcut yillari getirir.

**Parametre**: Yok

**Yanit**:
```json
[{ "year_id": 2024 }, { "year_id": 2023 }, { "year_id": 2022 }]
```

---

### `GET /api/regions/list`

Benzersiz bolge isimlerini getirir.

**Parametre**: Yok

**Yanit**:
```json
["Adana", "Ankara", "Antalya", "Istanbul", "Izmir", "..."]
```

---

### `GET /api/regions/metrics`

Mevcut bolgesel metrikleri getirir.

**Parametre**: Yok

**Yanit**:
```json
["Tasarruf Mevduati", "Bankalar Mevduati", "Iht.Disi Krediler", "..."]
```

---

### `GET /api/regions/loan-deposit-ratio`

Bolgesel kredi/mevduat oranini hesaplar. 7 kredi bileseni ve 7 mevduat bileseni kullanir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Evet | - | Yil |

**Haric tutulan bolgeler**: Tum Bolgeler, Yabanci Ulkeler, Iller Bankasi, Kibris

**Yanit**:
```json
[
  { "region": "Istanbul", "ratio": 1.45, "total_credit": 9876543210, "total_deposit": 6811064283 },
  { "region": "Ankara", "ratio": 0.92, "total_credit": 3456789012, "total_deposit": 3757379361 }
]
```

---

### `GET /api/regions/credit-hhi`

Bolgesel bazda kredi sektorel yogunlasma (HHI) endeksini hesaplar. 6 ihtisas kredi sektoru uzerinden.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Evet | - | Yil |

**Hesaplama**: `HHI = SUM(sektor_payi_yuzde ^ 2)` her sektor icin

**Yanit**:
```json
[
  {
    "region": "Antalya",
    "hhi": 3250,
    "dominant_sector": "Turizm",
    "shares": {
      "Denizcilik": 2.1,
      "Diger": 15.3,
      "Gayrimenkul": 12.7,
      "Mesleki": 8.4,
      "Tarim": 5.2,
      "Turizm": 56.3
    }
  }
]
```

**HHI Yorumlama**:
- < 1500: Dusuk yogunlasma
- 1500-2500: Orta yogunlasma
- > 2500: Yuksek yogunlasma

---

### `GET /api/regions/comparison`

Belirli bir metrik ve yil icin tum bolgeleri karsilastirir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| metric | string | Evet | - | Metrik adi |
| year | int | Evet | - | Yil |

**Yanit**:
```json
[
  { "region": "Istanbul", "value": 9876543210.50 },
  { "region": "Ankara", "value": 3456789012.25 }
]
```

---

## Risk Center (Risk Merkezi)

Prefix: `/api/risk-center`
Veri Kaynagi: ClickHouse `tbb.risk_center`
Cache TTL: 6 saat

### `GET /api/risk-center/data`

Risk merkezi kayitlarini filtreli olarak getirir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| report_name | string | Hayir | - | Rapor adi |
| category | string | Hayir | - | Kategori adi |
| year | int | Hayir | - | Yil filtresi |
| month | int | Hayir | - | Ay filtresi |

**Yanit**:
```json
[
  {
    "report_name": "Bireysel Kredi Karti Istatistikleri",
    "category": "Kredi Karti Toplam Borc Bakiyesi",
    "person_count": 45678901,
    "quantity": 67890123,
    "amount": 234567890123.45,
    "year_id": 2025,
    "month_id": 6
  }
]
```

---

### `GET /api/risk-center/periods`

Risk merkezi verileri icin mevcut donemleri getirir.

**Parametre**: Yok

**Yanit**:
```json
[
  { "year_id": 2025, "month_id": 6 },
  { "year_id": 2025, "month_id": 3 }
]
```

---

### `GET /api/risk-center/reports`

Mevcut rapor isimlerini getirir.

**Parametre**: Yok

**Yanit**:
```json
["Bireysel Kredi Karti Istatistikleri", "Ticari Kredi Istatistikleri", "..."]
```

---

### `GET /api/risk-center/categories`

Belirli bir rapor icin kategori isimlerini getirir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| report_name | string | Evet | - | Rapor adi |

**Yanit**:
```json
["Kredi Karti Toplam Borc Bakiyesi", "Kredi Karti Limit Tutari", "..."]
```

---

## Banks (Banka Bilgileri)

Prefix: `/api/banks`
Veri Kaynagi: PostgreSQL (`bank_info`, `branch_info`, `atm_info`, `historical_events`)
Cache TTL: 24 saat

### `GET /api/banks/`

Tum bankalarin bilgilerini getirir.

**Parametre**: Yok

**Yanit**:
```json
[
  {
    "bank_group": "Mevduat Bankalari",
    "sub_bank_group": "Kamusal Sermayeli Mevduat Bankalari",
    "bank_name": "Turkiye Cumhuriyeti Ziraat Bankasi A.S.",
    "address": "...",
    "board_president": "...",
    "general_manager": "...",
    "phone_fax": "...",
    "web_kep_address": "...",
    "eft": "0010",
    "swift": "TCZBTR2A"
  }
]
```

---

### `GET /api/banks/dashboard-stats`

Dashboard icin toplam sube/ATM sayilari ve illere gore dagilim istatistiklerini getirir.

**Parametre**: Yok

**Yanit**:
```json
{
  "total_branches": 9087,
  "total_atms": 49958,
  "branch_by_city": [
    { "city": "Istanbul", "count": 2845 },
    { "city": "Ankara", "count": 987 }
  ],
  "atm_by_city": [
    { "city": "Istanbul", "count": 12345 },
    { "city": "Ankara", "count": 4567 }
  ]
}
```

**Not**: branch_by_city ve atm_by_city en fazla 15 il icerir (Top 15).

---

### `GET /api/banks/search`

Banka ismine gore arama yapar (buyuk/kucuk harf duyarsiz).

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| q | string | Evet | - | Arama sorgusu (min 1 karakter) |

**Yanit**: Banka listesi (ayni format: `GET /api/banks/`)

---

### `GET /api/banks/{bank_name}/branches`

Belirli bir bankanin subelerini getirir. Istege bagli olarak sehre gore filtrelenir.

| Parametre | Tip | Konum | Zorunlu | Aciklama |
|-----------|-----|-------|---------|----------|
| bank_name | string | Path | Evet | Banka adi (URL encoded) |
| city | string | Query | Hayir | Sehir filtresi |

**Yanit**:
```json
[
  {
    "bank_name": "Ziraat Bankasi A.S.",
    "branch_name": "Ulus Subesi",
    "address": "...",
    "district": "Altindag",
    "city": "Ankara",
    "phone": "0312 ...",
    "fax": "0312 ...",
    "opening_date": "1990-05-15"
  }
]
```

---

### `GET /api/banks/{bank_name}/atms`

Belirli bir bankanin ATM'lerini getirir. Istege bagli olarak sehre gore filtrelenir.

| Parametre | Tip | Konum | Zorunlu | Aciklama |
|-----------|-----|-------|---------|----------|
| bank_name | string | Path | Evet | Banka adi (URL encoded) |
| city | string | Query | Hayir | Sehir filtresi |

**Yanit**:
```json
[
  {
    "bank_name": "Ziraat Bankasi A.S.",
    "branch_name": "Ulus ATM",
    "address": "...",
    "district": "Altindag",
    "city": "Ankara"
  }
]
```

---

### `GET /api/banks/{bank_name}/history`

Belirli bir bankanin kurulus tarihi ve tarihce bilgisini getirir.

| Parametre | Tip | Konum | Zorunlu | Aciklama |
|-----------|-----|-------|---------|----------|
| bank_name | string | Path | Evet | Banka adi (URL encoded) |

**Yanit**:
```json
{
  "bank_name": "Turkiye Cumhuriyeti Ziraat Bankasi A.S.",
  "founding_date": "1863-11-20",
  "historical_event": "..."
}
```

---

## Liquidity (Likidite Analizi)

Prefix: `/api/liquidity`
Veri Kaynagi: ClickHouse `tbb.financial_statements` + PostgreSQL `bank_info`
Cache TTL: 1 saat
Metodoloji: Colak, Deniz, Korkmaz & Yilmaz (2024), "A Panorama of Liquidity Creation in Turkish Banking Industry", TCMB Working Paper 24/09

### `GET /api/liquidity/creation`

Belirli bir donem icin banka bazinda likidite yaratimi (LC) oranlarini hesaplar. Kalkinma/yatirim bankalari ve sektor aggregate satirlari haric tutulur.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Evet | - | Yil |
| month | int | Evet | - | Ay |
| accounting_system | string | Hayir | - | Muhasebe sistemi (SOLO, KONSOLİDE). Bos ise SOLO tercih edilir, sadece konsolide verisi olan bankalar icin KONSOLİDE kullanilir |

**LC Hesaplama Formulu (Cat Nonfat - bilanco ici)**:
```
LC_nonfat = [0.5*(Likit Olmayan Varliklar + Likit Yukumlulukler) + 0.0*(Yari Likit) - 0.5*(Likit Varliklar + Likit Olmayan Yuk. + Ozkaynak)] / Toplam Aktif
```

**LC Hesaplama Formulu (Cat Fat - bilanco disi dahil)**:
```
LC_fat = LC_nonfat_numerator + 0.5*(Likit Olmayan Nazim Hesaplar) / Toplam Aktif
```

**Yanit**:
```json
[
  {
    "bank_name": "Akbank T.A.S.",
    "lc_nonfat": 0.3245,
    "lc_fat": 0.2890,
    "lc_ratio": 0.3245,
    "liquid_assets": 150000000000,
    "semi_liquid_assets": 25000000000,
    "illiquid_assets": 800000000000,
    "liquid_liabilities": 600000000000,
    "semi_liquid_liabilities": 30000000000,
    "illiquid_liabilities_equity": 200000000000,
    "illiquid_obs": 120000000000,
    "semi_liquid_obs": 50000000000,
    "total_assets": 1250000000000
  }
]
```

---

### `GET /api/liquidity/time-series`

LC zaman serisi. Banka adi verilmezse sektor agirlikli ortalamasini dondurur.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| bank_name | string | Hayir | - | Banka adi (bos ise sektor ortalamasi) |
| from_year | int | Hayir | - | Baslangic yili |
| to_year | int | Hayir | - | Bitis yili |
| accounting_system | string | Hayir | - | Muhasebe sistemi |

**Yanit**:
```json
[
  { "year_id": 2025, "month_id": 3, "lc_nonfat": 0.3120, "lc_fat": 0.2780, "lc_ratio": 0.3120 },
  { "year_id": 2025, "month_id": 6, "lc_nonfat": 0.3180, "lc_fat": 0.2830, "lc_ratio": 0.3180 },
  { "year_id": 2025, "month_id": 9, "lc_nonfat": 0.3245, "lc_fat": 0.2890, "lc_ratio": 0.3245 }
]
```

---

### `GET /api/liquidity/groups`

Banka sahiplik grubuna gore agirlikli ortalama LC orani.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Evet | - | Yil |
| month | int | Evet | - | Ay |
| accounting_system | string | Hayir | - | Muhasebe sistemi |

**Yanit**:
```json
[
  { "group_name": "Kamusal Sermayeli Mevduat Bankalari", "lc_nonfat": 0.2850, "lc_fat": 0.2500, "lc_ratio": 0.2850, "bank_count": 3 },
  { "group_name": "Ozel Sermayeli Mevduat Bankalari", "lc_nonfat": 0.3100, "lc_fat": 0.2750, "lc_ratio": 0.3100, "bank_count": 7 }
]
```

---

### `GET /api/liquidity/group-time-series`

Grup bazli (Kamusal / Ozel / Yabanci) LC zaman serisi. Colak et al. (2024) Figure 2 icin.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| accounting_system | string | Hayir | - | Muhasebe sistemi |

**Yanit**:
```json
[
  { "group_name": "Kamusal", "year_id": 2025, "month_id": 9, "lc_nonfat": 0.2850 },
  { "group_name": "Ozel", "year_id": 2025, "month_id": 9, "lc_nonfat": 0.3100 },
  { "group_name": "Yabanci", "year_id": 2025, "month_id": 9, "lc_nonfat": 0.2200 }
]
```

---

### `GET /api/liquidity/decomposition`

Tek bir banka icin LC bilesen analizi. Pozitif katki yapan (likit olmayan varliklar, likit yukumlulukler) ve negatif katki yapan (likit varliklar, likit olmayan yuk. + ozkaynak) bilesenleri ayristirir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| bank_name | string | Evet | - | Banka adi |
| year | int | Evet | - | Yil |
| month | int | Evet | - | Ay |
| accounting_system | string | Hayir | - | Muhasebe sistemi |

**Yanit**:
```json
{
  "bank_name": "Akbank T.A.S.",
  "lc_nonfat": 0.3245,
  "lc_fat": 0.2890,
  "lc_ratio": 0.3245,
  "total_assets": 1250000000000,
  "components": {
    "liquid_assets": 150000000000,
    "semi_liquid_assets": 25000000000,
    "illiquid_assets": 800000000000,
    "liquid_liabilities": 600000000000,
    "semi_liquid_liabilities": 30000000000,
    "illiquid_liabilities_equity": 200000000000,
    "illiquid_obs": 120000000000,
    "semi_liquid_obs": 50000000000
  },
  "weighted_components": {
    "illiquid_assets_contrib": 0.3200,
    "liquid_liabilities_contrib": 0.2400,
    "liquid_assets_drag": -0.0600,
    "illiquid_liab_equity_drag": -0.0800,
    "illiquid_obs_contrib": 0.0480
  }
}
```

---

## Risk Analysis (Risk Analizi)

Prefix: `/api/risk-analysis`
Veri Kaynagi: ClickHouse `tbb.financial_statements`
Cache TTL: 1 saat
Metodoloji: Colak et al. (2024), Section IV.III "Bank Risk"

### `GET /api/risk-analysis/zscore`

Belirli bir donem icin tum bankalarin Z-Score siralamasi.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Evet | - | Yil |
| month | int | Evet | - | Ay |
| accounting_system | string | Hayir | - | Muhasebe sistemi (varsayilan SOLO) |

**Z-Score Hesaplama**:
```
Z-Score = (Sermaye Orani + ROA) / sigma(ROA)

Sermaye Orani = Ozkaynaklar / Toplam Aktif
ROA = Net Kar / Toplam Aktif
sigma(ROA) = 12 donemlik yuvarlanir pencere standart sapma
```
Yuksek Z-Score = dusuk risk (iflastan uzak mesafe).

**Yanit**:
```json
[
  {
    "bank_name": "Akbank T.A.S.",
    "z_score": 45.6789,
    "roa": 1.85,
    "capital_ratio": 12.50,
    "roa_std": 0.3125,
    "total_assets": 1250000000000,
    "equity": 156250000000,
    "net_income": 23125000000
  }
]
```

---

### `GET /api/risk-analysis/zscore-time-series`

Z-Score zaman serisi. Banka adi verilmezse tum bankalarin serisini dondurur.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| bank_name | string | Hayir | - | Banka adi (bos ise tum bankalar) |
| accounting_system | string | Hayir | - | Muhasebe sistemi |

**Yanit**:
```json
[
  { "bank_name": "Akbank T.A.S.", "year_id": 2025, "month_id": 9, "z_score": 45.67, "roa": 1.85, "capital_ratio": 12.50 }
]
```

---

### `GET /api/risk-analysis/lc-risk`

Likidite yaratimi (LC) ile banka riski (Z-Score) arasindaki iliskiyi gosteren veri. Sacilim grafigi icin kullanilir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Evet | - | Yil |
| month | int | Evet | - | Ay |
| accounting_system | string | Hayir | - | Muhasebe sistemi |

**Yanit**:
```json
[
  {
    "bank_name": "Akbank T.A.S.",
    "z_score": 45.67,
    "lc_nonfat": 0.3245,
    "roa": 1.85,
    "capital_ratio": 12.50,
    "total_assets": 1250000000000,
    "bank_group": "Ozel"
  }
]
```

---

## Panel Regression (Panel Regresyon)

Prefix: `/api/panel-regression`
Veri Kaynagi: ClickHouse `tbb.financial_statements`
Cache TTL: 1 saat
Metodoloji: Colak et al. (2024) - Cross-sectional OLS (2025/9 donemi)

### `GET /api/panel-regression/results`

Uc regresyon modelinin sonuclarini, tanimlayici istatistikleri ve banka bazli verileri dondurur.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| accounting_system | string | Hayir | - | Muhasebe sistemi |

**Modeller**:

| Model | Bagimli Degisken | Bagimsiz Degiskenler | Denklem |
|-------|-------------------|---------------------|---------|
| capital_adequacy_lc | LC (Cat Nonfat) | Sermaye Yeterliligi, Banka Buyuklugu (ln), ROA | Eq. 2 |
| lc_bank_risk | Z-Score (Risk) | LC Orani, Banka Buyuklugu (ln), ROA | Eq. 5 |
| state_ownership_lc | LC (Cat Nonfat) | Kamu Sahipligi (dummy), Banka Buyuklugu (ln), ROA | Eq. 4 |

**Degisken Tanimlari**:
- `capital_adequacy`: Ozkaynak / Toplam Aktif - 0.08 (%8 esik degeri uzerindeki fazla)
- `bank_size`: ln(Toplam Aktif)
- `state`: Kamu bankasi = 1, diger = 0

**Yanit**:
```json
{
  "models": {
    "capital_adequacy_lc": {
      "title": "Sermaye Yeterliligi → Likidite Yaratimi (Eq. 2)",
      "dependent": "LC (Cat Nonfat)",
      "method": "OLS",
      "r_squared": 0.45,
      "adj_r_squared": 0.39,
      "n_obs": 33,
      "f_stat": 7.85,
      "f_pvalue": 0.0005,
      "coefficients": [
        {
          "variable": "Sabit",
          "coefficient": 0.8500,
          "std_error": 0.3200,
          "t_stat": 2.65,
          "p_value": 0.013,
          "significant": true
        },
        {
          "variable": "capital_adequacy",
          "coefficient": -0.0023,
          "std_error": 0.001,
          "t_stat": -2.30,
          "p_value": 0.027,
          "significant": true
        }
      ]
    }
  },
  "descriptive_stats": {
    "lc_nonfat": { "mean": 0.25, "std": 0.08, "min": 0.05, "max": 0.42, "count": 33 }
  },
  "panel_info": {
    "n_banks": 33,
    "n_periods": 1,
    "total_obs": 33,
    "periods": ["2025_9"]
  },
  "bank_data": [
    {
      "bank_name": "Akbank T.A.S.",
      "capital_adequacy": 0.045,
      "lc_nonfat": 0.3245,
      "z_score": 45.67,
      "roa": 0.0185,
      "bank_size": 27.85,
      "state": 0,
      "bank_group": "Ozel"
    }
  ]
}
```

---

## Regional Liquidity (Bolgesel Likidite)

Prefix: `/api/regional-liquidity`
Veri Kaynagi: ClickHouse `tbb.financial_statements` + PostgreSQL `branch_info`
Cache TTL: 1 saat

### `GET /api/regional-liquidity/distribution`

Il bazinda likidite yaratimi dagitimi. Her bankanin LC tutari, o bankanin sube dagilimina oranla illere dagitilir.

| Parametre | Tip | Zorunlu | Varsayilan | Aciklama |
|-----------|-----|---------|-----------|----------|
| year | int | Evet | - | Yil |
| month | int | Evet | - | Ay |
| accounting_system | string | Hayir | - | Muhasebe sistemi |

**Hesaplama Yontemi**:
```
il_LC += banka_LC * (banka_il_sube_sayisi / banka_toplam_sube_sayisi)

banka_LC = lc_nonfat * total_assets
```

Sadece LC hesaplanabilen (ClickHouse'da verisi olan) bankalar sube/banka sayisina dahil edilir.

**Yanit**:
```json
[
  {
    "city": "ISTANBUL",
    "lc_amount": 4600000000.50,
    "branch_count": 3200,
    "bank_count": 33,
    "avg_lc_ratio": 0.285
  },
  {
    "city": "ANKARA",
    "lc_amount": 1800000000.25,
    "branch_count": 1200,
    "bank_count": 30,
    "avg_lc_ratio": 0.270
  }
]
```

---

## Endpoint Ozet Tablosu

| # | Metod | Endpoint | Zorunlu Parametre | Aciklama |
|---|-------|----------|-------------------|----------|
| 1 | GET | /health | - | Saglik kontrolu |
| 2 | GET | /api/financial/statements | - | Mali tablo kayitlari (sayfalanmis) |
| 3 | GET | /api/financial/summary | - | Ana kalem bazinda ozet |
| 4 | GET | /api/financial/periods | - | Mevcut donemler |
| 5 | GET | /api/financial/bank-names | - | Banka isimleri |
| 6 | GET | /api/financial/main-statements | - | Ana kalem isimleri |
| 7 | GET | /api/financial/child-statements | - | Alt kalem isimleri |
| 8 | GET | /api/financial/ratio-types | - | Oran tipi tanimlari |
| 9 | GET | /api/financial/ratios | year, month | Banka bazinda finansal oranlar |
| 10 | GET | /api/financial/time-series | bank_name | Zaman serisi verisi |
| 11 | GET | /api/regions/stats | - | Bolgesel istatistikler |
| 12 | GET | /api/regions/periods | - | Mevcut yillar |
| 13 | GET | /api/regions/list | - | Bolge listesi |
| 14 | GET | /api/regions/metrics | - | Metrik listesi |
| 15 | GET | /api/regions/loan-deposit-ratio | year | Kredi/mevduat orani |
| 16 | GET | /api/regions/credit-hhi | year | Sektorel yogunlasma endeksi |
| 17 | GET | /api/regions/comparison | metric, year | Bolgesel karsilastirma |
| 18 | GET | /api/risk-center/data | - | Risk merkezi kayitlari |
| 19 | GET | /api/risk-center/periods | - | Mevcut donemler |
| 20 | GET | /api/risk-center/reports | - | Rapor listesi |
| 21 | GET | /api/risk-center/categories | report_name | Kategori listesi |
| 22 | GET | /api/banks/ | - | Tum bankalar |
| 23 | GET | /api/banks/dashboard-stats | - | Sube/ATM istatistikleri |
| 24 | GET | /api/banks/search | q | Banka arama |
| 25 | GET | /api/banks/{bank_name}/branches | bank_name | Sube listesi |
| 26 | GET | /api/banks/{bank_name}/atms | bank_name | ATM listesi |
| 27 | GET | /api/banks/{bank_name}/history | bank_name | Banka tarihcesi |
| 28 | GET | /api/liquidity/creation | year, month | Banka bazli LC oranlari |
| 29 | GET | /api/liquidity/time-series | - | LC zaman serisi |
| 30 | GET | /api/liquidity/groups | year, month | Grup bazli LC |
| 31 | GET | /api/liquidity/group-time-series | - | Grup LC zaman serisi |
| 32 | GET | /api/liquidity/decomposition | bank_name, year, month | LC bilesen analizi |
| 33 | GET | /api/risk-analysis/zscore | year, month | Z-Score siralamasi |
| 34 | GET | /api/risk-analysis/zscore-time-series | - | Z-Score zaman serisi |
| 35 | GET | /api/risk-analysis/lc-risk | year, month | LC vs Risk iliskisi |
| 36 | GET | /api/panel-regression/results | - | Panel regresyon sonuclari |
| 37 | GET | /api/regional-liquidity/distribution | year, month | Il bazli LC dagitimi |
