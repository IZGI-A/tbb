import React, { useState } from 'react';
import { Card, Select, Space, Table } from 'antd';
import BarChart from '../components/charts/BarChart';
import YearMonthFilter from '../components/filters/YearMonthFilter';
import { useRiskCenterData, useRiskCenterReports } from '../hooks/useRiskCenter';
import type { RiskCenterRecord } from '../types';

const RiskCenter: React.FC = () => {
  const [reportName, setReportName] = useState<string | undefined>();
  const [year, setYear] = useState<number | undefined>();
  const [month, setMonth] = useState<number | undefined>();

  const { data: reports } = useRiskCenterReports();
  const { data: riskData, isLoading } = useRiskCenterData({
    report_name: reportName,
    year,
    month,
  });

  const years = Array.from({ length: 10 }, (_, i) => 2024 - i);

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
            onChange={setReportName}
            style={{ width: 300 }}
            options={(reports ?? []).map((r: string) => ({ value: r, label: r }))}
          />
          <YearMonthFilter
            years={years}
            selectedYear={year}
            selectedMonth={month}
            onYearChange={setYear}
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
