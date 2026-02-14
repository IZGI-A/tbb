import React from 'react';
import { Card, Col, Row, Statistic, Spin } from 'antd';
import { BankOutlined, DollarOutlined, GlobalOutlined } from '@ant-design/icons';
import LineChart from '../components/charts/LineChart';
import { useFinancialSummary, useFinancialTimeSeries } from '../hooks/useFinancial';
import { useBanks } from '../hooks/useBanks';

const Dashboard: React.FC = () => {
  const { data: banks, isLoading: banksLoading } = useBanks();
  const { data: summary, isLoading: summaryLoading } = useFinancialSummary({});
  const { data: timeSeries, isLoading: tsLoading } = useFinancialTimeSeries({
    bank_name: 'Türkiye Bankacılık Sistemi',
  });

  const totalAssets = summary?.find(
    (s: { metric: string }) => s.metric.toLowerCase().includes('aktif') || s.metric.toLowerCase().includes('varlik')
  );
  const totalDeposits = summary?.find(
    (s: { metric: string }) => s.metric.toLowerCase().includes('mevduat')
  );

  const formatAmount = (val: number | null | undefined) => {
    if (!val) return '0';
    if (val >= 1e12) return `${(val / 1e12).toFixed(1)}T TL`;
    if (val >= 1e9) return `${(val / 1e9).toFixed(1)}B TL`;
    if (val >= 1e6) return `${(val / 1e6).toFixed(1)}M TL`;
    return String(val);
  };

  return (
    <div>
      <h2>Dashboard</h2>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Toplam Banka Sayisi"
              value={banks?.length ?? 0}
              prefix={<BankOutlined />}
              loading={banksLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Toplam Aktifler"
              value={formatAmount(totalAssets?.total)}
              prefix={<DollarOutlined />}
              loading={summaryLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Toplam Mevduat"
              value={formatAmount(totalDeposits?.total)}
              prefix={<GlobalOutlined />}
              loading={summaryLoading}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        {tsLoading ? (
          <Spin />
        ) : (
          <LineChart
            title="Sektor Toplam Trend"
            xData={(timeSeries ?? []).map(
              (p: { year_id: number; month_id: number }) => `${p.year_id}/${p.month_id}`
            )}
            series={[
              {
                name: 'Toplam',
                data: (timeSeries ?? []).map(
                  (p: { amount_total: number | null }) => p.amount_total
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
};

export default Dashboard;
