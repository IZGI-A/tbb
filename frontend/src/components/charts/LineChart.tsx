import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface LineChartProps {
  title: string;
  xData: string[];
  series: {
    name: string;
    data: (number | null)[];
  }[];
  loading?: boolean;
}

const LineChart: React.FC<LineChartProps> = ({ title, xData, series, loading }) => {
  const option: EChartsOption = {
    title: { text: title, left: 'center' },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: xData },
    yAxis: { type: 'value' },
    series: series.map(s => ({
      name: s.name,
      type: 'line' as const,
      data: s.data,
      smooth: true,
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

export default LineChart;
