import React, { useMemo, useState } from 'react';
import { Card, Col, Row, Statistic, Spin, Select, Space } from 'antd';
import {
  BankOutlined,
  HomeOutlined,
  DesktopOutlined,
  DollarOutlined,
} from '@ant-design/icons';
import LineChart from '../components/charts/LineChart';
import BarChart from '../components/charts/BarChart';
import PieChart from '../components/charts/PieChart';
import { useFinancialSummary, useFinancialTimeSeries, useFinancialPeriods, useFinancialRatioTypes, useFinancialRatios } from '../hooks/useFinancial';
import { useBanks, useBankDashboardStats } from '../hooks/useBanks';
import { useRegionComparison, useRegionMetrics, useRegionPeriods, useLoanDepositRatio, useCreditHhi } from '../hooks/useRegions';
import type { BankInfo, BankRatios, DashboardStats } from '../types';

const formatAmount = (val: number | null | undefined) => {
  if (!val) return '0';
  if (val >= 1e12) return `${(val / 1e12).toFixed(1)}T TL`;
  if (val >= 1e9) return `${(val / 1e9).toFixed(1)}B TL`;
  if (val >= 1e6) return `${(val / 1e6).toFixed(1)}M TL`;
  return String(val);
};

const Dashboard: React.FC = () => {
  const [selectedMetric, setSelectedMetric] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<number>(0);
  const [ldrYear, setLdrYear] = useState<number>(0);
  const [hhiYear, setHhiYear] = useState<number>(0);
  const [hhiSectors, setHhiSectors] = useState<string[]>([]);
  const [ratioYear, setRatioYear] = useState<number>(0);
  const [ratioMonth, setRatioMonth] = useState<number>(0);
  const [selectedRatio, setSelectedRatio] = useState<string>('ROA');
  const [accountingSystem, setAccountingSystem] = useState<string | undefined>(undefined);

  const { data: banks, isLoading: banksLoading } = useBanks();
  const { data: dashStats, isLoading: dashStatsLoading } = useBankDashboardStats();
  const { data: summary, isLoading: summaryLoading } = useFinancialSummary({
    ...(accountingSystem ? { accounting_system: accountingSystem } : {}),
  });
  const { data: timeSeries, isLoading: tsLoading } = useFinancialTimeSeries({
    bank_name: 'Türkiye Bankacılık Sistemi',
    ...(accountingSystem ? { accounting_system: accountingSystem } : {}),
  });
  const { data: regionMetrics } = useRegionMetrics();
  const { data: regionPeriods } = useRegionPeriods();
  const { data: finPeriods } = useFinancialPeriods();
  const { data: ratioTypes } = useFinancialRatioTypes();

  // Set default metric/year when data loads
  React.useEffect(() => {
    if (regionMetrics?.length && !selectedMetric) {
      setSelectedMetric(regionMetrics[0]);
    }
  }, [regionMetrics, selectedMetric]);

  React.useEffect(() => {
    if (regionPeriods?.length && !selectedYear) {
      setSelectedYear(regionPeriods[0].year_id);
    }
    if (regionPeriods?.length && !ldrYear) {
      setLdrYear(regionPeriods[0].year_id);
    }
    if (regionPeriods?.length && !hhiYear) {
      setHhiYear(regionPeriods[0].year_id);
    }
  }, [regionPeriods, selectedYear, ldrYear, hhiYear]);

  React.useEffect(() => {
    if (finPeriods?.length && !ratioYear) {
      setRatioYear(finPeriods[0].year_id);
      setRatioMonth(finPeriods[0].month_id);
    }
  }, [finPeriods, ratioYear]);

  const { data: regionComparison, isLoading: regionCompLoading } = useRegionComparison(
    selectedMetric,
    selectedYear,
  );

  const { data: ldrData, isLoading: ldrLoading } = useLoanDepositRatio(ldrYear);
  const { data: hhiData, isLoading: hhiLoading } = useCreditHhi(hhiYear);
  const { data: ratioData, isLoading: ratioLoading } = useFinancialRatios(ratioYear, ratioMonth, accountingSystem);

  // Top 20 regions by LDR for chart readability
  const ldrChartData = useMemo(() => {
    if (!ldrData) return [];
    return (ldrData as { region: string; ratio: number | null }[])
      .filter((r) => r.ratio != null)
      .slice(0, 20);
  }, [ldrData]);

  // HHI data with sector shares
  type HhiRow = { region: string; hhi: number; dominant_sector: string; shares: Record<string, number> };
  const hhiRows = (hhiData ?? []) as HhiRow[];

  const allSectors = useMemo(() => {
    if (!hhiRows.length) return [];
    return Object.keys(hhiRows[0]?.shares ?? {}).sort();
  }, [hhiRows]);

  // Set default: all sectors selected
  React.useEffect(() => {
    if (allSectors.length && !hhiSectors.length) {
      setHhiSectors(allSectors);
    }
  }, [allSectors, hhiSectors.length]);

  const hhiFiltered = useMemo(() => {
    if (!hhiRows.length || !hhiSectors.length) return [];
    // Re-calculate HHI based on selected sectors only
    return hhiRows
      .map((r) => {
        const filteredShares: Record<string, number> = {};
        let total = 0;
        for (const s of hhiSectors) {
          const val = r.shares[s] ?? 0;
          filteredShares[s] = val;
          total += val;
        }
        return { ...r, filteredShares, filteredTotal: total };
      })
      .filter((r) => r.filteredTotal > 0)
      .slice(0, 20);
  }, [hhiRows, hhiSectors]);

  // Financial ratio chart data
  const ratioChartData = useMemo(() => {
    if (!ratioData) return [];
    return (ratioData as BankRatios[])
      .filter((r) => r[selectedRatio as keyof BankRatios] != null)
      .map((r) => ({
        bank: r.bank_name.replace(/ A\.Ş\.?$/i, '').replace(/ Bankası$/i, ''),
        value: r[selectedRatio as keyof BankRatios] as number,
      }))
      .sort((a, b) => b.value - a.value);
  }, [ratioData, selectedRatio]);

  const currentRatioType = ratioTypes?.find((t) => t.key === selectedRatio);

  const totalAssets = summary?.find(
    (s: { metric: string }) =>
      s.metric.toLowerCase().includes('aktif') || s.metric.toLowerCase().includes('varlik'),
  );

  // Client-side aggregations for pie charts
  const bankGroupData = useMemo(() => {
    if (!banks) return [];
    const groups: Record<string, number> = {};
    (banks as BankInfo[]).forEach((b) => {
      const g = b.bank_group || 'Belirtilmemis';
      groups[g] = (groups[g] || 0) + 1;
    });
    return Object.entries(groups).map(([name, value]) => ({ name, value }));
  }, [banks]);

  const subGroupData = useMemo(() => {
    if (!banks) return [];
    const subs: Record<string, number> = {};
    (banks as BankInfo[]).forEach((b) => {
      const sg = b.sub_bank_group || 'Belirtilmemis';
      subs[sg] = (subs[sg] || 0) + 1;
    });
    return Object.entries(subs).map(([name, value]) => ({ name, value }));
  }, [banks]);

  const stats = dashStats as DashboardStats | undefined;

  return (
    <div>
      <Space style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>Turkiye Bankacilik Sektoru Dashboard</h2>
        <Select
          placeholder="Muhasebe Sistemi"
          allowClear
          value={accountingSystem}
          onChange={setAccountingSystem}
          style={{ width: 180 }}
          options={[
            { value: 'SOLO', label: 'Solo' },
            { value: 'KONSOLİDE', label: 'Konsolide' },
          ]}
        />
      </Space>

      {/* Row 1: KPI Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Banka Sayisi"
              value={banks?.length ?? 0}
              prefix={<BankOutlined />}
              loading={banksLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Sube Sayisi"
              value={stats?.total_branches ?? 0}
              prefix={<HomeOutlined />}
              loading={dashStatsLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="ATM Sayisi"
              value={stats?.total_atms ?? 0}
              prefix={<DesktopOutlined />}
              loading={dashStatsLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Toplam Aktifler"
              value={formatAmount(totalAssets?.total)}
              prefix={<DollarOutlined />}
              loading={summaryLoading}
            />
          </Card>
        </Col>
      </Row>

      {/* Row 2: Bank Distribution Pie Charts */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12}>
          <Card>
            <PieChart
              title="Banka Grubu Dagilimi"
              data={bankGroupData}
              loading={banksLoading}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card>
            <PieChart
              title="Alt Grup Dagilimi"
              data={subGroupData}
              loading={banksLoading}
              donut
            />
          </Card>
        </Col>
      </Row>

      {/* Row 3: Geographic Distribution Bar Charts */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12}>
          <Card>
            <BarChart
              title="Illere Gore Sube Sayisi (Top 15)"
              xData={stats?.branch_by_city?.map((b) => b.city) ?? []}
              series={[
                {
                  name: 'Sube Sayisi',
                  data: stats?.branch_by_city?.map((b) => b.count) ?? [],
                },
              ]}
              loading={dashStatsLoading}
              horizontal
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card>
            <BarChart
              title="Illere Gore ATM Sayisi (Top 15)"
              xData={stats?.atm_by_city?.map((a) => a.city) ?? []}
              series={[
                {
                  name: 'ATM Sayisi',
                  data: stats?.atm_by_city?.map((a) => a.count) ?? [],
                },
              ]}
              loading={dashStatsLoading}
              horizontal
            />
          </Card>
        </Col>
      </Row>

      {/* Row 4: Loan-to-Deposit Ratio */}
      <Card style={{ marginBottom: 24 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <h4 style={{ margin: 0 }}>Kredi / Mevduat Orani</h4>
          <Select
            placeholder="Yil secin"
            value={ldrYear || undefined}
            onChange={setLdrYear}
            style={{ width: 150 }}
            options={regionPeriods?.map((p: { year_id: number }) => ({
              value: p.year_id,
              label: String(p.year_id),
            }))}
          />
        </Space>
        {ldrLoading ? (
          <Spin />
        ) : (
          <BarChart
            title={`Bolgesel Kredi/Mevduat Orani (${ldrYear || ''})`}
            xData={ldrChartData.map((r) => r.region)}
            series={[
              {
                name: 'Kredi/Mevduat Orani',
                data: ldrChartData.map((r) => r.ratio),
              },
            ]}
            loading={ldrLoading}
            horizontal
          />
        )}
      </Card>

      {/* Row 5: Credit HHI Concentration with Sector Breakdown */}
      <Card style={{ marginBottom: 24 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <h4 style={{ margin: 0 }}>Kredi Sektorel Yogunlasma (HHI)</h4>
          <Select
            placeholder="Yil secin"
            value={hhiYear || undefined}
            onChange={setHhiYear}
            style={{ width: 150 }}
            options={regionPeriods?.map((p: { year_id: number }) => ({
              value: p.year_id,
              label: String(p.year_id),
            }))}
          />
          <Select
            mode="multiple"
            placeholder="Sektor secin"
            value={hhiSectors}
            onChange={setHhiSectors}
            style={{ minWidth: 300 }}
            options={allSectors.map((s) => ({ value: s, label: s }))}
          />
        </Space>
        <p style={{ color: '#888', fontSize: 12, margin: '0 0 12px' }}>
          HHI &lt; 1500: Dusuk yogunlasma | 1500-2500: Orta | &gt; 2500: Yuksek yogunlasma. Barlar sektorel paylari (%) gosterir.
        </p>
        {hhiLoading ? (
          <Spin />
        ) : (
          <BarChart
            title={`Sektorel Kredi Paylari ve HHI (${hhiYear || ''})`}
            xData={hhiFiltered.map((r) => `${r.region} (HHI: ${r.hhi})`)}
            series={hhiSectors.map((sector) => ({
              name: sector,
              data: hhiFiltered.map((r) => r.filteredShares[sector] ?? 0),
            }))}
            loading={hhiLoading}
            horizontal
            stacked
          />
        )}
      </Card>

      {/* Row 6: Financial Ratio Analysis */}
      <Card style={{ marginBottom: 24 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <h4 style={{ margin: 0 }}>Finansal Oran Analizi</h4>
          <Select
            placeholder="Donem secin"
            value={ratioYear && ratioMonth ? `${ratioYear}/${ratioMonth}` : undefined}
            onChange={(val: string) => {
              const [y, m] = val.split('/').map(Number);
              setRatioYear(y);
              setRatioMonth(m);
            }}
            style={{ width: 150 }}
            options={finPeriods?.map((p) => ({
              value: `${p.year_id}/${p.month_id}`,
              label: `${p.year_id}/${p.month_id}`,
            }))}
          />
          <Select
            placeholder="Oran secin"
            value={selectedRatio}
            onChange={setSelectedRatio}
            style={{ width: 280 }}
            options={ratioTypes?.map((t) => ({
              value: t.key,
              label: t.label,
            }))}
          />
        </Space>
        {currentRatioType && (
          <p style={{ color: '#888', fontSize: 12, margin: '0 0 12px' }}>
            {currentRatioType.desc}
          </p>
        )}
        {ratioLoading ? (
          <Spin />
        ) : (
          <BarChart
            title={`${currentRatioType?.label || selectedRatio} (${ratioYear}/${ratioMonth})`}
            xData={ratioChartData.map((r) => r.bank)}
            series={[
              {
                name: currentRatioType?.label || selectedRatio,
                data: ratioChartData.map((r) => r.value),
              },
            ]}
            loading={ratioLoading}
            horizontal
          />
        )}
      </Card>

      {/* Row 7: Regional Comparison with Filters */}
      <Card style={{ marginBottom: 24 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <Select
            placeholder="Metrik secin"
            value={selectedMetric || undefined}
            onChange={setSelectedMetric}
            style={{ width: 300 }}
            options={regionMetrics?.map((m: string) => ({ value: m, label: m }))}
          />
          <Select
            placeholder="Yil secin"
            value={selectedYear || undefined}
            onChange={setSelectedYear}
            style={{ width: 150 }}
            options={regionPeriods?.map((p: { year_id: number }) => ({
              value: p.year_id,
              label: String(p.year_id),
            }))}
          />
        </Space>
        {regionCompLoading ? (
          <Spin />
        ) : (
          <BarChart
            title={`Bolgesel Karsilastirma: ${selectedMetric || ''}`}
            xData={regionComparison?.map((r: { region: string }) => r.region) ?? []}
            series={[
              {
                name: selectedMetric || 'Deger',
                data:
                  regionComparison?.map((r: { value: number | null }) => r.value) ?? [],
              },
            ]}
            loading={regionCompLoading}
          />
        )}
      </Card>

      {/* Row 5: Sector Trend Line Chart */}
      <Card>
        {tsLoading ? (
          <Spin />
        ) : (
          <LineChart
            title="Sektor Toplam Trend"
            xData={(timeSeries ?? []).map(
              (p: { year_id: number; month_id: number }) => `${p.year_id}/${p.month_id}`,
            )}
            series={[
              {
                name: 'Toplam',
                data: (timeSeries ?? []).map(
                  (p: { amount_total: number | null }) => p.amount_total,
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
};

export default Dashboard;
