import React, { useState } from 'react';
import { Card, Input, Table, Collapse, Descriptions, Tag, Spin } from 'antd';
import { useBanks, useBankSearch, useBankBranches, useBankHistory } from '../hooks/useBanks';
import type { BankInfo, BranchInfo } from '../types';

const { Search } = Input;

const BankDetail: React.FC<{ bankName: string }> = ({ bankName }) => {
  const { data: branches, isLoading: branchLoading } = useBankBranches(bankName);
  const { data: history, isLoading: histLoading } = useBankHistory(bankName);

  const branchColumns = [
    { title: 'Sube Adi', dataIndex: 'branch_name', key: 'branch_name' },
    { title: 'Il', dataIndex: 'city', key: 'city' },
    { title: 'Ilce', dataIndex: 'district', key: 'district' },
    { title: 'Adres', dataIndex: 'address', key: 'address', ellipsis: true },
    { title: 'Telefon', dataIndex: 'phone', key: 'phone' },
  ];

  if (branchLoading || histLoading) return <Spin />;

  return (
    <div>
      {history && (
        <Descriptions bordered size="small" column={1} style={{ marginBottom: 16 }}>
          <Descriptions.Item label="Kurulus Tarihi">
            {history.founding_date ?? '-'}
          </Descriptions.Item>
          <Descriptions.Item label="Tarihce">
            {history.historical_event ?? '-'}
          </Descriptions.Item>
        </Descriptions>
      )}

      <h4>Subeler ({branches?.length ?? 0})</h4>
      <Table
        columns={branchColumns}
        dataSource={branches ?? []}
        rowKey={(r: BranchInfo) => r.branch_name}
        pagination={{ pageSize: 10 }}
        size="small"
        scroll={{ x: 800 }}
      />
    </div>
  );
};

const BankDirectory: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');

  const { data: allBanks, isLoading: allLoading } = useBanks();
  const { data: searchResults, isLoading: searchLoading } = useBankSearch(searchQuery);

  const banks = searchQuery ? searchResults : allBanks;
  const loading = searchQuery ? searchLoading : allLoading;

  const columns = [
    { title: 'Banka Adi', dataIndex: 'bank_name', key: 'bank_name', width: 250 },
    { title: 'Grup', dataIndex: 'bank_group', key: 'bank_group' },
    { title: 'Alt Grup', dataIndex: 'sub_bank_group', key: 'sub_bank_group' },
    {
      title: 'YK Baskani',
      dataIndex: 'board_president',
      key: 'board_president',
      ellipsis: true,
    },
    {
      title: 'Genel Mudur',
      dataIndex: 'general_manager',
      key: 'general_manager',
      ellipsis: true,
    },
    {
      title: 'EFT',
      dataIndex: 'eft',
      key: 'eft',
      width: 80,
      render: (v: string | null) => v ? <Tag>{v}</Tag> : '-',
    },
    {
      title: 'SWIFT',
      dataIndex: 'swift',
      key: 'swift',
      width: 120,
      render: (v: string | null) => v ? <Tag color="blue">{v}</Tag> : '-',
    },
  ];

  return (
    <div>
      <h2>Banka Rehberi</h2>

      <Card style={{ marginBottom: 16 }}>
        <Search
          placeholder="Banka ara..."
          allowClear
          onSearch={setSearchQuery}
          onChange={e => {
            if (!e.target.value) setSearchQuery('');
          }}
          style={{ width: 400 }}
        />
      </Card>

      <Table
        columns={columns}
        dataSource={banks ?? []}
        loading={loading}
        rowKey={(r: BankInfo) => r.bank_name}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1200 }}
        size="small"
        expandable={{
          expandedRowRender: (record: BankInfo) => (
            <BankDetail bankName={record.bank_name} />
          ),
        }}
      />
    </div>
  );
};

export default BankDirectory;
