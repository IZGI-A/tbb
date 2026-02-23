import React, { useState } from 'react';
import { Card, Select, Space, Table, Row, Col, Statistic, Tooltip, Tag, Descriptions, Spin, Alert } from 'antd';
import { InfoCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import ScatterChart from '../components/charts/ScatterChart';

interface Coefficient {
  variable: string;
  coefficient: number;
  std_error: number;
  t_stat: number;
  p_value: number;
  significant: boolean;
}

interface ModelResult {
  title: string;
  dependent: string;
  method: string;
  equation?: string;
  fixed_effects?: string;
  coefficients?: Coefficient[];
  r_squared?: number;
  adj_r_squared?: number;
  n_obs?: number;
  n_entities?: number;
  n_periods?: number;
  f_stat?: number;
  f_pvalue?: number;
  error?: string;
}

interface DescStat {
  mean: number;
  std: number;
  min: number;
  max: number;
  count: number;
}

interface BankDataPoint {
  bank_name: string;
  capital_adequacy: number;
  lc_nonfat: number;
  z_score: number;
  roa: number;
  bank_size: number;
  state: number;
  bank_group: string;
}

interface PanelResult {
  models: Record<string, ModelResult>;
  descriptive_stats: Record<string, DescStat>;
  panel_info: {
    n_banks: number;
    n_periods: number;
    total_obs: number;
    periods: string[];
  };
  bank_data: BankDataPoint[];
}

const VARIABLE_LABELS: Record<string, string> = {
  capital_adequacy: 'Sermaye Yeterliligi',
  L_capital_adequacy: 'Sermaye Yeterliligi (t-1)',
  bank_size: 'Banka Buyuklugu (ln)',
  L_bank_size: 'Banka Buyuklugu (t-1)',
  roa: 'ROA',
  L_roa: 'ROA (t-1)',
  lc_nonfat: 'LC (Cat Nonfat)',
  L_lc_nonfat: 'LC (t-1)',
  state: 'Kamu Sahipligi',
  z_score: 'Z-Score',
  competition: 'Rekabet (1/HHI)',
  L_competition: 'Rekabet (t-1)',
  Sabit: 'Sabit',
};

const STAT_LABELS: Record<string, string> = {
  lc_nonfat: 'LC (Cat Nonfat)',
  z_score: 'Z-Score',
  capital_adequacy: 'Sermaye Yeterliligi',
  roa: 'ROA',
  bank_size: 'Banka Buyuklugu (ln)',
  state: 'Kamu Sahipligi',
  competition: 'Rekabet (1/HHI)',
};

const PanelRegression: React.FC = () => {
  const [accountingSystem, setAccountingSystem] = useState<string | undefined>();

  const { data, isLoading, error } = useQuery<PanelResult>({
    queryKey: ['panel-regression', accountingSystem],
    queryFn: () => apiClient.get('/panel-regression/results', {
      params: { accounting_system: accountingSystem },
    }).then(r => r.data),
  });

  const coefColumns = [
    {
      title: 'Degisken',
      dataIndex: 'variable',
      key: 'variable',
      render: (v: string) => VARIABLE_LABELS[v] || v,
      width: 200,
    },
    {
      title: 'Katsayi',
      dataIndex: 'coefficient',
      key: 'coefficient',
      render: (v: number) => v.toFixed(4),
      width: 120,
    },
    {
      title: 'Std. Hata',
      dataIndex: 'std_error',
      key: 'std_error',
      render: (v: number) => v.toFixed(4),
      width: 120,
    },
    {
      title: 't-ist.',
      dataIndex: 't_stat',
      key: 't_stat',
      render: (v: number) => v.toFixed(3),
      width: 100,
    },
    {
      title: 'p-deger',
      dataIndex: 'p_value',
      key: 'p_value',
      render: (v: number) => {
        const stars = v < 0.01 ? '***' : v < 0.05 ? '**' : v < 0.10 ? '*' : '';
        return <span>{v.toFixed(4)} {stars && <strong>{stars}</strong>}</span>;
      },
      width: 120,
    },
    {
      title: 'Anlamlilik',
      dataIndex: 'significant',
      key: 'significant',
      render: (v: boolean) => v
        ? <Tag icon={<CheckCircleOutlined />} color="success">p&lt;0.05</Tag>
        : <Tag icon={<CloseCircleOutlined />} color="default">p≥0.05</Tag>,
      width: 120,
    },
  ];

  const descColumns = [
    {
      title: 'Degisken',
      dataIndex: 'variable',
      key: 'variable',
      render: (v: string) => STAT_LABELS[v] || v,
    },
    { title: 'Ort.', dataIndex: 'mean', key: 'mean', render: (v: number) => v.toFixed(4) },
    { title: 'Std. Sapma', dataIndex: 'std', key: 'std', render: (v: number) => v.toFixed(4) },
    { title: 'Min', dataIndex: 'min', key: 'min', render: (v: number) => v.toFixed(4) },
    { title: 'Max', dataIndex: 'max', key: 'max', render: (v: number) => v.toFixed(4) },
    { title: 'N', dataIndex: 'count', key: 'count' },
  ];

  const latestPeriod = data?.panel_info.periods[data.panel_info.periods.length - 1]?.replace('_', '/');

  const renderModel = (key: string, model: ModelResult) => (
    <Card
      key={key}
      title={
        <span>
          {model.title}{' '}
          <Tag color="blue">{model.method}</Tag>
          {model.fixed_effects && (
            <Tag color="purple">FE: {model.fixed_effects}</Tag>
          )}
        </span>
      }
      style={{ marginBottom: 16 }}
    >
      {model.error ? (
        <Alert type="warning" message={model.error} />
      ) : (
        <>
          {model.equation && (
            <div style={{
              background: '#f5f5f5',
              padding: '8px 12px',
              marginBottom: 12,
              borderRadius: 4,
              fontFamily: 'monospace',
              fontSize: 13,
            }}>
              {model.equation}
            </div>
          )}
          <Descriptions size="small" column={{ xs: 1, sm: 2, md: 4 }} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Bagimli Degisken">{model.dependent}</Descriptions.Item>
            <Descriptions.Item label="R²">{model.r_squared?.toFixed(4)}</Descriptions.Item>
            <Descriptions.Item label="Duz. R²">{model.adj_r_squared?.toFixed(4)}</Descriptions.Item>
            <Descriptions.Item label="N">{model.n_obs}</Descriptions.Item>
            {model.n_entities && (
              <Descriptions.Item label="Banka">{model.n_entities}</Descriptions.Item>
            )}
            {model.n_periods && (
              <Descriptions.Item label="Donem">{model.n_periods}</Descriptions.Item>
            )}
            {model.f_stat && (
              <Descriptions.Item label="F-ist.">{model.f_stat?.toFixed(2)} (p={model.f_pvalue?.toFixed(4)})</Descriptions.Item>
            )}
          </Descriptions>
          <Table
            columns={coefColumns}
            dataSource={model.coefficients ?? []}
            rowKey="variable"
            pagination={false}
            scroll={{ x: 800 }}
            size="small"
          />
        </>
      )}
    </Card>
  );

  return (
    <div>
      <h2>
        Panel Regresyon{' '}
        <Tooltip title="Colak, Deniz, Korkmaz & Yilmaz (2024) — TCMB Working Paper 24/09. Sermaye yeterliligi, kamu sahipligi ve likidite yaratiminin banka riski uzerindeki etkisini inceleyen panel veri regresyon modelleri.">
          <InfoCircleOutlined style={{ fontSize: 16, color: '#999' }} />
        </Tooltip>
      </h2>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Select
            placeholder="Muhasebe Sistemi"
            allowClear
            value={accountingSystem}
            onChange={setAccountingSystem}
            style={{ width: 200 }}
            options={[
              { value: 'SOLO', label: 'Solo' },
              { value: 'KONSOLİDE', label: 'Konsolide' },
            ]}
          />
        </Space>
      </Card>

      {isLoading && (
        <Card><Spin tip="Regresyon modelleri calistiriliyor..." size="large"><div style={{ padding: 50 }} /></Spin></Card>
      )}

      {error && (
        <Alert type="error" message="Regresyon sonuclari yuklenemedi" style={{ marginBottom: 16 }} />
      )}

      {data && (
        <>
          {/* Panel Info */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} md={12} lg={6}>
              <Card><Statistic title="Banka Sayisi" value={data.panel_info.n_banks} /></Card>
            </Col>
            <Col xs={12} md={12} lg={6}>
              <Card><Statistic title="Donem Sayisi" value={data.panel_info.n_periods} /></Card>
            </Col>
            <Col xs={12} md={12} lg={6}>
              <Card><Statistic title="Toplam Gozlem" value={data.panel_info.total_obs} /></Card>
            </Col>
            <Col xs={12} md={12} lg={6}>
              <Card><Statistic title="Donemler" value={data.panel_info.periods.map(p => p.replace('_', '/')).join(', ')} /></Card>
            </Col>
          </Row>

          {/* Scatter: Capital Adequacy vs LC */}
          {data.bank_data && data.bank_data.length > 0 && (
            <Card title={`Sermaye Yeterliligi vs LC Orani (${latestPeriod})`} style={{ marginBottom: 16 }}>
              <ScatterChart
                title=""
                xLabel="Sermaye Yeterliligi (%)"
                yLabel="LC (%)"
                showTrendLine
                groups={[
                  {
                    name: 'Kamu',
                    color: '#cf1322',
                    data: data.bank_data.filter(b => b.bank_group === 'Kamu').map(b => ({
                      name: b.bank_name,
                      value: [parseFloat((b.capital_adequacy * 100).toFixed(2)), parseFloat((b.lc_nonfat * 100).toFixed(2))],
                    })),
                  },
                  {
                    name: 'Ozel',
                    color: '#1677ff',
                    data: data.bank_data.filter(b => b.bank_group === 'Ozel').map(b => ({
                      name: b.bank_name,
                      value: [parseFloat((b.capital_adequacy * 100).toFixed(2)), parseFloat((b.lc_nonfat * 100).toFixed(2))],
                    })),
                  },
                  {
                    name: 'Yabanci',
                    color: '#389e0d',
                    data: data.bank_data.filter(b => b.bank_group === 'Yabanci').map(b => ({
                      name: b.bank_name,
                      value: [parseFloat((b.capital_adequacy * 100).toFixed(2)), parseFloat((b.lc_nonfat * 100).toFixed(2))],
                    })),
                  },
                ]}
              />
            </Card>
          )}

          {/* Descriptive Stats */}
          <Card title="Tanimlayici Istatistikler" style={{ marginBottom: 16 }}>
            <Table
              columns={descColumns}
              dataSource={Object.entries(data.descriptive_stats).map(([k, v]) => ({
                variable: k,
                ...v,
              }))}
              rowKey="variable"
              pagination={false}
              scroll={{ x: 600 }}
              size="small"
            />
          </Card>

          {/* Regression Models */}
          {Object.entries(data.models).map(([key, model]) => renderModel(key, model))}
        </>
      )}
    </div>
  );
};

export default PanelRegression;
