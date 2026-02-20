import React from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface ScatterPoint {
  name: string;
  value: [number, number];
}

interface ScatterGroup {
  name: string;
  color: string;
  data: ScatterPoint[];
}

interface ScatterChartProps {
  title: string;
  xLabel: string;
  yLabel: string;
  data?: ScatterPoint[];
  groups?: ScatterGroup[];
  showTrendLine?: boolean;
  loading?: boolean;
}

const GROUP_SYMBOLS = ['circle', 'diamond', 'triangle'] as const;

function computeTrendLine(points: [number, number][]): { slope: number; intercept: number; minX: number; maxX: number } | null {
  if (points.length < 2) return null;
  const n = points.length;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  let minX = Infinity, maxX = -Infinity;
  for (const [x, y] of points) {
    sumX += x; sumY += y; sumXY += x * y; sumX2 += x * x;
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
  }
  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return null;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept, minX, maxX };
}

const ScatterChart: React.FC<ScatterChartProps> = ({ title, xLabel, yLabel, data, groups, showTrendLine, loading }) => {
  const allPoints: [number, number][] = [];

  const series: any[] = groups
    ? groups.map((g, i) => {
        g.data.forEach(d => allPoints.push(d.value));
        return {
          type: 'scatter',
          name: g.name,
          symbol: GROUP_SYMBOLS[i % GROUP_SYMBOLS.length],
          symbolSize: 14,
          itemStyle: {
            color: g.color,
            borderColor: '#fff',
            borderWidth: 1.5,
            shadowBlur: 4,
            shadowColor: 'rgba(0,0,0,0.15)',
          },
          data: g.data.map(d => ({ name: d.name, value: d.value })),
          emphasis: {
            scale: 1.6,
            itemStyle: {
              borderColor: g.color,
              borderWidth: 2,
              shadowBlur: 10,
              shadowColor: 'rgba(0,0,0,0.3)',
            },
            label: {
              show: true,
              formatter: (p: any) => p.data.name.replace(/ A\.Ş\.$/, '').replace(/ T\.A\.O\.$/, ''),
              position: 'top',
              fontSize: 11,
              fontWeight: 600,
              color: '#333',
              backgroundColor: 'rgba(255,255,255,0.85)',
              borderColor: '#ddd',
              borderWidth: 1,
              borderRadius: 3,
              padding: [3, 6],
            },
          },
        };
      })
    : (() => {
        (data ?? []).forEach(d => allPoints.push(d.value));
        return [{
          type: 'scatter',
          symbolSize: 14,
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 1.5,
            shadowBlur: 4,
            shadowColor: 'rgba(0,0,0,0.15)',
          },
          data: (data ?? []).map(d => ({ name: d.name, value: d.value })),
          emphasis: {
            scale: 1.6,
            label: {
              show: true,
              formatter: (p: any) => p.data.name,
              position: 'top',
              fontSize: 11,
              fontWeight: 600,
            },
          },
        }];
      })();

  if (showTrendLine && allPoints.length >= 2) {
    const trend = computeTrendLine(allPoints);
    if (trend) {
      const pad = (trend.maxX - trend.minX) * 0.05;
      const x1 = trend.minX - pad;
      const x2 = trend.maxX + pad;
      series.push({
        type: 'line',
        name: 'Trend',
        showSymbol: false,
        lineStyle: { color: '#999', width: 1.5, type: 'dashed' },
        data: [
          [x1, trend.slope * x1 + trend.intercept],
          [x2, trend.slope * x2 + trend.intercept],
        ],
        tooltip: { show: false },
        z: 0,
      });
    }
  }

  const option: EChartsOption = {
    title: title ? { text: title, left: 'center', textStyle: { fontSize: 15, fontWeight: 600 } } : undefined,
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: '#e8e8e8',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { fontSize: 13, color: '#333' },
      formatter: (params: any) => {
        if (params.seriesType === 'line') return '';
        const d = params.data;
        const marker = params.marker || '';
        return `${marker} <strong>${d.name}</strong><br/>`
          + `${xLabel}: <b>${d.value[0]}%</b><br/>`
          + `${yLabel}: <b>${d.value[1]}%</b>`;
      },
    },
    legend: groups ? {
      bottom: 4,
      itemWidth: 14,
      itemHeight: 14,
      textStyle: { fontSize: 13 },
      itemGap: 24,
    } : undefined,
    grid: {
      left: '6%',
      right: '5%',
      top: title ? '12%' : '6%',
      bottom: groups ? '16%' : '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      name: xLabel,
      nameLocation: 'middle',
      nameGap: 32,
      nameTextStyle: { fontSize: 13, fontWeight: 600, color: '#555' },
      axisLabel: { formatter: '{value}%', fontSize: 11, color: '#666' },
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLine: { lineStyle: { color: '#d9d9d9' } },
    },
    yAxis: {
      type: 'value',
      name: yLabel,
      nameLocation: 'middle',
      nameGap: 55,
      nameTextStyle: { fontSize: 13, fontWeight: 600, color: '#555' },
      axisLabel: { formatter: '{value}%', fontSize: 11, color: '#666' },
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLine: { lineStyle: { color: '#d9d9d9' } },
    },
    animationDuration: 600,
    animationEasing: 'cubicOut',
    series,
  };

  return (
    <ReactECharts
      option={option}
      showLoading={loading}
      style={{ height: 480 }}
    />
  );
};

export default ScatterChart;
