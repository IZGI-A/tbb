import { useQuery } from '@tanstack/react-query';
import { riskAnalysisApi } from '../api/client';
import type { ZScoreRanking, ZScoreTimeSeries, LCRiskRelationship } from '../types';

export function useZScoreRanking(year?: number, month?: number, accountingSystem?: string) {
  return useQuery<ZScoreRanking[]>({
    queryKey: ['risk', 'zscore', year, month, accountingSystem],
    queryFn: () => riskAnalysisApi.getZScore({
      year: year!, month: month!, accounting_system: accountingSystem,
    }).then(r => r.data),
    enabled: !!year && !!month,
  });
}

export function useZScoreTimeSeries(bankName?: string, accountingSystem?: string) {
  return useQuery<ZScoreTimeSeries[]>({
    queryKey: ['risk', 'zscore-ts', bankName, accountingSystem],
    queryFn: () => riskAnalysisApi.getZScoreTimeSeries({
      bank_name: bankName, accounting_system: accountingSystem,
    }).then(r => r.data),
  });
}

export function useLCRiskRelationship(year?: number, month?: number, accountingSystem?: string) {
  return useQuery<LCRiskRelationship[]>({
    queryKey: ['risk', 'lc-risk', year, month, accountingSystem],
    queryFn: () => riskAnalysisApi.getLCRisk({
      year: year!, month: month!, accounting_system: accountingSystem,
    }).then(r => r.data),
    enabled: !!year && !!month,
  });
}
