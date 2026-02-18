import React, { useState } from 'react';
import { Card, Select, Space, Table, Row, Col, Statistic, Tooltip, Tag } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import ScatterChart from '../components/charts/ScatterChart';
import LineChart from '../components/charts/LineChart';
import PieChart from '../components/charts/PieChart';
import YearMonthFilter from '../components/filters/YearMonthFilter';
import { useFinancialPeriods } from '../hooks/useFinancial';
import {
  useZScoreRanking,
  useZScoreTimeSeries,
  useLCRiskRelationship,
} from '../hooks/useRiskAnalysis';
import type { PeriodInfo, ZScoreRanking, ZScoreTimeSeries } from '../types';

const RiskAnalysis: React.FC = () => {
  const [year, setYear] = useState<number | undefined>();
  const [month, setMonth] = useState<number | undefined>();
  const [accountingSystem, setAccountingSystem] = useState<string | undefined>();
  const [selectedBank, setSelectedBank] = useState<string | undefined>();

  const { data: periods } = useFinancialPeriods();
  const periodList = (periods ?? []) as PeriodInfo[];
  const years = Array.from(new Set<number>(periodList.map(p => p.year_id))).sort((a, b) => b - a);
  const months = year
    ? Array.from(new Set<number>(periodList.filter(p => p.year_id === year).map(p => p.month_id))).sort((a, b) => b - a)
    : [];

  const { data: zscore, isLoading: zscoreLoading } = useZScoreRanking(year, month, accountingSystem);
  const { data: lcRisk, isLoading: lcRiskLoading } = useLCRiskRelationship(year, month, accountingSystem);
  const { data: bankTs, isLoading: bankTsLoading } = useZScoreTimeSeries(selectedBank, accountingSystem);

  // Summary stats
  const avgZScore = zscore && zscore.length > 0
    ? zscore.reduce((sum, b) => sum + (b.z_score ?? 0), 0) / zscore.length
    : null;
  const maxZScore = zscore && zscore.length > 0
    ? zscore.reduce((max, b) => (b.z_score ?? 0) > (max.z_score ?? 0) ? b : max)
    : null;
  const minZScore = zscore && zscore.length > 0
    ? zscore.reduce((min, b) => (b.z_score ?? Infinity) < (min.z_score ?? Infinity) ? b : min)
    : null;

  // Bank options from zscore data
  const bankOptions = (zscore ?? []).map(b => b.bank_name).sort().map(b => ({ value: b, label: b }));

  const columns = [
    {
      title: 'Banka',
      dataIndex: 'bank_name',
      key: 'bank_name',
      ellipsis: true,
      width: 280,
    },
    {
      title: 'Z-Score',
      dataIndex: 'z_score',
      key: 'z_score',
      sorter: (a: ZScoreRanking, b: ZScoreRanking) => (a.z_score ?? 0) - (b.z_score ?? 0),
      defaultSortOrder: 'descend' as const,
      render: (v: number | null) => v !== null ? v.toFixed(2) : '-',
      width: 120,
    },
    {
      title: 'Risk Seviyesi',
      key: 'risk_level',
      width: 140,
      filters: [
        { text: 'Cok Dusuk', value: 'Cok Dusuk' },
        { text: 'Dusuk', value: 'Dusuk' },
        { text: 'Orta', value: 'Orta' },
        { text: 'Yuksek', value: 'Yuksek' },
      ],
      onFilter: (value: any, record: ZScoreRanking) => {
        const z = record.z_score ?? 0;
        if (value === 'Cok Dusuk') return z >= 50;
        if (value === 'Dusuk') return z >= 20 && z < 50;
        if (value === 'Orta') return z >= 10 && z < 20;
        return z < 10;
      },
      render: (_: unknown, record: ZScoreRanking) => {
        const z = record.z_score ?? 0;
        if (z >= 50) return <Tag color="green">Cok Dusuk</Tag>;
        if (z >= 20) return <Tag color="blue">Dusuk</Tag>;
        if (z >= 10) return <Tag color="orange">Orta</Tag>;
        return <Tag color="red">Yuksek</Tag>;
      },
    },
    {
      title: 'ROA (%)',
      dataIndex: 'roa',
      key: 'roa',
      sorter: (a: ZScoreRanking, b: ZScoreRanking) => a.roa - b.roa,
      render: (v: number) => v.toFixed(2) + '%',
      width: 120,
    },
    {
      title: 'Sermaye Orani (%)',
      dataIndex: 'capital_ratio',
      key: 'capital_ratio',
      sorter: (a: ZScoreRanking, b: ZScoreRanking) => a.capital_ratio - b.capital_ratio,
      render: (v: number) => v.toFixed(2) + '%',
      width: 160,
    },
    {
      title: 'Toplam Aktif',
      dataIndex: 'total_assets',
      key: 'total_assets',
      sorter: (a: ZScoreRanking, b: ZScoreRanking) => a.total_assets - b.total_assets,
      render: (v: number) => (v / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 0 }) + ' M',
      width: 160,
    },
  ];

  return (
    <div>
      <h2>
        Risk Analizi{' '}
        <Tooltip title="Colak et al. (2024) — Z-Score = (Sermaye Orani + ROA) / σ(ROA). Yuksek Z-Score = dusuk risk (iflastan uzaklik). σ(ROA) 12 aylik hareketli standart sapma ile hesaplanir.">
          <InfoCircleOutlined style={{ fontSize: 16, color: '#999' }} />
        </Tooltip>
      </h2>

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
            placeholder="Banka secin (zaman serisi)"
            allowClear
            showSearch
            value={selectedBank}
            onChange={setSelectedBank}
            style={{ width: 300 }}
            options={bankOptions}
          />
        </Space>
      </Card>

      {/* Summary Stats */}
      {year && month && zscore && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col flex={1}>
            <Card>
              <Statistic
                title="Ort. Z-Score"
                value={avgZScore !== null ? avgZScore.toFixed(2) : '-'}
              />
            </Card>
          </Col>
          <Col flex={1}>
            <Card>
              <Statistic
                title="Banka Sayisi"
                value={zscore.length}
              />
            </Card>
          </Col>
          <Col flex={1}>
            <Card>
              <Statistic
                title="En Yuksek Z-Score"
                value={maxZScore?.z_score?.toFixed(2) ?? '-'}
                suffix={maxZScore ? ` (${maxZScore.bank_name.split(' ')[0]})` : ''}
              />
            </Card>
          </Col>
          <Col flex={1}>
            <Card>
              <Statistic
                title="En Dusuk Z-Score"
                value={minZScore?.z_score?.toFixed(2) ?? '-'}
                suffix={minZScore ? ` (${minZScore.bank_name.split(' ')[0]})` : ''}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* LC vs Z-Score Scatter + Risk Distribution */}
      {year && month && lcRisk && lcRisk.length > 0 && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={16}>
            <Card
              title={
                <span>
                  Likidite Yaratimi ve Risk Iliskisi{' '}
                  <Tooltip title="Colak et al. (2024): Yuksek likidite yaratimi banka riskini artirir (Z-Score duser). Scatter plot: her nokta bir banka.">
                    <InfoCircleOutlined style={{ fontSize: 14, color: '#999' }} />
                  </Tooltip>
                </span>
              }
              style={{ height: '100%' }}
            >
              <ScatterChart
                title=""
                xLabel="LC Nonfat (%)"
                yLabel="Z-Score"
                data={lcRisk.map(d => ({
                  name: d.bank_name,
                  value: [
                    Number((d.lc_nonfat * 100).toFixed(2)),
                    Number((d.z_score ?? 0).toFixed(2)),
                  ],
                }))}
                loading={lcRiskLoading}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card title="Risk Seviyesi Dagilimi" style={{ height: '100%' }}>
              <PieChart
                title=""
                donut
                data={(() => {
                  const scores = (zscore ?? []).map(b => b.z_score ?? 0);
                  return [
                    { name: 'Cok Dusuk (≥50)', value: scores.filter(z => z >= 50).length },
                    { name: 'Dusuk (20-50)', value: scores.filter(z => z >= 20 && z < 50).length },
                    { name: 'Orta (10-20)', value: scores.filter(z => z >= 10 && z < 20).length },
                    { name: 'Yuksek (<10)', value: scores.filter(z => z < 10).length },
                  ].filter(d => d.value > 0);
                })()}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Z-Score Time Series for selected bank */}
      {selectedBank && bankTs && bankTs.length > 0 && (
        <Card title={`${selectedBank} — Z-Score Zaman Serisi`} style={{ marginBottom: 16 }}>
          <LineChart
            title=""
            xData={bankTs.map(
              (p: ZScoreTimeSeries) => `${p.year_id}/${String(p.month_id).padStart(2, '0')}`
            )}
            series={[
              {
                name: 'Z-Score',
                data: bankTs.map((p: ZScoreTimeSeries) => Number((p.z_score ?? 0).toFixed(2))),
              },
            ]}
            loading={bankTsLoading}
          />
        </Card>
      )}

      {/* Z-Score Ranking Table */}
      {year && month && (
        <Card title="Banka Bazinda Z-Score Siralamasi" style={{ marginBottom: 16 }}>
          <Table
            columns={columns}
            dataSource={zscore ?? []}
            loading={zscoreLoading}
            rowKey="bank_name"
            pagination={{ pageSize: 15 }}
            scroll={{ x: 900 }}
            size="small"
          />
        </Card>
      )}
    </div>
  );
};

export default RiskAnalysis;
