## ClickHouse
```sql
CREATE TABLE tbb.financial_statements
(
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
)
ENGINE = ReplacingMergeTree(crawl_timestamp)
ORDER BY (accounting_system, child_statement, bank_name, year_id, month_id, main_statement)
PARTITION BY year_id
COMMENT 'TBB Financial Statements - report_financial';
```


```sql
CREATE TABLE tbb.region_statistics
(
    region          LowCardinality(String),
    metric          LowCardinality(String),
    year_id         UInt16,
    value           Decimal128(2),
    crawl_timestamp DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(crawl_timestamp)
ORDER BY (region, metric, year_id)
PARTITION BY year_id
COMMENT 'TBB Regional Statistics - report_regions';
```

```sql
CREATE TABLE tbb.risk_center
(
    report_name     LowCardinality(String),
    category        LowCardinality(String),
    person_count    Nullable(UInt64),
    quantity        Nullable(UInt64),
    amount          Nullable(Decimal128(2)),
    year_id         UInt16,
    month_id        UInt8,
    crawl_timestamp DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(crawl_timestamp)
ORDER BY (report_name, category, year_id, month_id)
PARTITION BY year_id
COMMENT 'TBB Risk Center Data - report_rm';

```
## Postgresql

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
```

```sql
CREATE TABLE branch_info (
    bank_name VARCHAR(200),
    branch_name VARCHAR(200) PRIMARY KEY,
    address TEXT,
    district VARCHAR(150),
    city VARCHAR(150),
    phone VARCHAR(100),
    fax VARCHAR(100),
    opening_date DATE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_name) REFERENCES bank_info(bank_name) ON DELETE CASCADE
);
```

```sql
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
```

```sql
CREATE TABLE historical_events (
    bank_name VARCHAR(200) PRIMARY KEY,
    founding_date DATE,
    historical_event TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_name) REFERENCES bank_info(bank_name) ON DELETE CASCADE
);
```