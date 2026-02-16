# TBB Veri Platformu

Turkiye Bankalar Birligi (TBB) kamuya acik verilerini toplayan, isleyen ve gorsellestiren uctan uca bir veri analiz platformu.

## Ozellikler

- TBB web sitelerinden otomatik veri toplama (Selenium)
- 4 Airflow DAG ile zamanlanmis ETL pipeline'lari
- PostgreSQL (yapisal veri) + ClickHouse (analitik veri) ikili veritabani mimarisi
- FastAPI ile 27 REST endpoint (Redis cache + gzip sikistirma)
- React dashboard: finansal oranlar, bolgesel analizler, risk merkezi, banka rehberi
- Donanim altyapisina gore otomatik bellek yapilandirmasi

## Onkosullar

- [Docker](https://docs.docker.com/get-docker/) ve [Docker Compose](https://docs.docker.com/compose/install/)
- [Python 3.9+](https://www.python.org/downloads/) (bellek yapilandirma scripti icin)
- En az **4 GB** bos RAM (ClickHouse min. 1.5 GB gerektirir)
- Portlar: 3000, 5432, 6379, 8000, 8080, 8123, 9000

## Hizli Kurulum

```bash
git clone <repo-url>
cd tbb
cp .env.example .env       # Ortam degiskenlerini ayarla (asagiya bak)
./start.sh                 # Otomatik yapilandirma + baslatma
```

Bu kadar. `start.sh` geri kalan her seyi otomatik halleder:
1. Python bagimliliklerini kurar (psutil, ruamel.yaml)
2. Makinenin RAM'ini tespit eder 
3. Her servise uygun bellek limiti atar (Redis maxmemory, PostgreSQL shared_buffers dahil)
4. Docker servislerini baslatir

### RAM Secenekleri

```bash
./start.sh                 # Varsayilan: toplam RAM'in %70'i (sunucu icin onerilen)
./start.sh 8g              # Sabit ram: 8 GB
./start.sh 60%             # Toplam RAM'in %60'i (lokal gelistirme icin onerilen)
./start.sh --build         # Image'lari yeniden build et
./start.sh 8g --build      # RAM + build birlikte
```

### Ortam Degiskenleri

`cp .env.example .env` ile olusturulan `.env` dosyasinda asagidaki alanlari doldur:

```
POSTGRES_PASSWORD=tbb_secure_pass_123
AIRFLOW__CORE__FERNET_KEY=<fernet-key>
AIRFLOW__WEBSERVER__SECRET_KEY=<secret-key>
```

Fernet key uretmek icin:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Manuel Kurulum

Adim adim kontrol etmek istiyorsaniz:

```bash
# 1. Ortam degiskenleri
cp .env.example .env

# 2. Bellek yapilandirmasi
pip3 install -r scripts/requirements.txt
python3 scripts/configure_resources.py --ram 70% --dry-run   # Onizleme
python3 scripts/configure_resources.py --ram 70%             # Uygula

# 3. Servisleri baslat
docker compose up -d --build
```

### Kurulumu Dogrula

```bash
docker compose ps                     # 7 servis running/healthy olmali
docker compose logs -f fastapi        # "Uvicorn running on http://0.0.0.0:8000" mesajini bekle
```

## Erisim Adresleri

| Servis | URL | Aciklama |
|--------|-----|----------|
| **Frontend** | http://localhost:3000 | Web arayuzu (Dashboard) |
| **FastAPI** | http://localhost:8000/docs | Swagger API dokumantasyonu |
| **Airflow** | http://localhost:8080 | DAG yonetim paneli |
| **ClickHouse** | http://localhost:8123 | ClickHouse HTTP arayuzu |
| **PostgreSQL** | localhost:5432 | Veritabani (kullanici: tbb_user) |

Airflow giris bilgileri: `admin` / `admin`

## Veri Toplama (Ilk Calistirma)

Kurulumdan sonra veritabanlari bos gelir. Verileri toplamak icin Airflow DAG'larini tetikle:

### Airflow Web UI uzerinden

1. http://localhost:8080 adresine git
2. DAG'lari sirayla **unpause** yap (toggle butonu)
3. Her DAG'in yanindaki **play** butonuna tiklayip "Trigger DAG" sec

### Komut satirindan

```bash
# Banka bilgileri
docker compose exec airflow-webserver airflow dags unpause tbb_bank_info
docker compose exec airflow-webserver airflow dags trigger tbb_bank_info

# Finansal tablolar
docker compose exec airflow-webserver airflow dags unpause tbb_financial_statements
docker compose exec airflow-webserver airflow dags trigger tbb_financial_statements

# Bolgesel istatistikler
docker compose exec airflow-webserver airflow dags unpause tbb_region_statistics
docker compose exec airflow-webserver airflow dags trigger tbb_region_statistics

# Risk merkezi
docker compose exec airflow-webserver airflow dags unpause tbb_risk_center
docker compose exec airflow-webserver airflow dags trigger tbb_risk_center
```

DAG durumlarini takip et:

```bash
docker compose exec airflow-webserver airflow dags list-runs -d tbb_financial_statements
```

## Yeniden Build

```bash
./start.sh --build                           # Tum servisler (bellek yeniden yapilandirilir)
docker compose up -d --build fastapi         # Sadece backend
docker compose up -d --build frontend        # Sadece frontend
docker compose up -d --build fastapi frontend  # Her ikisi
```

## Faydali Komutlar

```bash
# Servis durumlarini gor
docker compose ps

# Belirli bir servisin loglarini takip et
docker compose logs -f fastapi
docker compose logs -f airflow-scheduler

# Redis cache'ini temizle (veri degisikliginden sonra)
docker compose exec redis redis-cli FLUSHDB

# ClickHouse'a dogrudan sorgu at
docker compose exec clickhouse clickhouse-client --query "SELECT count() FROM tbb.financial_statements"

# PostgreSQL'e baglan
docker compose exec postgres psql -U tbb_user -d tbb

# Bellek yapilandirmasini onizle
python3 scripts/configure_resources.py --ram 70% --dry-run

# Tum servisleri durdur
docker compose down

# Servisleri VE verileri sil (dikkat: veritabani verileri silinir!)
docker compose down -v
```

## Proje Yapisi

```
tbb/
├── start.sh                    # Otomatik kurulum ve baslatma scripti
├── docker-compose.yml          # 7 servis tanimlamasi + bellek limitleri
├── .env.example                # Ortam degiskenleri sablonu
├── dags/                       # Airflow DAG tanimlari (4 pipeline)
├── docker/
│   ├── airflow/Dockerfile      # Airflow + Chrome + Python deps
│   ├── clickhouse/init-db.sql
│   └── postgres/init-db.sql
├── frontend/                   # React + TypeScript + Ant Design
│   ├── src/
│   │   ├── pages/              # 5 sayfa (Dashboard, Financial, ...)
│   │   ├── hooks/              # TanStack Query hooklari
│   │   ├── components/         # Chart bilesenleri (Line, Bar, Pie)
│   │   └── api/client.ts       # Axios API istemcisi
│   └── Dockerfile
├── source/                     # Python backend + scrapers + ETL
│   ├── api/                    # FastAPI (routers + services)
│   ├── db/cache.py             # Gzip sikistirmali Redis cache
│   ├── scrapers/               # 4 Selenium scraper
│   ├── etl/                    # Transformer + Loader
│   ├── config.py
│   └── Dockerfile
├── scripts/
│   ├── configure_resources.py  # Bellek otomatik yapilandirma
│   └── requirements.txt        # Script bagimliliklari
└── documents/
    ├── ARCHITECTURE.md         # Sistem mimarisi ve veri akisi
    ├── ENDPOINTS.md            # 27 API endpoint dokumantasyonu
    └── DASHBOARD_ANALYSES.md   # Dashboard analiz aciklamalari
```

## Dokumantasyon

Dokumanlar `documents/` klasoru altinda yer almaktadir.

| Dosya | Icerik |
|-------|--------|
| [ARCHITECTURE.md](documents/ARCHITECTURE.md) | Sistem mimarisi, veri akisi, veritabani semalari, servis iletisimi |
| [ENDPOINTS.md](documents/ENDPOINTS.md) | 27 API endpoint - parametreler, ornek yanitlar |
| [DASHBOARD_ANALYSES.md](documents/DASHBOARD_ANALYSES.md) | Dashboard grafik/analiz aciklamalari, SQL sorgulari, formuller |

## Veritabani Semalari

### ClickHouse

```sql
-- Mali tablolar (~800K satir, Solo + Konsolide)
CREATE TABLE tbb.financial_statements (
    accounting_system     LowCardinality(String),
    main_statement        LowCardinality(String),
    child_statement       LowCardinality(String),
    bank_name             LowCardinality(String),
    year_id               UInt16,
    month_id              UInt8,
    amount_tc             Nullable(Decimal128(2)),
    amount_fc             Nullable(Decimal128(2)),
    amount_total          Nullable(Decimal128(2)),
    crawl_timestamp       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(crawl_timestamp)
  ORDER BY (accounting_system, child_statement, bank_name, year_id, month_id, main_statement)
  PARTITION BY year_id;

-- Bolgesel istatistikler
CREATE TABLE tbb.region_statistics (
    region          LowCardinality(String),
    metric          LowCardinality(String),
    year_id         UInt16,
    value           Decimal128(2),
    crawl_timestamp DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(crawl_timestamp)
  ORDER BY (region, metric, year_id)
  PARTITION BY year_id;

-- Risk merkezi
CREATE TABLE tbb.risk_center (
    report_name     LowCardinality(String),
    category        LowCardinality(String),
    person_count    Nullable(UInt64),
    quantity        Nullable(UInt64),
    amount          Nullable(Decimal128(2)),
    year_id         UInt16,
    month_id        UInt8,
    crawl_timestamp DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(crawl_timestamp)
  ORDER BY (report_name, category, year_id, month_id)
  PARTITION BY year_id;
```

### PostgreSQL

```sql
CREATE TABLE bank_info (
    bank_group VARCHAR(150),
    sub_bank_group VARCHAR(150),
    bank_name VARCHAR(200) PRIMARY KEY,
    address TEXT,
    board_president VARCHAR(150),
    general_manager VARCHAR(150),
    phone_fax VARCHAR(100),
    web_kep_address VARCHAR(250),
    eft VARCHAR(50),
    swift VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE branch_info (
    bank_name VARCHAR(200),
    branch_name VARCHAR(200),
    address TEXT,
    district VARCHAR(150),
    city VARCHAR(150),
    phone VARCHAR(100),
    fax VARCHAR(100),
    opening_date DATE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bank_name, branch_name),
    FOREIGN KEY (bank_name) REFERENCES bank_info(bank_name) ON DELETE CASCADE
);

CREATE TABLE atm_info (
    bank_name VARCHAR(200),
    branch_name VARCHAR(200),
    address TEXT,
    district VARCHAR(150),
    city VARCHAR(150),
    phone VARCHAR(100),
    fax VARCHAR(100),
    opening_date DATE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bank_name, branch_name, address),
    FOREIGN KEY (bank_name) REFERENCES bank_info(bank_name) ON DELETE CASCADE
);

CREATE TABLE historical_events (
    bank_name VARCHAR(200) PRIMARY KEY,
    founding_date DATE,
    historical_event TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_name) REFERENCES bank_info(bank_name) ON DELETE CASCADE
);
```
