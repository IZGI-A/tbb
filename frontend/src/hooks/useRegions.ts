import { useQuery } from '@tanstack/react-query';
import { regionsApi } from '../api/client';

export function useRegionStats(params: Record<string, unknown>) {
  return useQuery({
    queryKey: ['regions', 'stats', params],
    queryFn: () => regionsApi.getStats(params).then(r => r.data),
  });
}

export function useRegionList() {
  return useQuery({
    queryKey: ['regions', 'list'],
    queryFn: () => regionsApi.getList().then(r => r.data),
  });
}

export function useRegionMetrics() {
  return useQuery({
    queryKey: ['regions', 'metrics'],
    queryFn: () => regionsApi.getMetrics().then(r => r.data),
  });
}

export function useRegionPeriods() {
  return useQuery({
    queryKey: ['regions', 'periods'],
    queryFn: () => regionsApi.getPeriods().then(r => r.data),
  });
}

export function useRegionComparison(metric: string, year: number) {
  return useQuery({
    queryKey: ['regions', 'comparison', metric, year],
    queryFn: () => regionsApi.getComparison({ metric, year }).then(r => r.data),
    enabled: !!metric && !!year,
  });
}

export function useCreditHhi(year: number) {
  return useQuery({
    queryKey: ['regions', 'credit-hhi', year],
    queryFn: () => regionsApi.getCreditHhi(year).then(r => r.data),
    enabled: !!year,
  });
}

export function useLoanDepositRatio(year: number) {
  return useQuery({
    queryKey: ['regions', 'loan-deposit-ratio', year],
    queryFn: () => regionsApi.getLoanDepositRatio(year).then(r => r.data),
    enabled: !!year,
  });
}
