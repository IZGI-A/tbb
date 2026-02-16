import React, { useState } from 'react';
import { Table, Card, Space, Select, Button } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import LineChart from '../components/charts/LineChart';
import YearMonthFilter from '../components/filters/YearMonthFilter';
import { useFinancialStatements, useFinancialPeriods, useFinancialTimeSeries, useFinancialBankNames, useFinancialMainStatements, useFinancialChildStatements } from '../hooks/useFinancial';
import type { FinancialRecord, PeriodInfo, TimeSeriesPoint } from '../types';

const FinancialStatements: React.FC = () => {
  const [year, setYear] = useState<number | undefined>();
  const [month, setMonth] = useState<number | undefined>();
  const [accountingSystem, setAccountingSystem] = useState<string | undefined>();
  const [bankName, setBankName] = useState<string | undefined>();
  const [mainStatement, setMainStatement] = useState<string | undefined>();
  const [childStatement, setChildStatement] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const limit = 50;

  const { data: periods } = useFinancialPeriods();
  const { data: statementsData, isLoading } = useFinancialStatements({
    year, month, accounting_system: accountingSystem, bank_name: bankName,
    main_statement: mainStatement, child_statement: childStatement,
    limit, offset: (page - 1) * limit,
  });

  const { data: bankNames } = useFinancialBankNames();
  const { data: mainStatements } = useFinancialMainStatements();
  const { data: childStatements } = useFinancialChildStatements(mainStatement);
  const { data: timeSeries, isLoading: tsLoading } = useFinancialTimeSeries({
    bank_name: bankName,
  });

  const periodList = (periods ?? []) as PeriodInfo[];
  const years: number[] = Array.from(new Set<number>(periodList.map(p => p.year_id))).sort(
    (a, b) => b - a
  );
  const months: number[] = year
    ? Array.from(
        new Set<number>(
          periodList.filter(p => p.year_id === year).map(p => p.month_id)
        )
      ).sort((a, b) => b - a)
    : [];

  const columns = [
    { title: 'Muhasebe Sistemi', dataIndex: 'accounting_system', key: 'accounting_system' },
    { title: 'Ana Kalem', dataIndex: 'main_statement', key: 'main_statement' },
    { title: 'Alt Kalem', dataIndex: 'child_statement', key: 'child_statement' },
    { title: 'Banka', dataIndex: 'bank_name', key: 'bank_name' },
    { title: 'Yil', dataIndex: 'year_id', key: 'year_id', width: 70 },
    { title: 'Ay', dataIndex: 'month_id', key: 'month_id', width: 60 },
    {
      title: 'TP Tutar',
      dataIndex: 'amount_tc',
      key: 'amount_tc',
      render: (v: number | null) => v?.toLocaleString('tr-TR') ?? '-',
    },
    {
      title: 'YP Tutar',
      dataIndex: 'amount_fc',
      key: 'amount_fc',
      render: (v: number | null) => v?.toLocaleString('tr-TR') ?? '-',
    },
    {
      title: 'Toplam',
      dataIndex: 'amount_total',
      key: 'amount_total',
      render: (v: number | null) => v?.toLocaleString('tr-TR') ?? '-',
    },
  ];

  const handleExportCSV = () => {
    const rows = statementsData?.data ?? [];
    if (!rows.length) return;

    const header = columns.map(c => c.title).join(',');
    const body = rows.map((r: FinancialRecord) =>
      columns.map(c => {
        const val = r[c.dataIndex as keyof FinancialRecord];
        return val ?? '';
      }).join(',')
    ).join('\n');

    const blob = new Blob([`${header}\n${body}`], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'financial_statements.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <h2>Mali Tablolar</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <YearMonthFilter
            years={years}
            months={months}
            selectedYear={year}
            selectedMonth={month}
            onYearChange={(y) => { setYear(y); setMonth(undefined); }}
            onMonthChange={setMonth}
          />
          <Select
            placeholder="Muhasebe Sistemi"
            allowClear
            value={accountingSystem}
            onChange={(val: string | undefined) => { setAccountingSystem(val); setPage(1); }}
            style={{ width: 200 }}
            options={[
              { value: 'SOLO', label: 'Solo' },
              { value: 'KONSOLİDE', label: 'Konsolide' },
            ]}
          />
          <Select
            placeholder="Banka secin"
            allowClear
            showSearch
            value={bankName}
            onChange={setBankName}
            style={{ width: 250 }}
            options={(bankNames ?? []).map((b: string) => ({ value: b, label: b }))}
          />
          <Select
            placeholder="Ana Kalem secin"
            allowClear
            showSearch
            value={mainStatement}
            onChange={(val: string | undefined) => {
              setMainStatement(val);
              setChildStatement(undefined);
              setPage(1);
            }}
            style={{ width: 280 }}
            options={(mainStatements ?? []).map((s: string) => ({ value: s, label: s }))}
          />
          <Select
            placeholder="Alt Kalem secin"
            allowClear
            showSearch
            value={childStatement}
            onChange={(val: string | undefined) => {
              setChildStatement(val);
              setPage(1);
            }}
            style={{ width: 320 }}
            options={(childStatements ?? []).map((s: string) => ({ value: s, label: s }))}
          />
          <Button icon={<DownloadOutlined />} onClick={handleExportCSV}>
            CSV Indir
          </Button>
        </Space>
      </Card>

      <Table
        columns={columns}
        dataSource={statementsData?.data ?? []}
        loading={isLoading}
        rowKey={(r: FinancialRecord) =>
          `${r.accounting_system}-${r.child_statement}-${r.bank_name}-${r.year_id}-${r.month_id}`
        }
        pagination={{
          current: page,
          pageSize: limit,
          total: statementsData?.total ?? 0,
          onChange: setPage,
        }}
        scroll={{ x: 1200 }}
        size="small"
        style={{ marginBottom: 24 }}
      />

      {bankName && (
        <Card title={`${bankName} - Zaman Serisi`}>
          <LineChart
            title=""
            xData={(timeSeries ?? []).map(
              (p: TimeSeriesPoint) => `${p.year_id}/${p.month_id}`
            )}
            series={[{
              name: 'Toplam',
              data: (timeSeries ?? []).map(
                (p: TimeSeriesPoint) => p.amount_total
              ),
            }]}
            loading={tsLoading}
          />
        </Card>
      )}
    </div>
  );
};

export default FinancialStatements;
