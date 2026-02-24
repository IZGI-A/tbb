# TBB Veri Platformu - Sistem Mimarisi

Turkiye Bankalar Birligi (TBB) kamuya acik verilerini scrape eden, donusturup analitik veritabanlarina yukleyen ve web arayuzu uzerinden gorsellestiren uctan uca bir veri platformu.

---

## 1. Sistem Genel Gorunumu

Sistem yukaridan asagiya tek bir dikey akis seklinde okunur.

```
                    ┌─────────────────────────┐
                    │    TBB Web Siteleri     │
                    │    tbb.org.tr           │
                    │    verisistemi.tbb.org  │
                    └────────────┬────────────┘
                                 │
                                 │  Selenium (Headless Chrome)
                                 v
                    ┌─────────────────────────┐
                    │    Airflow Scheduler    │
                    │    :8080                │
                    │                         │
                    │   4 Scraper:            │
                    │   - Financial (haftalik)│
                    │   - BankInfo  (aylik)   │
                    │   - Region   (aylik)    │
                    │   - RiskCenter(aylik)   │
                    └────────────┬────────────┘
                                 │
                                 │  JSON → Transform → Load
                                 v
              ┌──────────────────────────────────────┐
              │           VERITABANLARI              │
              │                                      │
              │   PostgreSQL :5432   ClickHouse :9000│
              │   ┌──────────────┐   ┌─────────────┐ │
              │   │ bank_info    │   │ financial_  │ │
              │   │ branch_info  │   │  statements │ │
              │   │ atm_info     │   │ region_     │ │
              │   │ historical_  │   │  statistics │ │
              │   │  events      │   │ risk_center │ │
              │   └──────────────┘   └─────────────┘ │
              └──────────────────┬───────────────────┘
                                 │
                                 │  read
                                 v
                    ┌─────────────────────────┐
                    │    FastAPI  :8000       │
                    │    37 REST endpoint     │
                    │                         │
                    │    Redis :6379 (cache)  │
                    └────────────┬────────────┘
                                 │
                                 │  /api/* proxy
                                 v
                    ┌─────────────────────────┐
                    │    Nginx + React SPA    │
                    │    :3000                │
                    │                         │
                    │    10 Sayfa:            │
                    │    - Dashboard          │
                    │    - Mali Tablolar      │
                    │    - Bolgesel Ist.      │
                    │    - Risk Merkezi       │
                    │    - Banka Rehberi      │
                    │    - Likidite Analizi   │
                    │    - Bolgesel Likidite  │
                    │    - Banka Karsilast.   │
                    │    - Risk Analizi       │
                    │    - Panel Regresyon    │
                    └────────────┬────────────┘
                                 │
                                 v
                    ┌─────────────────────────┐
                    │      Kullanici          │
                    │      (Web Tarayici)     │
                    └─────────────────────────┘
```

---

## 2. Docker Servis Mimarisi

7 container, Docker Compose ile orkestre edilir.

```
  ┌─────────────────────── ALTYAPI ────────────────────────┐
  │                                                        │
  │  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐ │
  │  │  PostgreSQL   │  │  ClickHouse  │  │    Redis     │ │
  │  │  :5432        │  │  :9000/:8123 │  │    :6379     │ │
  │  │  postgres:16  │  │  ch:24.1     │  │  redis:7     │ │
  │  └──────┬────────┘  └──────┬───────┘  └──────┬───────┘ │
  └─────────┼──────────────────┼─────────────────┼─────────┘
            |                  |                 |
            v                  v                 v
  ┌──────── UYGULAMA ───────────────────────────────────┐
  │                                                      │
  │  ┌──────────────┐  ┌──────────────┐                  │
  │  │   Airflow     │  │   Airflow     │                 │
  │  │  Webserver    │  │  Scheduler    │                 │
  │  │  :8080        │  │  (cron jobs)  │                 │
  │  └──────────────┘  └──────────────┘                  │
  │                                                      │
  │  ┌──────────────┐      ┌──────────────┐              │
  │  │   FastAPI     │ ───> │   Frontend   │              │
  │  │   :8000       │      │ Nginx :3000  │              │
  │  └──────────────┘      └──────────────┘              │
  └──────────────────────────────────────────────────────┘
```

| Servis | Image | Port | Amac |
|--------|-------|------|------|
| **postgres** | postgres:16-alpine | 5432 | Yapisal veri (bankalar, subeler, ATM'ler) |
| **clickhouse** | clickhouse/clickhouse-server:24.1 | 8123, 9000 | Buyuk hacimli analitik veri |
| **redis** | redis:7-alpine | 6379 | API onbellekleme katmani |
| **airflow-webserver** | Custom (Airflow 2.8.1 + Python 3.11) | 8080 | DAG izleme ve yonetim arayuzu |
| **airflow-scheduler** | Custom (Airflow 2.8.1 + Python 3.11) | - | Gorev zamanlama ve calistirma |
| **fastapi** | Custom (Python 3.12-slim) | 8000 | REST API sunucusu |
| **frontend** | Custom (Node 20 build + Nginx) | 3000 | Web arayuzu (SPA) |

### Volume'lar
- `postgres-data`: PostgreSQL veritabani dosyalari
- `clickhouse-data`: ClickHouse veritabani dosyalari
- `redis-data`: Redis snapshot dosyalari

### Saglik Kontrolleri
- PostgreSQL: `pg_isready`
- ClickHouse: `clickhouse-client --query "SELECT 1"`
- Redis: `redis-cli ping`

---

## 3. Veri Akisi (Data Flow)

4 bagimsiz ETL pipeline'i. Her biri ayni pattern'i izler:

```
  Kaynak Site ──> Scraper ──> JSON Staging ──> Transformer ──> Loader ──> Veritabani
```

### Pipeline 1: Finansal Tablolar (Haftalik)

```
  verisistemi.tbb.org.tr/report_mali
          |
          v
  FinancialScraper (Selenium)
  - Solo tablosu (index 0)
  - Konsolide tablosu (index 1)
  - 6 banka grubu, 5'li batch
          |
          v
  /tmp/tbb_staging/financial/raw_solo_*.json
  /tmp/tbb_staging/financial/raw_consolidated_*.json
          |
          v
  transform_financial()
  - Muhasebe sistemi cikarma
  - Ana/alt kalem hiyerarsi esleme
  - Turkce tutar ayristirma (TP/YP/Toplam)
  - Yil/ay cikarma
          |
          v
  load_financial_statements()  ──>  ClickHouse: tbb.financial_statements
  (Batch 10K satir)                  (~800K satir)
```

### Pipeline 2: Banka Bilgileri (Aylik)

```
  tbb.org.tr/bankalarimiz + /subeler
          |
          v
  BankInfoScraper (Selenium)
  - Banka listesi (grup, alt grup, iletisim)
  - Sube listesi (Drupal AJAX)
  - ATM listesi (Drupal AJAX)
          |
          v
  /tmp/tbb_staging/bank_info/raw_*.json
          |
          v
  transform_bank_info()
  - Tablo formati donusumu
  - Turkce tarih ayristirma (dd.mm.yyyy)
          |
          v
  load_all_bank_data()  ──>  PostgreSQL: bank_info, branch_info,
  (UPSERT)                               atm_info, historical_events
```

### Pipeline 3: Bolgesel Istatistikler (Aylik)

```
  verisistemi.tbb.org.tr/report_bolgeler
          |
          v
  RegionScraper (Selenium)
  - 96 bolge/il
  - Son 3 yil, tum metrikler
          |
          v
  /tmp/tbb_staging/regions/raw_*.json
          |
          v
  transform_regions()
  - Bolge/metrik cikarma
  - Deger ayristirma
          |
          v
  load_region_statistics()  ──>  ClickHouse: tbb.region_statistics
  (Batch 10K satir)
```

### Pipeline 4: Risk Merkezi (Aylik)

```
  verisistemi.tbb.org.tr/report_rm
          |
          v
  RiskCenterScraper (Selenium)
  - Tum raporlar uzerinde iterasyon
  - Kategoriler, ilk 3 donem
  - KISI/ADET/TUTAR flag'lari
          |
          v
  /tmp/tbb_staging/risk_center/raw_*.json
          |
          v
  transform_risk_center()
  - Rapor/kategori cikarma
  - Kisi/adet/tutar ayristirma
          |
          v
  load_risk_center()  ──>  ClickHouse: tbb.risk_center
  (Batch 10K satir)
```

---

## 4. Airflow DAG Gorev Akislari

### Finansal (Haftalik - Pazartesi 06:00 UTC)

Solo ve konsolide sirayla calisir (ayni anda ikisi birden Chrome bellek tasmasi yapar).

```
  scrape_solo ──> transform_solo ──> load_solo ──> scrape_consolidated ──> transform_consolidated ──> load_consolidated
```

### Diger DAG'lar (Aylik - Her ayin 1'i 06:00 UTC)

```
  tbb_bank_info:          scrape_banks ──> transform ──> load_postgres
  tbb_region_statistics:  scrape_data  ──> transform ──> load_clickhouse
  tbb_risk_center:        scrape_data  ──> transform ──> load_clickhouse
```

Ortak ozellikler:
- **Retry politikasi**: 2 tekrar, 5 dakika aralik, 2 saat timeout
- **Staging dizini**: `/tmp/tbb_staging/{pipeline}/`
- **catchup**: False (geriye donuk calistirma kapali)

---

## 5. Veritabani Yapilari

### PostgreSQL (Yapisal Veri)

```
  ┌────────────────────────────────────────────────┐
  │                  bank_info                     │
  │  PK: bank_name                                 │
  │────────────────────────────────────────────────│
  │  bank_group          VARCHAR(150)              │
  │  sub_bank_group      VARCHAR(150)              │
  │  bank_name           VARCHAR(200)  PK          │
  │  address             TEXT                      │
  │  board_president     VARCHAR(150)              │
  │  general_manager     VARCHAR(150)              │
  │  phone_fax           VARCHAR(100)              │
  │  web_kep_address     VARCHAR(250)              │
  │  eft                 VARCHAR(50)               │
  │  swift               VARCHAR(50)               │
  │  updated_at          TIMESTAMP                 │
  └──────┬──────────────────┬──────────────────────┘
         |                  |           
         | FK (CASCADE)     | FK           
         v                  v           
  ┌──────────────┐  ┌──────────────┐  
  │ branch_info  │  │   atm_info   │  
  │              │  │              │  
  │ PK: bank_name│  │ PK: bank_name│ 
  │   + branch_  │  │   + branch_  │  
  │     name     │  │     name     │  
  │              │  │   + address  │  
  │ address      │  │              │  
  │ district     │  │ district     │
  │ city  [IDX]  │  │ city  [IDX]  │
  │ phone, fax   │  │ phone, fax   │
  │ opening_date │  │ opening_date │
  └──────────────┘  └──────────────┘
```

### ClickHouse (Analitik Veri)

Tum tablolar **ReplacingMergeTree** motoru kullanir. Ayni kayit tekrar yuklendiginde `crawl_timestamp` ile eski versiyon silinir. Sorgularda `FINAL` keyword'u zorunlu.

```
  ┌─────────────────────────────────────────────────────────────┐
  │            tbb.financial_statements  (~800K satir)           │
  │─────────────────────────────────────────────────────────────│
  │  accounting_system   LowCardinality(String)  Solo/Konsolide │
  │  main_statement      LowCardinality(String)  Ana Kalem      │
  │  child_statement     LowCardinality(String)  Alt Kalem      │
  │  bank_name           LowCardinality(String)                 │
  │  year_id             UInt16                                 │
  │  month_id            UInt8                                  │
  │  amount_tc           Decimal128(2)           TP Tutar       │
  │  amount_fc           Decimal128(2)           YP Tutar       │
  │  amount_total        Decimal128(2)           Toplam         │
  │  crawl_timestamp     DateTime                               │
  │─────────────────────────────────────────────────────────────│
  │  PARTITION BY year_id                                       │
  │  ORDER BY (accounting_system, child_statement, bank_name,   │
  │            year_id, month_id, main_statement)               │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │          tbb.region_statistics                   │
  │─────────────────────────────────────────────────│
  │  region              LowCardinality(String)     │
  │  metric              LowCardinality(String)     │
  │  year_id             UInt16                     │
  │  value               Decimal128(2)              │
  │  crawl_timestamp     DateTime                   │
  │─────────────────────────────────────────────────│
  │  PARTITION BY year_id                           │
  │  ORDER BY (region, metric, year_id)             │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │              tbb.risk_center                     │
  │─────────────────────────────────────────────────│
  │  report_name         LowCardinality(String)     │
  │  category            LowCardinality(String)     │
  │  person_count        UInt64                     │
  │  quantity            UInt64                     │
  │  amount              Decimal128(2)              │
  │  year_id             UInt16                     │
  │  month_id            UInt8                      │
  │  crawl_timestamp     DateTime                   │
  │─────────────────────────────────────────────────│
  │  PARTITION BY year_id                           │
  │  ORDER BY (report_name, category,               │
  │            year_id, month_id)                    │
  └─────────────────────────────────────────────────┘
```

---

## 6. Backend API Katmani ve Servisler Arasi Iletisim

### Istek Akisi (Cache Mekanizmasi)

```
  Tarayici                Nginx         FastAPI        Redis         ClickHouse/PG
     |                    :3000          :8000         :6379
     |                      |              |             |
     |  GET /api/fin/ratios |              |             |
     |─────────────────────>|              |             |
     |                      |  proxy_pass  |             |
     |                      |─────────────>|             |
     |                      |              |  GET cache  |
     |                      |              |────────────>|
     |                      |              |             |
     |                      |              |<────────────|
     |                      |              |             |
     |              [Cache HIT]            |             |
     |                      |<─────────────|             |
     |<─────────────────────|  JSON (cached)             |
     |                      |              |             |
     |              [Cache MISS]           |             |              DB
     |                      |              |  SELECT ... |              |
     |                      |              |────────────────────────────>|
     |                      |              |<───────────────────────────|
     |                      |              |             |
     |                      |              |  SETEX TTL  |
     |                      |              |────────────>|
     |                      |<─────────────|             |
     |<─────────────────────|  JSON (fresh)              |
```

### Katmanli Mimari

```
  ┌──────────────────────────── ROUTER KATMANI ──────────────────────────────┐
  │                                                                          │
  │  financial.py     regions.py    risk_center.py   banks.py                │
  │  /api/financial/* /api/regions/* /api/risk-center /api/banks              │
  │  (9 endpoint)    (7 endpoint)  (4 endpoint)    (6 endpoint)              │
  │                                                                          │
  │  liquidity.py         risk_analysis.py    panel_regression.py            │
  │  /api/liquidity/*     /api/risk-analysis  /api/panel-regression          │
  │  (5 endpoint)         (3 endpoint)        (1 endpoint)                   │
  │                                                                          │
  │  regional_liquidity.py                                                   │
  │  /api/regional-liquidity                                                 │
  │  (1 endpoint)                                                            │
  └────────┬──────────────┬─────────────┬──────────────┬─────────────────────┘
           |              |             |              |
           v              v             v              v
  ┌──────────────────────────── SERVICE KATMANI ────────────────────────────┐
  │                                                                          │
  │  financial_service   region_service  risk_service  bank_service           │
  │  - get_statements    - get_stats     - get_data    - get_banks           │
  │  - get_summary       - get_ldr       - get_reports - get_branches        │
  │  - get_ratios        - get_hhi       - get_periods - get_atms            │
  │  - get_time_series   - get_comparison               - get_dashboard_stats│
  │  - get_periods       - get_metrics                  - search             │
  │  + 4 daha            + 2 daha                       + 1 daha             │
  │                                                                          │
  │  liquidity_service          risk_analysis_service                         │
  │  - get_liquidity_creation   - get_zscore_ranking                         │
  │  - get_liquidity_time_series- get_zscore_time_series                     │
  │  - get_liquidity_by_group   - get_lc_risk_relationship                   │
  │  - get_group_time_series                                                 │
  │  - get_decomposition        panel_regression_service                     │
  │                              - run_panel_regressions                     │
  │  regional_liquidity_service                                              │
  │  - get_regional_liquidity                                                │
  └────┬────────────┬─────────────────────────────────┬──────────────────────┘
       |            |                                 |
       v            v                                 v
  ┌────────┐  ┌──────────┐                    ┌──────────┐
  │ Redis  │  │ClickHouse│                    │PostgreSQL│
  │ Cache  │  │ (Finansal,│                   │ (Banka   │
  │        │  │  Bolgesel,│                   │  Bilgi)  │
  │        │  │  Risk)    │                   │          │
  └────────┘  └──────────┘                    └──────────┘
```

### Onbellekleme Stratejisi (Redis)

**Redis neden kullaniliyor?**

FastAPI her istekte ClickHouse ve PostgreSQL'e sorgu atar. Ancak TBB verileri anlik degismez;
finansal tablolar ceyreklik, bolgesel istatistikler aylik, banka bilgileri ise yilda birkac kez
guncellenir. Ayni sorguyu her istek icin tekrar calistirmak gereksiz veritabani yuku olusturur
ve yanit suresini arttirir. Redis, sik tekrarlanan sorgu sonuclarini bellekte tutarak:

- **Yanit suresini dusurur**: Veritabani sorgulari ~50-200 ms → Redis okuma ~1-2 ms
- **Veritabani yukunu azaltir**: Ayni sorgu binlerce kez yerine sadece TTL dolunca calisir
- **Olceklenebilirlik saglar**: Es zamanli kullanici sayisi artsa bile veritabani darbogazina yol acmaz

Her servis fonksiyonu once Redis'te cache key'i arar; varsa dogrudan dondurur, yoksa
veritabanindan ceker ve sonucu TTL suresiyle Redis'e yazar.

| Veri Turu | TTL | Cache Key Ornegi | Aciklama |
|-----------|-----|------------------|----------|
| Finansal veriler | 1 saat | `fin:ratios:2025:9:SOLO` | Ceyreklik guncellenir |
| Bolgesel / Risk verileri | 6 saat | `region:ldr:2024` | Aylik guncellenir |
| Banka bilgileri | 24 saat | `banks:all` | Nadiren degisir |
| Likidite analizi | 1 saat | `liq:creation:v7:2025:9:SOLO` | LC hesaplamalari |
| Risk analizi | 1 saat | `risk:zscore:2025:9:SOLO` | Z-Score hesaplamalari |
| Panel regresyon | 1 saat | `panel:regressions:SOLO` | OLS model sonuclari |
| Bolgesel likidite | 1 saat | `regional_liq:2025:9:SOLO` | Il bazli LC dagitimi |

### Gzip Sikistirma (Redis Cache)

Cache'e yazilan veriler gzip ile sikistirilarak saklanir. Bu sayede Redis bellek tuketimi %60-85 azalir.

Sikistirma akisi (`db/cache.py`):

```
YAZMA: json.dumps() → gzip.compress() → base64.b64encode() → redis.setex()
OKUMA: redis.get() → base64.b64decode() → gzip.decompress() → json.loads()
```

- **Neden base64?** Redis istemcisi `decode_responses=True` ile calisir (string modu).
  Gzip ciktisi binary oldugu icin base64 ile ASCII string'e donusturulur.
- **Esik degeri**: 256 byte'tan kucuk veriler sikistirilmaz (overhead kazanimi asar)
- **Geriye uyumluluk**: Eski (sikistirilmamis) cache degerleri otomatik taninir.
  Gzip+base64 verileri `H4sI` ile baslar, duz JSON ise `[` veya `{` ile baslar.
- **Sikistirma seviyesi**: gzip level 6 (hiz/oran dengesi)

Tum 24 cache fonksiyonu merkezi `cache_get`/`cache_set` yardimcilarini kullanir.

---

## 7. Kullanici Etkilesim Noktalari (Frontend)

### Teknoloji Yigini
- **React 18** + **TypeScript** + **React Router**
- **Ant Design** (Card, Table, Select, Statistic, Row/Col)
- **ECharts** (echarts-for-react) - Line, Bar, Pie/Donut grafikleri
- **TanStack Query** (cache + refetch yonetimi)
- **Axios** - HTTP istemcisi

### Sayfa Yapisi ve Veri Akisi

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                       Web Tarayici (:3000)                       │
  │──────────────────────────────────────────────────────────────────│
  │                                                                  │
  │  / Dashboard                                                     │
  │  ├── 4 KPI Karti (banka, sube, ATM, aktif)                      │
  │  ├── Banka Grubu Dagilimi (Pie + Donut)                          │
  │  ├── Sube/ATM Il Dagilimi (Bar)                                  │
  │  ├── Kredi/Mevduat Orani - LDR (Bar)                             │
  │  ├── Sektorel Yogunlasma - HHI (Stacked Bar)                     │
  │  ├── Finansal Oran Analizi - ROA/ROE/NIM/... (Bar)               │
  │  ├── Bolgesel Karsilastirma (Bar)                                │
  │  └── Sektor Toplam Trend (Line)                                  │
  │                                                                  │
  │  /financial - Mali Tablolar                                      │
  │  ├── Filtrelenebilir Tablo (yil, ay, banka, muhasebe sistemi)    │
  │  ├── CSV Export                                                  │
  │  └── Banka Bazli Zaman Serisi (Line)                             │
  │                                                                  │
  │  /regions - Bolgesel Istatistikler                               │
  │  ├── Metrik/Yil Secici                                           │
  │  ├── Bolgesel Karsilastirma (Bar)                                │
  │  └── Detay Tablosu                                               │
  │                                                                  │
  │  /risk-center - Risk Merkezi                                     │
  │  ├── Rapor/Kategori/Donem Secici                                 │
  │  ├── Tutar/Kisi/Adet Grafikleri (Bar)                            │
  │  └── Detay Tablosu                                               │
  │                                                                  │
  │  /banks - Banka Rehberi                                          │
  │  ├── Arama + Grup/Alt Grup Filtre                                │
  │  ├── Sube Listesi (il/ilce filtreli)                             │
  │  ├── ATM Listesi (il/ilce filtreli)                              │
  │  └── Tarihce (kurulus tarihi, onemli olaylar)                    │
  │                                                                  │
  │  /liquidity - Likidite Analizi (Colak et al. 2024)               │
  │  ├── Banka bazli LC tablosu (nonfat + fat)                       │
  │  ├── Banka grubu bazli LC karsilastirmasi                         │
  │  ├── Grup zaman serisi (Kamusal/Ozel/Yabanci)                    │
  │  └── LC bilesen (decomposition) analizi                          │
  │                                                                  │
  │  /regional-liquidity - Bolgesel Likidite                         │
  │  ├── Ozet istatistikler (il, sube, en yuksek LC)                │
  │  ├── En yuksek LC ilk 20 il (Bar)                                │
  │  ├── Sube dagilimi ilk 20 il (Bar)                               │
  │  └── Tum iller tablosu (81 il, siralanabilir)                    │
  │                                                                  │
  │  /comparison - Banka Karsilastirmasi                             │
  │  ├── Secilen bankalarin LC karsilastirmasi (Bar)                 │
  │  ├── LC zaman serisi karsilastirmasi (Line)                      │
  │  └── LC bilesen analizi (pozitif/negatif katkilar)               │
  │                                                                  │
  │  /risk - Risk Analizi                                            │
  │  ├── Z-Score siralamasi                                          │
  │  ├── Z-Score zaman serisi                                        │
  │  └── LC vs Risk iliskisi (Scatter)                               │
  │                                                                  │
  │  /panel-regression - Panel Regresyon (Colak et al. 2024)         │
  │  ├── Model 1: Sermaye Yeterliligi → LC                           │
  │  ├── Model 2: LC → Banka Riski (Z-Score)                         │
  │  ├── Model 3: Kamu Sahipligi → LC                                │
  │  └── Sermaye Yeterliligi vs LC sacilim grafigi                   │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘
          |
          |  Her sayfa icin:
          |
          v
  ┌─────────────────────────────────────────┐
  │  Custom Hook (TanStack Query)            │
  │  useFinancialRatios, useBanks, ...       │
  │  - Otomatik cache (staleTime)            │
  │  - enabled flag (gereksiz istek onleme)  │
  └──────────────┬──────────────────────────┘
                 |
                 v
  ┌──────────────────────────────────────────┐
  │  API Client (Axios)                       │
  │  financialApi.*, regionsApi.*,            │
  │  banksApi.*, riskCenterApi.*,             │
  │  liquidityApi.*, riskAnalysisApi.*,       │
  │  panelRegressionApi.*,                    │
  │  regionalLiquidityApi.*                   │
  └──────────────┬───────────────────────────┘
                 |
                 |  /api/*
                 v
  ┌──────────────────────────────────────────┐
  │  Nginx ──> proxy_pass ──> FastAPI :8000  │
  └──────────────────────────────────────────┘
```

### Sayfa - API Esleme Tablosu

| Route | Sayfa | Kullandigi API Endpoint'leri |
|-------|-------|-----------------------------|
| `/` | Dashboard | `/banks/`, `/banks/dashboard-stats`, `/financial/summary`, `/financial/periods`, `/financial/ratios`, `/financial/ratio-types`, `/financial/time-series`, `/regions/comparison`, `/regions/metrics`, `/regions/periods`, `/regions/loan-deposit-ratio`, `/regions/credit-hhi` |
| `/financial` | FinancialStatements | `/financial/statements`, `/financial/periods`, `/financial/bank-names`, `/financial/main-statements`, `/financial/child-statements`, `/financial/time-series` |
| `/regions` | RegionalStats | `/regions/stats`, `/regions/list`, `/regions/metrics`, `/regions/periods`, `/regions/comparison` |
| `/risk-center` | RiskCenter | `/risk-center/data`, `/risk-center/reports`, `/risk-center/periods`, `/risk-center/categories` |
| `/banks` | BankDirectory | `/banks/`, `/banks/search`, `/banks/{name}/branches`, `/banks/{name}/atms`, `/banks/{name}/history` |
| `/liquidity` | LiquidityAnalysis | `/liquidity/creation`, `/liquidity/time-series`, `/liquidity/groups`, `/liquidity/group-time-series`, `/liquidity/decomposition` |
| `/regional-liquidity` | RegionalLiquidity | `/regional-liquidity/distribution` |
| `/comparison` | BankComparison | `/liquidity/creation`, `/liquidity/time-series`, `/liquidity/decomposition`, `/financial/bank-names` |
| `/risk` | RiskAnalysis | `/risk-analysis/zscore`, `/risk-analysis/zscore-time-series`, `/risk-analysis/lc-risk` |
| `/panel-regression` | PanelRegression | `/panel-regression/results` |

---

## 8. Veri Kaynaklari ve Scraperlar

### Kaynak Siteler
1. **tbb.org.tr** - Banka bilgileri, sube/ATM verileri (statik HTML + Drupal AJAX)
2. **verisistemi.tbb.org.tr** - Finansal tablolar, bolgesel istatistikler, risk merkezi (DevExtreme UI bilesenleri + Pivot Grid)

### Temel Scraper Sinifi (`scrapers/base.py`)
Tum scraper'larin miras aldigi temel sinif:
- Headless Chrome driver (Turkce dil destegi)
- Rate limiting (varsayilan 2 saniye bekleme)
- BeautifulSoup ile HTML tablo ayristirma
- DevExtreme UI bilesenleri: dxList, dxTreeView, dxPivotGrid, dxCheckBox
- JavaScript API uzerinden Pivot Grid veri cikarma (HTML fallback)
- Turkce sayi/tarih formati ayristirma

### Scraper Detaylari

| Scraper | Kaynak | Hedef | Veri Turu |
|---------|--------|-------|-----------|
| **FinancialScraper** | verisistemi - report_mali | ClickHouse | Mali tablolar (Solo + Konsolide) |
| **BankInfoScraper** | tbb.org.tr | PostgreSQL | Banka, sube, ATM bilgileri |
| **RegionScraper** | verisistemi - report_bolgeler | ClickHouse | Bolgesel istatistikler |
| **RiskCenterScraper** | verisistemi - report_rm | ClickHouse | Risk merkezi verileri |

#### FinancialScraper
- 2 tablo tipi: SOLO (index 0) ve KONSOLİDE (index 1)
- 6 banka grubu (ID: 1, 2, 3, 4, 9, 13) sirayla islenir
- Bireysel bankalar 5'li batch'ler halinde islenir (bellek tasmasini onlemek icin)
- Pivot kayitlari: banka adi, muhasebe sistemi, donem, tutarlar (TP/YP/Toplam)
- Hiyerarsi esleme: item ID → isim, ust kalem, kok kalem

#### BankInfoScraper
- Banka listesi: grup, alt grup, isim, adres, yonetim, iletisim, EFT, SWIFT
- Subeler/ATM'ler: Drupal AJAX form ile "Listele" butonu
- Cookie banner otomatik kapatma
- Beyaz bosluk normalizasyonu

#### RegionScraper
- 96 bolge/il (selectAll)
- En guncel 3 yil
- Tum parametreler/metrikler
- DevExtreme dxList sanal kaydirma cozumu

#### RiskCenterScraper
- Tum raporlar uzerinde iterasyon
- Kategori sayisi <=1 olan raporlar atlanir
- Her rapor icin: tum kategoriler, ilk 3 donem, 3 flag (KISI, ADET, TUTAR)
- Raporlar arasi secim temizleme

---

## 9. Transformer ve Loader Detaylari

### Transformerlar (`etl/transformers.py`)

| Fonksiyon | Giris | Islemler | Cikis |
|-----------|-------|----------|-------|
| `transform_financial` | Ham pivot kayitlari | Muhasebe sistemi cikarma, ana/alt kalem esleme, Turkce tutar ayristirma (TP/YP/Toplam), yil/ay cikarma | `{accounting_system, main_statement, child_statement, bank_name, year_id, month_id, amount_tc, amount_fc, amount_total}` |
| `transform_regions` | Ham pivot kayitlari | Bolge/metrik cikarma, deger ayristirma, yil cikarma | `{region, metric, year_id, value}` |
| `transform_risk_center` | Ham pivot kayitlari | Rapor/kategori cikarma, kisi/adet/tutar ayristirma, yil/ay cikarma | `{report_name, category, person_count, quantity, amount, year_id, month_id}` |
| `transform_bank_info` | Dict (banks, branches, atms) | Tablo formati donusumu, Turkce tarih ayristirma (dd.mm.yyyy) | `{bank_info[], branch_info[], atm_info[], historical_events[]}` |

Yardimci fonksiyonlar:
- `_safe_decimal()`: Turkce formatli sayilari Decimal'e cevirir (nokta=binlik, virgul=ondalik)
- `_safe_int()`: Turkce formatli tam sayilari cevirir
- `_parse_date()`: dd.mm.yyyy → yyyy-mm-dd donusumu
- `_first_of()`: Birden fazla alan adindan ilk bos olmayanini alir

### Loaderlar

#### ClickHouse Loader (`etl/clickhouse_loader.py`)
- Batch boyutu: 10.000 satir
- 3 fonksiyon: `load_financial_statements()`, `load_region_statistics()`, `load_risk_center()`
- Tarih string'lerini datetime objesine cevirir

#### PostgreSQL Loader (`etl/postgres_loader.py`)
- `psycopg2` ile `execute_values` toplu ekleme
- UPSERT (ON CONFLICT) destegi - tekrar scrape'te veri guncellenir
- 4 fonksiyon: `load_bank_info()`, `load_branch_info()`, `load_atm_info()`, `load_historical_events()`
- `load_all_bank_data()`: Tum yuklemeleri sirayla orkestre eder
- ATM verilerinde PK bazli tekilsizlik temizleme (son kayit korunur)

---

## 10. Konfigurasyoni (`config.py`)

| Degisken | Varsayilan | Aciklama |
|----------|-----------|----------|
| POSTGRES_HOST | localhost | PostgreSQL sunucu adresi |
| POSTGRES_PORT | 5432 | PostgreSQL portu |
| POSTGRES_USER | tbb_user | PostgreSQL kullanici adi |
| POSTGRES_DB | tbb | PostgreSQL veritabani adi |
| CLICKHOUSE_HOST | localhost | ClickHouse sunucu adresi |
| CLICKHOUSE_PORT | 9000 | ClickHouse native portu |
| CLICKHOUSE_HTTP_PORT | 8123 | ClickHouse HTTP portu |
| CLICKHOUSE_DB | tbb | ClickHouse veritabani adi |
| REDIS_HOST | localhost | Redis sunucu adresi |
| REDIS_PORT | 6379 | Redis portu |
| FASTAPI_HOST | 0.0.0.0 | FastAPI bind adresi |
| FASTAPI_PORT | 8000 | FastAPI portu |
| CORS_ORIGINS | localhost:3000, localhost:5173 | Izin verilen CORS kaynaklari |
| TBB_BASE_URL | https://verisistemi.tbb.org.tr | Scraping hedef URL |
| TBB_RATE_LIMIT_SECONDS | 2.0 | Istekler arasi bekleme suresi |
| SELENIUM_HEADLESS | true | Chrome basiz modda calisir |

Tum degiskenler ortam degiskenleri ile override edilebilir.

---

## 11. Bellek Yapilandirmasi

Proje 7 Docker container calistirir. Sinirli RAM'e sahip makinelerde bellek tasmasi yasanabilir.
Bu sorunu onlemek icin otomatik bellek yapilandirma scripti sunulur.

### Otomatik Yapilandirma

`start.sh` scripti makinenin donanim ozelliklerini algilar ve tum sistemi otomatik baslatir:

```bash
./start.sh              # Varsayilan: toplam RAM'in %80'i
./start.sh 8g           # Sabit RAM: 8 GB
./start.sh 60%          # Toplam RAM'in %60'i
```

Arka planda `scripts/configure_resources.py` calisir. Manuel kullanim:

```bash
python3 scripts/configure_resources.py --ram 70% --dry-run  # Onizleme
python3 scripts/configure_resources.py --ram 70%            # Uygula
docker compose up -d
```

RAM belirtilmezse kullanilabilir RAM otomatik tespit edilir.
Remote sunucularda `--ram 70%` onerilen varsayilandir (start.sh bunu kullanir).

| Servis | Kullanilabilir RAM'in Payi | Minimum |
|--------|---------------------------|---------|
| clickhouse | %30 | 1536 MB |
| postgres | %18 | 256 MB |
| airflow-webserver | %15 | 512 MB |
| airflow-scheduler | %12 | 384 MB |
| fastapi | %10 | 256 MB |
| redis | %6 | 64 MB |
| frontend | %4 | 64 MB |

Kullanilabilir RAM yetersizse script uyari verir.

### Ek Yapilandirmalar

Script asagidaki optimizasyonlari da otomatik uygular:

**PostgreSQL**:
- `shared_buffers`: Container limitinin %25'i (varsayilan 128 MB yerine)
- `checkpoint_timeout`: 30 dakika (varsayilan 5 dakika yerine)

**Redis**:
- `maxmemory`: Container limitinin %90'i
- `maxmemory-policy`: `allkeys-lru` (bellek dolunca en az kullanilan key silinir)

### Ornek Cikti (16 GB makine, 8 GB bos)

```
Total RAM     : 16.0 GB
Used (OS+apps): 8.0 GB
Available     : 8.0 GB

Service                   Limit
--------------------------------
  postgres                1472m
  clickhouse              2496m
  redis                    512m
  airflow-webserver       1280m
  airflow-scheduler        960m
  fastapi                  832m
  frontend                 320m
--------------------------------
  Docker total            7872m  (7.7 GB / 8.0 GB available)
```

---

## 12. Dizin Yapisi

```
tbb/
├── dags/                          # Airflow DAG tanimlari
│   ├── tbb_financial_dag.py
│   ├── tbb_bank_info_dag.py
│   ├── tbb_regions_dag.py
│   └── tbb_risk_center_dag.py
├── docker/
│   ├── airflow/Dockerfile         # Airflow custom image
│   ├── clickhouse/init-db.sql     # ClickHouse sema
│   └── postgres/init-db.sql       # PostgreSQL sema
├── docker-compose.yml
├── frontend/
│   ├── Dockerfile                 # Node build + Nginx
│   ├── nginx.conf                 # Reverse proxy
│   └── src/
│       ├── api/client.ts          # Axios API istemcisi
│       ├── components/charts/     # LineChart, BarChart, PieChart, ScatterChart
│       ├── hooks/                 # TanStack Query hooklari (8 hook modulu)
│       ├── pages/                 # 10 sayfa (Dashboard, Financial, Regions,
│       │                          #   Risk, Banks, Liquidity, RegionalLiquidity,
│       │                          #   BankComparison, RiskAnalysis, PanelRegression)
│       └── types/index.ts         # TypeScript tip tanimlari
├── source/
│   ├── config.py                  # Merkezi konfigurasyoni
│   ├── api/
│   │   ├── main.py                # FastAPI uygulama
│   │   ├── dependencies.py        # DI (DB baglantilar)
│   │   ├── routers/               # Endpoint tanimlari
│   │   └── services/              # Is mantigi katmani
│   ├── etl/
│   │   ├── transformers.py        # Veri donusturuculer
│   │   ├── clickhouse_loader.py   # ClickHouse yukleyici
│   │   └── postgres_loader.py     # PostgreSQL yukleyici
│   ├── scrapers/
│   │   ├── base.py                # Temel scraper sinifi
│   │   ├── financial_scraper.py
│   │   ├── bank_info_scraper.py
│   │   ├── region_scraper.py
│   │   └── risk_center_scraper.py
│   └── db/                        # Veritabani baglanti yardimcilari
│       ├── redis.py               # Async Redis istemcisi
│       ├── postgres.py            # AsyncPG connection pool
│       ├── clickhouse.py          # ClickHouse native istemci
│       └── cache.py               # Gzip sikistirmali cache yardimcilari
├── scripts/
│   ├── configure_resources.py     # Bellek otomatik yapilandirma
│   └── requirements.txt           # Script bagimliliklari (psutil, ruamel.yaml)
├── start.sh                       # Tek komutla otomatik kurulum ve baslatma
├── ARCHITECTURE.md
├── ENDPOINTS.md
└── DASHBOARD_ANALYSES.md
```
