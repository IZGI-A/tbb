import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Grid } from 'antd';
import type { EChartsOption } from 'echarts';

interface PieChartProps {
  title: string;
  data: {
    name: string;
    value: number;
  }[];
  loading?: boolean;
  donut?: boolean;
  height?: number;
}

const PieChart: React.FC<PieChartProps> = ({ title, data, loading, donut = false, height }) => {
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;
  const chartHeight = height ?? (isMobile ? 280 : 400);

  const option: EChartsOption = {
    title: { text: title, left: 'center', textStyle: { fontSize: isMobile ? 13 : undefined } },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: donut ? { show: false } : (isMobile
      ? { orient: 'horizontal', bottom: 0, textStyle: { fontSize: 10 } }
      : { orient: 'vertical', left: 'left' }
    ),
    series: [
      {
        name: title,
        type: 'pie',
        radius: donut
          ? (isMobile ? ['30%', '55%'] : ['40%', '70%'])
          : (isMobile ? '55%' : '70%'),
        data: data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
        label: {
          show: true,
          formatter: '{b}: {d}%',
          fontSize: isMobile ? 10 : 12,
        },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      showLoading={loading}
      style={{ height: chartHeight }}
    />
  );
};

export default PieChart;
