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
import { useFinancialSummary, useFinancialTimeSeries } from '../hooks/useFinancial';
import { useBanks, useBankDashboardStats } from '../hooks/useBanks';
import { useRegionComparison, useRegionMetrics, useRegionPeriods } from '../hooks/useRegions';
import type { BankInfo, DashboardStats } from '../types';

const formatAmount = (val: number | null | undefined) => {
  if (!val) return '0';
  if (val >= 1e12) return `${(val / 1e12).toFixed(1)}T TL`;
  if (val >= 1e9) return `${(val / 1e9).toFixed(1)}B TL`;
  if (val >= 1e6) return `${(val / 1e6).toFixed(1)}M TL`;
  return String(val);
};

const Dashboard: React.FC = () => {
  const { data: banks, isLoading: banksLoading } = useBanks();
  const { data: dashStats, isLoading: dashStatsLoading } = useBankDashboardStats();
  const { data: summary, isLoading: summaryLoading } = useFinancialSummary({});
  const { data: timeSeries, isLoading: tsLoading } = useFinancialTimeSeries({
    bank_name: 'Türkiye Bankacılık Sistemi',
  });
  const { data: regionMetrics } = useRegionMetrics();
  const { data: regionPeriods } = useRegionPeriods();

  const [selectedMetric, setSelectedMetric] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<number>(0);

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
  }, [regionPeriods, selectedYear]);

  const { data: regionComparison, isLoading: regionCompLoading } = useRegionComparison(
    selectedMetric,
    selectedYear,
  );

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
      <h2>Turkiye Bankacilik Sektoru Dashboard</h2>

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

      {/* Row 4: Regional Comparison with Filters */}
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
