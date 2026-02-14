import { useQuery } from '@tanstack/react-query';
import { financialApi } from '../api/client';
import type { FinancialRecord, FinancialSummary, PaginatedResponse, PeriodInfo, TimeSeriesPoint } from '../types';

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

export function useFinancialTimeSeries(params: Record<string, unknown>) {
  return useQuery<TimeSeriesPoint[]>({
    queryKey: ['financial', 'time-series', params],
    queryFn: () => financialApi.getTimeSeries(params).then(r => r.data),
    enabled: !!params.bank_name,
  });
}
