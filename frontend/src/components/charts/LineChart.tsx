import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Grid } from 'antd';
import type { EChartsOption } from 'echarts';

interface LineChartProps {
  title: string;
  xData: string[];
  series: {
    name: string;
    data: (number | null)[];
  }[];
  loading?: boolean;
  height?: number;
  yAxisMin?: number;
}

const LineChart: React.FC<LineChartProps> = ({ title, xData, series, loading, height, yAxisMin }) => {
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;
  const chartHeight = height ?? (isMobile ? 280 : 400);

  const option: EChartsOption = {
    title: { text: title, left: 'center', textStyle: { fontSize: isMobile ? 13 : undefined } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: isMobile ? 10 : 12 } },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: xData },
    yAxis: {
      type: 'value',
      min: yAxisMin !== undefined
        ? yAxisMin
        : (value: { min: number }) => Math.floor(value.min - 2),
    },
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
      style={{ height: chartHeight }}
    />
  );
};

export default LineChart;
