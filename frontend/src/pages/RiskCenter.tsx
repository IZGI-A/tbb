import React, { useState } from 'react';
import { Card, Select, Space, Table } from 'antd';
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

  // Group data by category for the chart
  const chartData = (riskData ?? []).reduce((acc: Record<string, number>, r: RiskCenterRecord) => {
    if (r.amount) {
      acc[r.category] = (acc[r.category] ?? 0) + r.amount;
    }
    return acc;
  }, {} as Record<string, number>);

  const chartCategories = Object.keys(chartData);
  const chartValues = chartCategories.map(c => chartData[c]);

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

      {chartCategories.length > 0 && (
        <Card style={{ marginBottom: 16 }}>
          <BarChart
            title="Kategorilere Gore Tutar Dagilimi"
            xData={chartCategories}
            series={[{ name: 'Tutar', data: chartValues }]}
          />
        </Card>
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
