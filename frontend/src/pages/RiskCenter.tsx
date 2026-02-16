import React, { useState } from 'react';
import { Card, Col, Row, Select, Space, Table } from 'antd';
import BarChart from '../components/charts/BarChart';
import YearMonthFilter from '../components/filters/YearMonthFilter';
import { useRiskCenterData, useRiskCenterReports, useRiskCenterPeriods, useRiskCenterCategories } from '../hooks/useRiskCenter';
import type { RiskCenterRecord, PeriodInfo } from '../types';

const RiskCenter: React.FC = () => {
  const [reportName, setReportName] = useState<string | undefined>();
  const [category, setCategory] = useState<string | undefined>();
  const [year, setYear] = useState<number | undefined>();
  const [month, setMonth] = useState<number | undefined>();

  const { data: reports } = useRiskCenterReports();
  const { data: periods } = useRiskCenterPeriods();
  const { data: categories } = useRiskCenterCategories(reportName ?? '');
  const { data: riskData, isLoading } = useRiskCenterData({
    report_name: reportName,
    category,
    year,
    month,
  });

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

  const columns = [
    { title: 'Rapor Adi', dataIndex: 'report_name', key: 'report_name' },
    { title: 'Kategori', dataIndex: 'category', key: 'category' },
    {
      title: 'Kisi Sayisi',
      dataIndex: 'person_count',
      key: 'person_count',
      render: (v: number | null) => v?.toLocaleString('tr-TR') ?? '-',
    },
    {
      title: 'Adet',
      dataIndex: 'quantity',
      key: 'quantity',
      render: (v: number | null) => v?.toLocaleString('tr-TR') ?? '-',
    },
    {
      title: 'Tutar',
      dataIndex: 'amount',
      key: 'amount',
      render: (v: number | null) => v?.toLocaleString('tr-TR') ?? '-',
    },
    { title: 'Yil', dataIndex: 'year_id', key: 'year_id', width: 70 },
    { title: 'Ay', dataIndex: 'month_id', key: 'month_id', width: 60 },
  ];

  // Detect which numeric fields have data
  const records = (riskData ?? []) as RiskCenterRecord[];
  const hasAmount = records.some(r => r.amount != null && r.amount !== 0);
  const hasPersonCount = records.some(r => r.person_count != null && r.person_count !== 0);
  const hasQuantity = records.some(r => r.quantity != null && r.quantity !== 0);

  // Group data by category for the chart
  const grouped: Record<string, { amount: number; person_count: number; quantity: number }> = {};
  for (const r of records) {
    if (!grouped[r.category]) {
      grouped[r.category] = { amount: 0, person_count: 0, quantity: 0 };
    }
    grouped[r.category].amount += r.amount ?? 0;
    grouped[r.category].person_count += r.person_count ?? 0;
    grouped[r.category].quantity += r.quantity ?? 0;
  }

  const chartCategories = Object.keys(grouped);

  // Build separate charts for each metric to avoid scale mismatch
  const charts: { title: string; data: number[] }[] = [];
  if (hasAmount) {
    charts.push({ title: 'Tutar Dagilimi', data: chartCategories.map(c => grouped[c].amount) });
  }
  if (hasPersonCount) {
    charts.push({ title: 'Kisi Sayisi Dagilimi', data: chartCategories.map(c => grouped[c].person_count) });
  }
  if (hasQuantity) {
    charts.push({ title: 'Adet Dagilimi', data: chartCategories.map(c => grouped[c].quantity) });
  }

  return (
    <div>
      <h2>Risk Merkezi</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="Rapor secin"
            allowClear
            showSearch
            value={reportName}
            onChange={(val: string | undefined) => {
              setReportName(val);
              setCategory(undefined);
            }}
            style={{ width: 300 }}
            options={(reports ?? []).map((r: string) => ({ value: r, label: r }))}
          />
          <Select
            placeholder="Kategori secin"
            allowClear
            showSearch
            value={category}
            onChange={setCategory}
            style={{ width: 300 }}
            options={(categories ?? []).map((c: string) => ({ value: c, label: c }))}
            disabled={!reportName}
          />
          <YearMonthFilter
            years={years}
            months={months}
            selectedYear={year}
            selectedMonth={month}
            onYearChange={(y) => { setYear(y); setMonth(undefined); }}
            onMonthChange={setMonth}
          />
        </Space>
      </Card>

      {chartCategories.length > 0 && charts.length > 0 && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          {charts.map((chart) => (
            <Col xs={24} md={charts.length === 1 ? 24 : 12} key={chart.title}>
              <Card>
                <BarChart
                  title={chart.title}
                  xData={chartCategories}
                  series={[{ name: chart.title, data: chart.data }]}
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Table
        columns={columns}
        dataSource={riskData ?? []}
        loading={isLoading}
        rowKey={(r: RiskCenterRecord) =>
          `${r.report_name}-${r.category}-${r.year_id}-${r.month_id}`
        }
        pagination={{ pageSize: 50 }}
        scroll={{ x: 1000 }}
        size="small"
      />
    </div>
  );
};

export default RiskCenter;
