import { useQuery } from '@tanstack/react-query';
import { financialApi } from '../api/client';

export function useFinancialStatements(params: Record<string, unknown>) {
  return useQuery({
    queryKey: ['financial', 'statements', params],
    queryFn: () => financialApi.getStatements(params).then(r => r.data),
  });
}

export function useFinancialSummary(params: Record<string, unknown>) {
  return useQuery({
    queryKey: ['financial', 'summary', params],
    queryFn: () => financialApi.getSummary(params).then(r => r.data),
  });
}

export function useFinancialPeriods() {
  return useQuery({
    queryKey: ['financial', 'periods'],
    queryFn: () => financialApi.getPeriods().then(r => r.data),
  });
}

export function useFinancialTimeSeries(params: Record<string, unknown>) {
  return useQuery({
    queryKey: ['financial', 'time-series', params],
    queryFn: () => financialApi.getTimeSeries(params).then(r => r.data),
    enabled: !!params.bank_name,
  });
}
