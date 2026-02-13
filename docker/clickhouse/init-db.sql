CREATE DATABASE IF NOT EXISTS tbb;

CREATE TABLE IF NOT EXISTS tbb.financial_statements
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

CREATE TABLE IF NOT EXISTS tbb.region_statistics
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

CREATE TABLE IF NOT EXISTS tbb.risk_center
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
