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

export interface RatioType {
  key: string;
  label: string;
  desc: string;
}

export interface BankRatios {
  bank_name: string;
  total_assets: number;
  ROA: number | null;
  ROE: number | null;
  NIM: number | null;
  PROVISION: number | null;
  LEVERAGE: number | null;
  FX_SHARE: number | null;
}

export interface DashboardStats {
  total_branches: number;
  total_atms: number;
  branch_by_city: { city: string; count: number }[];
  atm_by_city: { city: string; count: number }[];
}

export type LiquidityMeasure = 'nonfat' | 'fat';

export interface LiquidityCreation {
  bank_name: string;
  lc_ratio: number;
  lc_nonfat: number;
  lc_fat: number;
  liquid_assets: number;
  semi_liquid_assets: number;
  illiquid_assets: number;
  liquid_liabilities: number;
  semi_liquid_liabilities: number;
  illiquid_liabilities_equity: number;
  illiquid_obs: number;
  semi_liquid_obs: number;
  total_assets: number;
}

export interface LiquidityTimeSeries {
  year_id: number;
  month_id: number;
  lc_ratio: number;
  lc_nonfat: number;
  lc_fat: number;
}

export interface LiquidityGroup {
  group_name: string;
  lc_ratio: number;
  lc_nonfat: number;
  lc_fat: number;
  bank_count: number;
}

export interface LiquidityGroupTimeSeries {
  group_name: string;
  year_id: number;
  month_id: number;
  lc_nonfat: number;
}

export interface LiquidityDecomposition {
  bank_name: string;
  lc_ratio: number;
  lc_nonfat: number;
  lc_fat: number;
  total_assets: number;
  components: {
    liquid_assets: number;
    semi_liquid_assets: number;
    illiquid_assets: number;
    liquid_liabilities: number;
    semi_liquid_liabilities: number;
    illiquid_liabilities_equity: number;
    illiquid_obs: number;
    semi_liquid_obs: number;
  };
  weighted_components: {
    illiquid_assets_contrib: number;
    liquid_liabilities_contrib: number;
    liquid_assets_drag: number;
    illiquid_liab_equity_drag: number;
    illiquid_obs_contrib: number;
  };
}

export interface ZScoreRanking {
  bank_name: string;
  z_score: number | null;
  roa: number;
  capital_ratio: number;
  roa_std: number | null;
  total_assets: number;
  equity: number;
  net_income: number;
}

export interface ZScoreTimeSeries {
  bank_name: string;
  year_id: number;
  month_id: number;
  z_score: number | null;
  roa: number;
  capital_ratio: number;
}

export interface LCRiskRelationship {
  bank_name: string;
  z_score: number | null;
  lc_nonfat: number;
  roa: number;
  capital_ratio: number;
  total_assets: number;
  bank_group: string;
}

export interface RegionalLiquidity {
  city: string;
  lc_amount: number;
  branch_count: number;
  bank_count: number;
  avg_lc_ratio: number | null;
}
