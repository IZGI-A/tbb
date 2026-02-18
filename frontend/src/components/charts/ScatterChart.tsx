import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface ScatterPoint {
  name: string;
  value: [number, number];
}

interface ScatterChartProps {
  title: string;
  xLabel: string;
  yLabel: string;
  data: ScatterPoint[];
  loading?: boolean;
}

const ScatterChart: React.FC<ScatterChartProps> = ({ title, xLabel, yLabel, data, loading }) => {
  const option: EChartsOption = {
    title: { text: title, left: 'center' },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const d = params.data;
        return `<strong>${d.name}</strong><br/>${xLabel}: ${d.value[0]}<br/>${yLabel}: ${d.value[1]}`;
      },
    },
    grid: { left: '8%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: {
      type: 'value',
      name: xLabel,
      nameLocation: 'middle',
      nameGap: 30,
    },
    yAxis: {
      type: 'value',
      name: yLabel,
      nameLocation: 'middle',
      nameGap: 50,
    },
    series: [
      {
        type: 'scatter',
        symbolSize: 12,
        data: data.map(d => ({ name: d.name, value: d.value })),
        label: { show: false },
        emphasis: {
          label: { show: false },
        },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      showLoading={loading}
      style={{ height: 450 }}
    />
  );
};

export default ScatterChart;
