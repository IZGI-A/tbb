-- Create airflow database
CREATE DATABASE airflow;

-- TBB tables in default database
CREATE TABLE IF NOT EXISTS bank_info (
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

CREATE TABLE IF NOT EXISTS branch_info (
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

CREATE TABLE IF NOT EXISTS atm_info (
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

CREATE TABLE IF NOT EXISTS historical_events (
    bank_name VARCHAR(200) PRIMARY KEY,
    founding_date DATE,
    historical_event TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bank_name) REFERENCES bank_info(bank_name) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_branch_bank ON branch_info(bank_name);
CREATE INDEX IF NOT EXISTS idx_branch_city ON branch_info(city);
CREATE INDEX IF NOT EXISTS idx_atm_bank ON atm_info(bank_name);
CREATE INDEX IF NOT EXISTS idx_atm_city ON atm_info(city);
