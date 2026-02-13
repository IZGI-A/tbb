import { useQuery } from '@tanstack/react-query';
import { riskCenterApi } from '../api/client';

export function useRiskCenterData(params: Record<string, unknown>) {
  return useQuery({
    queryKey: ['risk-center', 'data', params],
    queryFn: () => riskCenterApi.getData(params).then(r => r.data),
  });
}

export function useRiskCenterReports() {
  return useQuery({
    queryKey: ['risk-center', 'reports'],
    queryFn: () => riskCenterApi.getReports().then(r => r.data),
  });
}

export function useRiskCenterCategories(reportName: string) {
  return useQuery({
    queryKey: ['risk-center', 'categories', reportName],
    queryFn: () => riskCenterApi.getCategories(reportName).then(r => r.data),
    enabled: !!reportName,
  });
}
