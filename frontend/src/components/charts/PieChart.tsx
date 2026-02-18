import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface PieChartProps {
  title: string;
  data: {
    name: string;
    value: number;
  }[];
  loading?: boolean;
  donut?: boolean;
}

const PieChart: React.FC<PieChartProps> = ({ title, data, loading, donut = false }) => {
  const option: EChartsOption = {
    title: { text: title, left: 'center' },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: donut ? { show: false } : {
      orient: 'vertical',
      left: 'left',
    },
    series: [
      {
        name: title,
        type: 'pie',
        radius: donut ? ['40%', '70%'] : '70%',
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
        },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      showLoading={loading}
      style={{ height: 400 }}
    />
  );
};

export default PieChart;
