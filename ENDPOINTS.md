# TBB Veri Platformu - API Endpoint Dokumantasyonu

Base URL: `http://localhost:3000/api` (Nginx proxy) veya `http://localhost:8000/api` (dogrudan FastAPI)

Toplam **28 endpoint** - tumu GET metodu kullanir.

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
