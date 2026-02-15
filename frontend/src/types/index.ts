export interface FinancialRecord {
  accounting_system: string;
  main_statement: string;
  child_statement: string;
  bank_name: string;
  year_id: number;
  month_id: number;
  amount_tc: number | null;
  amount_fc: number | null;
  amount_total: number | null;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface FinancialSummary {
  metric: string;
  total: number | null;
  count: number;
}

export interface PeriodInfo {
  year_id: number;
  month_id: number;
}

export interface TimeSeriesPoint {
  year_id: number;
  month_id: number;
  amount_total: number | null;
}

export interface RegionStat {
  region: string;
  metric: string;
  year_id: number;
  value: number | null;
}

export interface RegionComparison {
  region: string;
  value: number | null;
}

export interface RiskCenterRecord {
  report_name: string;
  category: string;
  person_count: number | null;
  quantity: number | null;
  amount: number | null;
  year_id: number;
  month_id: number;
}

export interface BankInfo {
  bank_group: string | null;
  sub_bank_group: string | null;
  bank_name: string;
  address: string | null;
  board_president: string | null;
  general_manager: string | null;
  phone_fax: string | null;
  web_kep_address: string | null;
  eft: string | null;
  swift: string | null;
}

export interface BranchInfo {
  bank_name: string;
  branch_name: string;
  address: string | null;
  district: string | null;
  city: string | null;
  phone: string | null;
  fax: string | null;
  opening_date: string | null;
}

export interface ATMInfo {
  bank_name: string;
  branch_name: string | null;
  address: string | null;
  district: string | null;
  city: string | null;
}

export interface HistoricalEvent {
  bank_name: string;
  founding_date: string | null;
  historical_event: string | null;
}

export interface DashboardStats {
  total_branches: number;
  total_atms: number;
  branch_by_city: { city: string; count: number }[];
  atm_by_city: { city: string; count: number }[];
}
