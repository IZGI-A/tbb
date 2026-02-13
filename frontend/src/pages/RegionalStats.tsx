import React, { useState } from 'react';
import { Card, Select, Space, Table } from 'antd';
import BarChart from '../components/charts/BarChart';
import { useRegionList, useRegionMetrics, useRegionComparison, useRegionStats } from '../hooks/useRegions';
import type { RegionStat, RegionComparison as RegionComparisonType } from '../types';

const RegionalStats: React.FC = () => {
  const [selectedMetric, setSelectedMetric] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<number>(2024);
  const [selectedRegion, setSelectedRegion] = useState<string | undefined>();

  const { data: regions } = useRegionList();
  const { data: metrics } = useRegionMetrics();
  const { data: comparison, isLoading: compLoading } = useRegionComparison(
    selectedMetric, selectedYear
  );
  const { data: stats, isLoading: statsLoading } = useRegionStats({
    region: selectedRegion,
    metric: selectedMetric || undefined,
    year: selectedYear || undefined,
  });

  const columns = [
    { title: 'Bolge', dataIndex: 'region', key: 'region' },
    { title: 'Metrik', dataIndex: 'metric', key: 'metric' },
    { title: 'Yil', dataIndex: 'year_id', key: 'year_id' },
    {
      title: 'Deger',
      dataIndex: 'value',
      key: 'value',
      render: (v: number | null) => v?.toLocaleString('tr-TR') ?? '-',
    },
  ];

  return (
    <div>
      <h2>Bolgesel Istatistikler</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="Metrik secin"
            showSearch
            value={selectedMetric || undefined}
            onChange={setSelectedMetric}
            style={{ width: 300 }}
            options={(metrics ?? []).map((m: string) => ({ value: m, label: m }))}
          />
          <Select
            placeholder="Yil secin"
            value={selectedYear}
            onChange={setSelectedYear}
            style={{ width: 120 }}
            options={Array.from({ length: 10 }, (_, i) => ({
              value: 2024 - i,
              label: String(2024 - i),
            }))}
          />
          <Select
            placeholder="Bolge secin"
            allowClear
            showSearch
            value={selectedRegion}
            onChange={setSelectedRegion}
            style={{ width: 250 }}
            options={(regions ?? []).map((r: string) => ({ value: r, label: r }))}
          />
        </Space>
      </Card>

      {selectedMetric && (
        <Card style={{ marginBottom: 16 }}>
          <BarChart
            title={`${selectedMetric} - Bolge Karsilastirmasi (${selectedYear})`}
            xData={(comparison ?? []).map((c: RegionComparisonType) => c.region)}
            series={[{
              name: selectedMetric,
              data: (comparison ?? []).map((c: RegionComparisonType) => c.value),
            }]}
            loading={compLoading}
            horizontal
          />
        </Card>
      )}

      <Table
        columns={columns}
        dataSource={stats ?? []}
        loading={statsLoading}
        rowKey={(r: RegionStat) => `${r.region}-${r.metric}-${r.year_id}`}
        pagination={{ pageSize: 50 }}
        scroll={{ x: 800 }}
        size="small"
      />
    </div>
  );
};

export default RegionalStats;
