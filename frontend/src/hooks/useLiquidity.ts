import { useQuery } from '@tanstack/react-query';
import { liquidityApi } from '../api/client';
import type { LiquidityCreation, LiquidityTimeSeries, LiquidityGroup, LiquidityGroupTimeSeries, LiquidityDecomposition } from '../types';

export function useLiquidityCreation(year?: number, month?: number, accountingSystem?: string) {
  return useQuery<LiquidityCreation[]>({
    queryKey: ['liquidity', 'creation', year, month, accountingSystem],
    queryFn: () => liquidityApi.getCreation({
      year: year!, month: month!, accounting_system: accountingSystem,
    }).then(r => r.data),
    enabled: !!year && !!month,
  });
}

export function useLiquidityTimeSeries(
  bankName?: string,
  fromYear?: number,
  toYear?: number,
  accountingSystem?: string,
) {
  return useQuery<LiquidityTimeSeries[]>({
    queryKey: ['liquidity', 'time-series', bankName, fromYear, toYear, accountingSystem],
    queryFn: () => liquidityApi.getTimeSeries({
      bank_name: bankName, from_year: fromYear, to_year: toYear,
      accounting_system: accountingSystem,
    }).then(r => r.data),
  });
}

export function useLiquidityGroups(year?: number, month?: number, accountingSystem?: string) {
  return useQuery<LiquidityGroup[]>({
    queryKey: ['liquidity', 'groups', year, month, accountingSystem],
    queryFn: () => liquidityApi.getGroups({
      year: year!, month: month!, accounting_system: accountingSystem,
    }).then(r => r.data),
    enabled: !!year && !!month,
  });
}

export function useLiquidityGroupTimeSeries(accountingSystem?: string, col?: string) {
  return useQuery<LiquidityGroupTimeSeries[]>({
    queryKey: ['liquidity', 'group-time-series', accountingSystem, col],
    queryFn: () => liquidityApi.getGroupTimeSeries({
      accounting_system: accountingSystem,
      col,
    }).then(r => r.data),
  });
}

export function useLiquidityGroupTimeSeriesArticle(accountingSystem?: string) {
  return useQuery<LiquidityGroupTimeSeries[]>({
    queryKey: ['liquidity', 'group-time-series-article', accountingSystem],
    queryFn: () => liquidityApi.getGroupTimeSeriesArticle({
      accounting_system: accountingSystem,
    }).then(r => r.data),
  });
}

export function useLiquidityDecomposition(
  bankName?: string,
  year?: number,
  month?: number,
  accountingSystem?: string,
) {
  return useQuery<LiquidityDecomposition>({
    queryKey: ['liquidity', 'decomposition', bankName, year, month, accountingSystem],
    queryFn: () => liquidityApi.getDecomposition({
      bank_name: bankName!, year: year!, month: month!,
      accounting_system: accountingSystem,
    }).then(r => r.data),
    enabled: !!bankName && !!year && !!month,
  });
}
