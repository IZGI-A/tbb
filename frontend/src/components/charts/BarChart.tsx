import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface BarChartProps {
  title: string;
  xData: string[];
  series: {
    name: string;
    data: (number | null)[];
  }[];
  loading?: boolean;
  horizontal?: boolean;
  stacked?: boolean;
}

const BarChart: React.FC<BarChartProps> = ({ title, xData, series, loading, horizontal, stacked }) => {
  const categoryAxis = { type: 'category' as const, data: xData };
  const valueAxis = { type: 'value' as const };

  const option: EChartsOption = {
    title: { text: title, left: 'center' },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: horizontal ? valueAxis : categoryAxis,
    yAxis: horizontal ? categoryAxis : valueAxis,
    series: series.map(s => ({
      name: s.name,
      type: 'bar' as const,
      data: s.data,
      ...(stacked ? { stack: 'total' } : {}),
    })),
  };

  return (
    <ReactECharts
      option={option}
      showLoading={loading}
      style={{ height: 400 }}
    />
  );
};

export default BarChart;
