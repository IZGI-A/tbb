import { useQuery } from '@tanstack/react-query';
import { regionalLiquidityApi } from '../api/client';
import type { RegionalLiquidity } from '../types';

export function useRegionalLiquidity(
  year?: number,
  month?: number,
  accountingSystem?: string,
) {
  return useQuery<RegionalLiquidity[]>({
    queryKey: ['regional-liquidity', 'distribution', year, month, accountingSystem],
    queryFn: () =>
      regionalLiquidityApi
        .getDistribution({
          year: year!,
          month: month!,
          accounting_system: accountingSystem,
        })
        .then((r) => r.data),
    enabled: !!year && !!month,
  });
}
