import { useQuery } from '@tanstack/react-query';
import { banksApi } from '../api/client';

export function useBanks() {
  return useQuery({
    queryKey: ['banks'],
    queryFn: () => banksApi.getAll().then(r => r.data),
  });
}

export function useBankSearch(query: string) {
  return useQuery({
    queryKey: ['banks', 'search', query],
    queryFn: () => banksApi.search(query).then(r => r.data),
    enabled: query.length > 0,
  });
}

export function useBankBranches(bankName: string, city?: string) {
  return useQuery({
    queryKey: ['banks', bankName, 'branches', city],
    queryFn: () => banksApi.getBranches(bankName, city).then(r => r.data),
    enabled: !!bankName,
  });
}

export function useBankAtms(bankName: string, city?: string) {
  return useQuery({
    queryKey: ['banks', bankName, 'atms', city],
    queryFn: () => banksApi.getAtms(bankName, city).then(r => r.data),
    enabled: !!bankName,
  });
}

export function useBankHistory(bankName: string) {
  return useQuery({
    queryKey: ['banks', bankName, 'history'],
    queryFn: () => banksApi.getHistory(bankName).then(r => r.data),
    enabled: !!bankName,
  });
}

export function useBankDashboardStats() {
  return useQuery({
    queryKey: ['banks', 'dashboard-stats'],
    queryFn: () => banksApi.getDashboardStats().then(r => r.data),
  });
}
