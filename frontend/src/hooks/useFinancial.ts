import { useQuery } from '@tanstack/react-query';
import { financialApi } from '../api/client';
import type { BankRatios, FinancialRecord, FinancialSummary, PaginatedResponse, PeriodInfo, RatioType, TimeSeriesPoint } from '../types';

export function useFinancialStatements(params: Record<string, unknown>) {
  return useQuery<PaginatedResponse<FinancialRecord>>({
    queryKey: ['financial', 'statements', params],
    queryFn: () => financialApi.getStatements(params).then(r => r.data),
  });
}

export function useFinancialSummary(params: Record<string, unknown>) {
  return useQuery<FinancialSummary[]>({
    queryKey: ['financial', 'summary', params],
    queryFn: () => financialApi.getSummary(params).then(r => r.data),
  });
}

export function useFinancialPeriods() {
  return useQuery<PeriodInfo[]>({
    queryKey: ['financial', 'periods'],
    queryFn: () => financialApi.getPeriods().then(r => r.data),
  });
}

export function useFinancialBankNames(accountingSystem?: string) {
  return useQuery<string[]>({
    queryKey: ['financial', 'bank-names', accountingSystem],
    queryFn: () => financialApi.getBankNames(
      accountingSystem ? { accounting_system: accountingSystem } : undefined
    ).then(r => r.data),
  });
}

export function useFinancialMainStatements() {
  return useQuery<string[]>({
    queryKey: ['financial', 'main-statements'],
    queryFn: () => financialApi.getMainStatements().then(r => r.data),
  });
}

export function useFinancialChildStatements(mainStatement?: string) {
  return useQuery<string[]>({
    queryKey: ['financial', 'child-statements', mainStatement],
    queryFn: () => financialApi.getChildStatements(
      mainStatement ? { main_statement: mainStatement } : {}
    ).then(r => r.data),
  });
}

export function useFinancialTimeSeries(params: Record<string, unknown>) {
  return useQuery<TimeSeriesPoint[]>({
    queryKey: ['financial', 'time-series', params],
    queryFn: () => financialApi.getTimeSeries(params).then(r => r.data),
    enabled: !!params.bank_name,
  });
}

export function useFinancialRatioTypes() {
  return useQuery<RatioType[]>({
    queryKey: ['financial', 'ratio-types'],
    queryFn: () => financialApi.getRatioTypes().then(r => r.data),
  });
}

export function useFinancialRatios(year: number, month: number, accountingSystem?: string) {
  return useQuery<BankRatios[]>({
    queryKey: ['financial', 'ratios', year, month, accountingSystem],
    queryFn: () => financialApi.getRatios({ year, month, accounting_system: accountingSystem }).then(r => r.data),
    enabled: !!year && !!month,
  });
}
