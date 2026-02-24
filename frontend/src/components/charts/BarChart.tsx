import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Grid } from 'antd';
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
  height?: number;
}

const BarChart: React.FC<BarChartProps> = ({ title, xData, series, loading, horizontal, stacked, height }) => {
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;
  const chartHeight = height ?? (isMobile ? 280 : 400);

  const categoryAxis = { type: 'category' as const, data: xData };
  const valueAxis = { type: 'value' as const };

  const option: EChartsOption = {
    title: { text: title, left: 'center', textStyle: { fontSize: isMobile ? 13 : undefined } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: isMobile ? 10 : 12 } },
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
      style={{ height: chartHeight }}
    />
  );
};

export default BarChart;
