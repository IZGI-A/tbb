from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


# --- Financial ---

class FinancialRecord(BaseModel):
    accounting_system: str
    main_statement: str
    child_statement: str
    bank_name: str
    year_id: int
    month_id: int
    amount_tc: Decimal | None = None
    amount_fc: Decimal | None = None
    amount_total: Decimal | None = None


class FinancialSummary(BaseModel):
    metric: str
    total: Decimal | None = None
    count: int = 0


class PeriodInfo(BaseModel):
    year_id: int
    month_id: int


class TimeSeriesPoint(BaseModel):
    year_id: int
    month_id: int
    amount_total: Decimal | None = None


# --- Regions ---

class RegionStat(BaseModel):
    region: str
    metric: str
    year_id: int
    value: Decimal | None = None


class RegionComparison(BaseModel):
    region: str
    value: Decimal | None = None


# --- Risk Center ---

class RiskCenterRecord(BaseModel):
    report_name: str
    category: str
    person_count: int | None = None
    quantity: int | None = None
    amount: Decimal | None = None
    year_id: int
    month_id: int


class ReportInfo(BaseModel):
    report_name: str


class CategoryInfo(BaseModel):
    category: str


# --- Banks ---

class BankInfo(BaseModel):
    bank_group: str | None = None
    sub_bank_group: str | None = None
    bank_name: str
    address: str | None = None
    board_president: str | None = None
    general_manager: str | None = None
    phone_fax: str | None = None
    web_kep_address: str | None = None
    eft: str | None = None
    swift: str | None = None


class BranchInfo(BaseModel):
    bank_name: str
    branch_name: str
    address: str | None = None
    district: str | None = None
    city: str | None = None
    phone: str | None = None
    fax: str | None = None
    opening_date: date | None = None


class ATMInfo(BaseModel):
    bank_name: str
    branch_name: str | None = None
    address: str | None = None
    district: str | None = None
    city: str | None = None
    phone: str | None = None
    fax: str | None = None
    opening_date: date | None = None


class HistoricalEvent(BaseModel):
    bank_name: str
    founding_date: date | None = None
    historical_event: str | None = None


# --- Pagination ---

class PaginatedResponse(BaseModel):
    data: list
    total: int
    limit: int
    offset: int
