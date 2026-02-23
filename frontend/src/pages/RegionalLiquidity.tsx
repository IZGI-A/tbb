import React, { useState, useMemo } from 'react';
import { Card, Select, Space, Table, Row, Col, Statistic, Spin, Alert, Grid } from 'antd';
import ReactECharts from 'echarts-for-react';
import YearMonthFilter from '../components/filters/YearMonthFilter';
import { useFinancialPeriods } from '../hooks/useFinancial';
import { useRegionalLiquidity } from '../hooks/useRegionalLiquidity';
import type { PeriodInfo, RegionalLiquidity as RegionalLiquidityType } from '../types';

const RegionalLiquidity: React.FC = () => {
  const [year, setYear] = useState<number | undefined>(2025);
  const [month, setMonth] = useState<number | undefined>(9);
  const [accountingSystem, setAccountingSystem] = useState<string | undefined>('SOLO');

  const { data: periods } = useFinancialPeriods();
  const periodList = (periods ?? []) as PeriodInfo[];
  const years = Array.from(new Set<number>(periodList.map(p => p.year_id))).sort((a, b) => b - a);
  const months = year
    ? Array.from(new Set<number>(periodList.filter(p => p.year_id === year).map(p => p.month_id))).sort((a, b) => b - a)
    : [];

  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  const { data, isLoading, error } = useRegionalLiquidity(year, month, accountingSystem);

  const top20ByLC = useMemo(() => {
    if (!data) return [];
    return [...data].sort((a, b) => b.lc_amount - a.lc_amount).slice(0, 20);
  }, [data]);

  const top20ByBranch = useMemo(() => {
    if (!data) return [];
    return [...data].sort((a, b) => b.branch_count - a.branch_count).slice(0, 20);
  }, [data]);

  const totalBranches = useMemo(() => {
    if (!data) return 0;
    return data.reduce((sum, d) => sum + d.branch_count, 0);
  }, [data]);

  const columns = [
    {
      title: 'Il',
      dataIndex: 'city',
      key: 'city',
      sorter: (a: RegionalLiquidityType, b: RegionalLiquidityType) =>
        a.city.localeCompare(b.city, 'tr'),
      width: 150,
    },
    {
      title: 'LC Tutari (Milyon TL)',
      dataIndex: 'lc_amount',
      key: 'lc_amount',
      sorter: (a: RegionalLiquidityType, b: RegionalLiquidityType) =>
        a.lc_amount - b.lc_amount,
      defaultSortOrder: 'descend' as const,
      render: (v: number) =>
        (v / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 0 }),
      width: 180,
    },
    {
      title: 'Sube Sayisi',
      dataIndex: 'branch_count',
      key: 'branch_count',
      sorter: (a: RegionalLiquidityType, b: RegionalLiquidityType) =>
        a.branch_count - b.branch_count,
      width: 130,
    },
    {
      title: 'Banka Sayisi',
      dataIndex: 'bank_count',
      key: 'bank_count',
      sorter: (a: RegionalLiquidityType, b: RegionalLiquidityType) =>
        a.bank_count - b.bank_count,
      width: 130,
    },
    {
      title: 'Ort. LC Orani',
      dataIndex: 'avg_lc_ratio',
      key: 'avg_lc_ratio',
      sorter: (a: RegionalLiquidityType, b: RegionalLiquidityType) =>
        (a.avg_lc_ratio ?? 0) - (b.avg_lc_ratio ?? 0),
      render: (v: number | null) =>
        v !== null ? '%' + (v * 100).toFixed(2) : '-',
      width: 140,
    },
  ];

  return (
    <div>
      <h2>Bolgesel Likidite Analizi</h2>

      {/* Filters */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <YearMonthFilter
            years={years}
            months={months}
            selectedYear={year}
            selectedMonth={month}
            onYearChange={(y) => { setYear(y); setMonth(undefined); }}
            onMonthChange={setMonth}
          />
          <Select
            placeholder="Muhasebe Sistemi"
            allowClear
            value={accountingSystem}
            onChange={setAccountingSystem}
            style={{ width: 200 }}
            options={[
              { value: 'SOLO', label: 'Solo' },
              { value: 'KONSOLİDE', label: 'Konsolide' },
            ]}
          />
        </Space>
      </Card>

      {isLoading && (
        <Card>
          <Spin tip="Bolgesel veriler yukleniyor..." size="large">
            <div style={{ padding: 50 }} />
          </Spin>
        </Card>
      )}

      {error && (
        <Alert type="error" message="Bolgesel veriler yuklenemedi" style={{ marginBottom: 16 }} />
      )}

      {data && data.length > 0 && (
        <>
          {/* Summary Stats */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} md={12} lg={6}>
              <Card><Statistic title="Toplam Il Sayisi" value={data.length} /></Card>
            </Col>
            <Col xs={12} md={12} lg={6}>
              <Card><Statistic title="Toplam Sube" value={totalBranches.toLocaleString('tr-TR')} /></Card>
            </Col>
            <Col xs={12} md={12} lg={6}>
              <Card>
                <Statistic
                  title="En Yuksek LC (Il)"
                  value={top20ByLC[0]?.city ?? '-'}
                />
              </Card>
            </Col>
            <Col xs={12} md={12} lg={6}>
              <Card>
                <Statistic
                  title="En Yuksek LC Tutari"
                  value={top20ByLC[0]
                    ? (top20ByLC[0].lc_amount / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 0 })
                    : '-'}
                  suffix="M TL"
                />
              </Card>
            </Col>
          </Row>

          {/* Charts Side by Side */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            {/* Top 20 by LC - Horizontal Bar */}
            <Col xs={24} lg={12}>
              <Card title="En Yuksek LC - Ilk 20 Il" style={{ height: '100%' }}>
                <ReactECharts
                  style={{ height: isMobile ? 400 : 520 }}
                  showLoading={isLoading}
                  option={{
                    tooltip: {
                      trigger: 'axis',
                      formatter: (params: any) => {
                        const p = params[0];
                        return `<strong>${p.name}</strong><br/>${p.seriesName}: ${Number(p.value).toLocaleString('tr-TR')} M TL`;
                      },
                    },
                    grid: { left: 8, right: 40, top: 8, bottom: 8, containLabel: true },
                    xAxis: { type: 'value', axisLabel: { formatter: '{value}' } },
                    yAxis: {
                      type: 'category',
                      data: [...top20ByLC].reverse().map(d => d.city),
                      axisLabel: { fontSize: 11 },
                    },
                    series: [{
                      name: 'LC Tutari',
                      type: 'bar',
                      data: [...top20ByLC].reverse().map(d => Math.round(d.lc_amount / 1e6)),
                      barMaxWidth: 18,
                      itemStyle: {
                        borderRadius: [0, 4, 4, 0],
                        color: {
                          type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
                          colorStops: [
                            { offset: 0, color: '#1677ff' },
                            { offset: 1, color: '#69b1ff' },
                          ],
                        } as any,
                      },
                      label: {
                        show: true,
                        position: 'right',
                        fontSize: 10,
                        color: '#666',
                        formatter: (p: any) => Number(p.value).toLocaleString('tr-TR'),
                      },
                    }],
                  }}
                />
              </Card>
            </Col>

            {/* Top 20 by Branch Count - Horizontal Bar */}
            <Col xs={24} lg={12}>
              <Card title="Sube Dagilimi - Ilk 20 Il" style={{ height: '100%' }}>
                <ReactECharts
                  style={{ height: isMobile ? 400 : 520 }}
                  showLoading={isLoading}
                  option={{
                    tooltip: {
                      trigger: 'axis',
                      formatter: (params: any) => {
                        const p = params[0];
                        return `<strong>${p.name}</strong><br/>${p.seriesName}: ${Number(p.value).toLocaleString('tr-TR')}`;
                      },
                    },
                    grid: { left: 8, right: 40, top: 8, bottom: 8, containLabel: true },
                    xAxis: { type: 'value', axisLabel: { formatter: '{value}' } },
                    yAxis: {
                      type: 'category',
                      data: [...top20ByBranch].reverse().map(d => d.city),
                      axisLabel: { fontSize: 11 },
                    },
                    series: [{
                      name: 'Sube Sayisi',
                      type: 'bar',
                      data: [...top20ByBranch].reverse().map(d => d.branch_count),
                      barMaxWidth: 18,
                      itemStyle: {
                        borderRadius: [0, 4, 4, 0],
                        color: {
                          type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
                          colorStops: [
                            { offset: 0, color: '#52c41a' },
                            { offset: 1, color: '#95de64' },
                          ],
                        } as any,
                      },
                      label: {
                        show: true,
                        position: 'right',
                        fontSize: 10,
                        color: '#666',
                        formatter: (p: any) => Number(p.value).toLocaleString('tr-TR'),
                      },
                    }],
                  }}
                />
              </Card>
            </Col>
          </Row>

          {/* Full Table */}
          <Card title="Tum Iller" style={{ marginBottom: 16 }}>
            <Table
              columns={columns}
              dataSource={data}
              rowKey="city"
              pagination={{ pageSize: 20 }}
              scroll={{ x: 700 }}
              size="small"
            />
          </Card>
        </>
      )}
    </div>
  );
};

export default RegionalLiquidity;
