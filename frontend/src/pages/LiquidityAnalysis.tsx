import React, { useState } from 'react';
import { Card, Select, Space, Table, Row, Col, Statistic, Tooltip } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import LineChart from '../components/charts/LineChart';
import YearMonthFilter from '../components/filters/YearMonthFilter';
import { useFinancialPeriods } from '../hooks/useFinancial';
import {
  useLiquidityCreation,
  useLiquidityGroupTimeSeries,
} from '../hooks/useLiquidity';
import type { PeriodInfo, LiquidityCreation, LiquidityGroupTimeSeries } from '../types';

const LiquidityAnalysis: React.FC = () => {
  const [year, setYear] = useState<number | undefined>(2025);
  const [month, setMonth] = useState<number | undefined>(9);
  const [accountingSystem, setAccountingSystem] = useState<string | undefined>('SOLO');
  const { data: periods } = useFinancialPeriods();

  const periodList = (periods ?? []) as PeriodInfo[];
  const years: number[] = Array.from(new Set<number>(periodList.map(p => p.year_id))).sort(
    (a, b) => b - a
  );
  const months: number[] = year
    ? Array.from(
        new Set<number>(
          periodList.filter(p => p.year_id === year).map(p => p.month_id)
        )
      ).sort((a, b) => b - a)
    : [];

  // Queries
  const { data: creation, isLoading: creationLoading } = useLiquidityCreation(
    year, month, accountingSystem,
  );
  const { data: groupTs, isLoading: groupTsLoading } = useLiquidityGroupTimeSeries(
    accountingSystem,
  );

  // Sector average (arithmetic mean)
  const sectorAvg = creation && creation.length > 0
    ? creation.reduce((sum, b) => sum + b.lc_nonfat, 0) / creation.length
    : null;

  // Sector total LC (monetary amount: sum of each bank's LC numerator)
  const sectorTotalLC = creation && creation.length > 0
    ? creation.reduce((sum, b) => sum + b.lc_nonfat * b.total_assets, 0)
    : null;

  const columns = [
    {
      title: 'Banka',
      dataIndex: 'bank_name',
      key: 'bank_name',
      ellipsis: true,
      width: 280,
    },
    {
      title: 'LC (%)',
      dataIndex: 'lc_nonfat',
      key: 'lc',
      sorter: (a: LiquidityCreation, b: LiquidityCreation) => a.lc_nonfat - b.lc_nonfat,
      defaultSortOrder: 'descend' as const,
      render: (v: number) => (v * 100).toFixed(2) + '%',
      width: 120,
    },
    {
      title: 'LC (Tutar)',
      key: 'lc_amount',
      sorter: (a: LiquidityCreation, b: LiquidityCreation) =>
        a.lc_nonfat * a.total_assets - b.lc_nonfat * b.total_assets,
      render: (_: unknown, record: LiquidityCreation) =>
        ((record.lc_nonfat * record.total_assets) / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 0 }) + ' M',
      width: 160,
    },
    {
      title: 'Toplam Aktif',
      dataIndex: 'total_assets',
      key: 'total_assets',
      sorter: (a: LiquidityCreation, b: LiquidityCreation) => a.total_assets - b.total_assets,
      render: (v: number) => (v / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 0 }) + ' M',
      width: 160,
    },
  ];

  return (
    <div>
      <h2>
        Likidite Yaratimi Analizi{' '}
        <Tooltip title="Colak, Deniz, Korkmaz & Yilmaz (2024) — TCMB Working Paper 24/09. Cat Nonfat: bilanco ici kalemlerle likidite yaratimi. LC = (1/2 x (likit olmayan varliklar + likit yukumlulukler) - 1/2 x (likit varliklar + likit olmayan yuk. + ozkaynaklar)) / toplam varliklar">
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
        </Space>
      </Card>

      {/* Summary stats */}
      {year && month && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} md={8}>
            <Card>
              <Statistic
                title="Sektor Ort. LC"
                value={sectorAvg !== null ? (sectorAvg * 100).toFixed(2) : '-'}
                suffix="%"
              />
            </Card>
          </Col>
          <Col xs={12} md={8}>
            <Card>
              <Statistic
                title={
                  <Tooltip title="Sektor toplam likidite yaratimi: tum bankalarin LC tutarlarinin toplami (bin TL)">
                    Toplam LC <InfoCircleOutlined style={{ fontSize: 12, color: '#999' }} />
                  </Tooltip>
                }
                value={sectorTotalLC !== null
                  ? (sectorTotalLC / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 0 })
                  : '-'}
                suffix="M"
              />
            </Card>
          </Col>
          <Col xs={12} md={8}>
            <Card>
              <Statistic
                title="Banka Sayisi"
                value={creation?.length ?? 0}
              />
            </Card>
          </Col>
          <Col xs={12} md={8}>
            <Card>
              <Statistic
                title="En Yuksek LC"
                value={creation && creation.length > 0
                  ? (Math.max(...creation.map(c => c.lc_nonfat)) * 100).toFixed(2)
                  : '-'}
                suffix="%"
              />
            </Card>
          </Col>
          <Col xs={12} md={8}>
            <Card>
              <Statistic
                title="En Dusuk LC"
                value={creation && creation.length > 0
                  ? (Math.min(...creation.map(c => c.lc_nonfat)) * 100).toFixed(2)
                  : '-'}
                suffix="%"
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* 1. LC by Bank Group — time series (Figure 2 from Çolak et al. 2024) */}
      <Card title="Banka Grubuna Gore Likidite Yaratma Trendi" style={{ marginBottom: 16 }}>
        <LineChart
          title=""
          xData={(() => {
            const periods = Array.from(
              new Set((groupTs ?? []).map((p: LiquidityGroupTimeSeries) =>
                `${p.year_id}/${String(p.month_id).padStart(2, '0')}`
              ))
            ).sort();
            return periods;
          })()}
          series={(() => {
            const groups = Array.from(new Set((groupTs ?? []).map((p: LiquidityGroupTimeSeries) => p.group_name))).sort();
            const periods = Array.from(
              new Set((groupTs ?? []).map((p: LiquidityGroupTimeSeries) =>
                `${p.year_id}/${String(p.month_id).padStart(2, '0')}`
              ))
            ).sort();
            const lookup = new Map<string, number>();
            (groupTs ?? []).forEach((p: LiquidityGroupTimeSeries) => {
              lookup.set(`${p.group_name}|${p.year_id}/${String(p.month_id).padStart(2, '0')}`, p.lc_nonfat);
            });
            return groups.map(g => ({
              name: g,
              data: periods.map(pd => {
                const val = lookup.get(`${g}|${pd}`);
                return val !== undefined ? Number((val * 100).toFixed(2)) : null;
              }),
            }));
          })()}
          loading={groupTsLoading}
        />
      </Card>

      {/* Bank Ranking Table */}
      {year && month && (
        <Card title="Banka Bazinda Likidite Yaratma" style={{ marginBottom: 16 }}>
          <Table
            columns={columns}
            dataSource={creation ?? []}
            loading={creationLoading}
            rowKey="bank_name"
            pagination={{ pageSize: 15 }}
            scroll={{ x: 1100 }}
            size="small"
          />
        </Card>
      )}

    </div>
  );
};

export default LiquidityAnalysis;
