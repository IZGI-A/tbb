import React, { useState } from 'react';
import { Card, Select, Space, Row, Col, Statistic, Empty, Grid } from 'antd';
import ReactECharts from 'echarts-for-react';
import LineChart from '../components/charts/LineChart';
import YearMonthFilter from '../components/filters/YearMonthFilter';
import { useFinancialPeriods, useFinancialBankNames } from '../hooks/useFinancial';
import {
  useLiquidityCreation,
  useLiquidityTimeSeries,
  useLiquidityDecomposition,
} from '../hooks/useLiquidity';
import type { PeriodInfo, LiquidityTimeSeries } from '../types';

const COLORS = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16'];

const BankComparison: React.FC = () => {
  const [year, setYear] = useState<number | undefined>(2025);
  const [month, setMonth] = useState<number | undefined>(9);
  const [accountingSystem, setAccountingSystem] = useState<string | undefined>('SOLO');
  const [selectedBanks, setSelectedBanks] = useState<string[]>([]);
  const [decompYear, setDecompYear] = useState<number | undefined>(2025);
  const [decompMonth, setDecompMonth] = useState<number | undefined>(9);
  const [decompAccounting, setDecompAccounting] = useState<string | undefined>('SOLO');
  const [decompositionBank, setDecompositionBank] = useState<string | undefined>();
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  const { data: periods } = useFinancialPeriods();
  const { data: bankNames } = useFinancialBankNames();
  const { data: creation } = useLiquidityCreation(year, month, accountingSystem);

  const periodList = (periods ?? []) as PeriodInfo[];
  const years = Array.from(new Set<number>(periodList.map(p => p.year_id))).sort((a, b) => b - a);
  const months = year
    ? Array.from(new Set<number>(periodList.filter(p => p.year_id === year).map(p => p.month_id))).sort((a, b) => b - a)
    : [];
  const decompMonths = decompYear
    ? Array.from(new Set<number>(periodList.filter(p => p.year_id === decompYear).map(p => p.month_id))).sort((a, b) => b - a)
    : [];

  // Time series for each selected bank
  const ts0 = useLiquidityTimeSeries(selectedBanks[0], undefined, undefined, accountingSystem);
  const ts1 = useLiquidityTimeSeries(selectedBanks[1], undefined, undefined, accountingSystem);
  const ts2 = useLiquidityTimeSeries(selectedBanks[2], undefined, undefined, accountingSystem);
  const ts3 = useLiquidityTimeSeries(selectedBanks[3], undefined, undefined, accountingSystem);
  const ts4 = useLiquidityTimeSeries(selectedBanks[4], undefined, undefined, accountingSystem);
  const ts5 = useLiquidityTimeSeries(selectedBanks[5], undefined, undefined, accountingSystem);
  const ts6 = useLiquidityTimeSeries(selectedBanks[6], undefined, undefined, accountingSystem);
  const ts7 = useLiquidityTimeSeries(selectedBanks[7], undefined, undefined, accountingSystem);
  const allTs = [ts0, ts1, ts2, ts3, ts4, ts5, ts6, ts7];

  // Decomposition for selected bank (uses its own year/month/accounting)
  const { data: decomposition } = useLiquidityDecomposition(
    decompositionBank, decompYear, decompMonth, decompAccounting,
  );

  // Build comparison line chart data
  const buildComparisonChart = () => {
    const activeSeries = selectedBanks.map((bank, i) => ({
      bank,
      data: allTs[i]?.data ?? [],
    })).filter(s => s.data.length > 0);

    if (activeSeries.length === 0) return { xData: [] as string[], series: [] as { name: string; data: (number | null)[] }[] };

    const allPeriods = Array.from(
      new Set(
        activeSeries.flatMap(s =>
          s.data.map((p: LiquidityTimeSeries) => `${p.year_id}/${String(p.month_id).padStart(2, '0')}`)
        )
      )
    ).sort();

    const series = activeSeries.map(s => {
      const lookup = new Map<string, number>();
      s.data.forEach((p: LiquidityTimeSeries) => {
        lookup.set(`${p.year_id}/${String(p.month_id).padStart(2, '0')}`, p.lc_nonfat);
      });
      return {
        name: s.bank,
        data: allPeriods.map(pd => {
          const val = lookup.get(pd);
          return val !== undefined ? Number((val * 100).toFixed(2)) : null;
        }),
      };
    });

    return { xData: allPeriods, series };
  };

  // Build bar chart for single-period comparison
  const buildBarComparison = () => {
    if (!creation || selectedBanks.length === 0) return { xData: [] as string[], data: [] as number[] };
    const filtered = creation.filter(c => selectedBanks.includes(c.bank_name));
    return {
      xData: filtered.map(c => c.bank_name),
      data: filtered.map(c => Number((c.lc_nonfat * 100).toFixed(2))),
    };
  };

  const comparison = buildComparisonChart();
  const barComparison = buildBarComparison();

  // Bank options filtered from creation data (LC analysis banks)
  const bankOptions = creation
    ? creation.map(c => c.bank_name).sort().map(b => ({ value: b, label: b }))
    : (bankNames ?? []).map((b: string) => ({ value: b, label: b }));

  return (
    <div>
      <h2>Banka Karsilastirmasi</h2>

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
          <Select
            mode="multiple"
            placeholder="Karsilastirilacak bankalari secin (maks 8)"
            value={selectedBanks}
            onChange={(vals: string[]) => setSelectedBanks(vals.slice(0, 8))}
            style={{ minWidth: isMobile ? undefined : 400, width: isMobile ? '100%' : undefined }}
            maxTagCount={3}
            showSearch
            options={bankOptions}
          />
        </Space>
      </Card>

      {selectedBanks.length === 0 && (
        <Card>
          <Empty description="Karsilastirmak icin banka secin" />
        </Card>
      )}

      {/* LC Bar Comparison (single period) */}
      {year && month && selectedBanks.length > 0 && (
        <Card title={`LC Karsilastirmasi — ${year}/${String(month).padStart(2, '0')}`} style={{ marginBottom: 16 }}>
          <ReactECharts
            style={{ height: Math.max(300, barComparison.xData.length * 40) }}
            option={{
              tooltip: {
                trigger: 'axis',
                formatter: (params: any) => {
                  const p = params[0];
                  return `<strong>${p.name}</strong><br/>${p.seriesName}: %${p.value}`;
                },
              },
              grid: { left: 8, right: 50, top: 8, bottom: 8, containLabel: true },
              xAxis: { type: 'value', axisLabel: { formatter: '%{value}' } },
              yAxis: {
                type: 'category',
                data: [...barComparison.xData].reverse(),
                axisLabel: { fontSize: 11, width: 180, overflow: 'truncate' },
              },
              series: [{
                name: 'LC Orani',
                type: 'bar',
                data: [...barComparison.data].reverse(),
                barMaxWidth: 22,
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
                  fontSize: 11,
                  color: '#555',
                  formatter: (p: any) => `%${p.value}`,
                },
              }],
            }}
          />
        </Card>
      )}

      {/* LC Time Series Comparison */}
      {selectedBanks.length > 0 && comparison.xData.length > 0 && (
        <Card title="LC Zaman Serisi Karsilastirmasi" style={{ marginBottom: 16 }}>
          <LineChart
            title=""
            xData={comparison.xData}
            series={comparison.series}
          />
        </Card>
      )}

      {/* LC Bilesen Analizi */}
      <Card title="LC Bilesen Analizi" style={{ marginBottom: 16 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <YearMonthFilter
            years={years}
            months={decompMonths}
            selectedYear={decompYear}
            selectedMonth={decompMonth}
            onYearChange={(y) => { setDecompYear(y); setDecompMonth(undefined); }}
            onMonthChange={setDecompMonth}
          />
          <Select
            placeholder="Muhasebe Sistemi"
            allowClear
            value={decompAccounting}
            onChange={setDecompAccounting}
            style={{ width: 200 }}
            options={[
              { value: 'SOLO', label: 'Solo' },
              { value: 'KONSOLİDE', label: 'Konsolide' },
            ]}
          />
          <Select
            placeholder="Bilesen analizi icin banka secin"
            allowClear
            showSearch
            value={decompositionBank}
            onChange={setDecompositionBank}
            style={{ width: isMobile ? '100%' : 400 }}
            options={bankOptions}
          />
        </Space>

        {!decompositionBank && (
          <Empty description="Bilesen analizi icin banka secin" />
        )}

        {decompositionBank && !decomposition && decompYear && decompMonth && (
          <Empty description="Veri bulunamadi" />
        )}

        {decomposition && (() => {
          const components = [
            { name: 'Likit Olmayan Varliklar (+)', value: Number((decomposition.weighted_components.illiquid_assets_contrib * 100).toFixed(2)), positive: true },
            { name: 'Likit Yukumlulukler (+)', value: Number((decomposition.weighted_components.liquid_liabilities_contrib * 100).toFixed(2)), positive: true },
            { name: 'Likit Varliklar (-)', value: Number((decomposition.weighted_components.liquid_assets_drag * 100).toFixed(2)), positive: false },
            { name: 'Likit Olm. Yuk. + Ozkaynak (-)', value: Number((decomposition.weighted_components.illiquid_liab_equity_drag * 100).toFixed(2)), positive: false },
          ];
          return (
            <>
              <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col xs={24} sm={12} lg={4}>
                  <Card style={{ background: '#f0f5ff', border: '1px solid #d6e4ff' }}>
                    <Statistic
                      title="LC (Cat Nonfat)"
                      value={(decomposition.lc_nonfat * 100).toFixed(2)}
                      suffix="%"
                      valueStyle={{ fontWeight: 700, fontSize: 22 }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={12} lg={5}>
                  <Card style={{ background: '#f6ffed', border: '1px solid #d9f7be' }}>
                    <Statistic
                      title="Likit Olmayan Varlik (+)"
                      value={(decomposition.weighted_components.illiquid_assets_contrib * 100).toFixed(2)}
                      suffix="%"
                      valueStyle={{ color: '#389e0d' }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={12} lg={5}>
                  <Card style={{ background: '#f6ffed', border: '1px solid #d9f7be' }}>
                    <Statistic
                      title="Likit Yukumluluk (+)"
                      value={(decomposition.weighted_components.liquid_liabilities_contrib * 100).toFixed(2)}
                      suffix="%"
                      valueStyle={{ color: '#389e0d' }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={12} lg={5}>
                  <Card style={{ background: '#fff2f0', border: '1px solid #ffccc7' }}>
                    <Statistic
                      title="Likit Varlik (-)"
                      value={(decomposition.weighted_components.liquid_assets_drag * 100).toFixed(2)}
                      suffix="%"
                      valueStyle={{ color: '#cf1322' }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={12} lg={5}>
                  <Card style={{ background: '#fff2f0', border: '1px solid #ffccc7' }}>
                    <Statistic
                      title="Likit Olm. Yuk. + Ozkaynak (-)"
                      value={(decomposition.weighted_components.illiquid_liab_equity_drag * 100).toFixed(2)}
                      suffix="%"
                      valueStyle={{ color: '#cf1322' }}
                    />
                  </Card>
                </Col>
              </Row>
              <ReactECharts
                style={{ height: isMobile ? 280 : 350 }}
                option={{
                  tooltip: {
                    trigger: 'axis',
                    formatter: (params: any) => {
                      const p = params[0];
                      return `<strong>${p.name}</strong><br/>Katki: %${p.value}`;
                    },
                  },
                  grid: { left: 8, right: 50, top: 16, bottom: 8, containLabel: true },
                  xAxis: {
                    type: 'category',
                    data: components.map(c => c.name),
                    axisLabel: { fontSize: 10, interval: 0, width: 120, overflow: 'break' },
                  },
                  yAxis: {
                    type: 'value',
                    axisLabel: { formatter: '%{value}' },
                    splitLine: { lineStyle: { type: 'dashed', color: '#e8e8e8' } },
                  },
                  series: [{
                    name: 'Katki',
                    type: 'bar',
                    data: components.map(c => ({
                      value: c.value,
                      itemStyle: {
                        borderRadius: c.positive ? [4, 4, 0, 0] : [0, 0, 4, 4],
                        color: c.positive
                          ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#52c41a' }, { offset: 1, color: '#95de64' }] }
                          : { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#ff7875' }, { offset: 1, color: '#f5222d' }] },
                      },
                    })),
                    barMaxWidth: 60,
                    label: {
                      show: true,
                      position: 'top',
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#333',
                      formatter: (p: any) => `%${p.value}`,
                    },
                  }],
                }}
              />
            </>
          );
        })()}
      </Card>
    </div>
  );
};

export default BankComparison;
