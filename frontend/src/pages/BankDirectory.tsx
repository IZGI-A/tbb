import React, { useState, useMemo } from 'react';
import { Card, Input, Select, Space, Table, Collapse, Descriptions, Tag, Spin } from 'antd';
import { useBanks, useBankSearch, useBankBranches, useBankAtms, useBankHistory } from '../hooks/useBanks';
import type { BankInfo, BranchInfo, ATMInfo } from '../types';

const { Search } = Input;

const BankDetail: React.FC<{ bankName: string }> = ({ bankName }) => {
  const { data: branches, isLoading: branchLoading } = useBankBranches(bankName);
  const { data: atms, isLoading: atmLoading } = useBankAtms(bankName);
  const { data: history, isLoading: histLoading } = useBankHistory(bankName);

  // Branch filters
  const [branchCity, setBranchCity] = useState<string | undefined>();
  const [branchDistrict, setBranchDistrict] = useState<string | undefined>();

  // ATM filters
  const [atmCity, setAtmCity] = useState<string | undefined>();
  const [atmDistrict, setAtmDistrict] = useState<string | undefined>();

  const branchCities = useMemo(() => {
    if (!branches) return [];
    return Array.from(new Set(branches.map((b: BranchInfo) => b.city).filter(Boolean))).sort() as string[];
  }, [branches]);

  const branchDistricts = useMemo(() => {
    if (!branches) return [];
    const filtered = branchCity
      ? branches.filter((b: BranchInfo) => b.city === branchCity)
      : branches;
    return Array.from(new Set(filtered.map((b: BranchInfo) => b.district).filter(Boolean))).sort() as string[];
  }, [branches, branchCity]);

  const filteredBranches = useMemo(() => {
    if (!branches) return [];
    return branches.filter((b: BranchInfo) => {
      if (branchCity && b.city !== branchCity) return false;
      if (branchDistrict && b.district !== branchDistrict) return false;
      return true;
    });
  }, [branches, branchCity, branchDistrict]);

  const atmCities = useMemo(() => {
    if (!atms) return [];
    return Array.from(new Set(atms.map((a: ATMInfo) => a.city).filter(Boolean))).sort() as string[];
  }, [atms]);

  const atmDistricts = useMemo(() => {
    if (!atms) return [];
    const filtered = atmCity
      ? atms.filter((a: ATMInfo) => a.city === atmCity)
      : atms;
    return Array.from(new Set(filtered.map((a: ATMInfo) => a.district).filter(Boolean))).sort() as string[];
  }, [atms, atmCity]);

  const filteredAtms = useMemo(() => {
    if (!atms) return [];
    return atms.filter((a: ATMInfo) => {
      if (atmCity && a.city !== atmCity) return false;
      if (atmDistrict && a.district !== atmDistrict) return false;
      return true;
    });
  }, [atms, atmCity, atmDistrict]);

  const branchColumns = [
    { title: 'Sube Adi', dataIndex: 'branch_name', key: 'branch_name' },
    { title: 'Il', dataIndex: 'city', key: 'city' },
    { title: 'Ilce', dataIndex: 'district', key: 'district' },
    { title: 'Adres', dataIndex: 'address', key: 'address', ellipsis: true },
    { title: 'Telefon', dataIndex: 'phone', key: 'phone' },
  ];

  const atmColumns = [
    { title: 'ATM Adi', dataIndex: 'branch_name', key: 'branch_name' },
    { title: 'Il', dataIndex: 'city', key: 'city' },
    { title: 'Ilce', dataIndex: 'district', key: 'district' },
    { title: 'Adres', dataIndex: 'address', key: 'address', ellipsis: true },
  ];

  if (branchLoading || atmLoading || histLoading) return <Spin />;

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

      <Space wrap style={{ marginBottom: 8 }}>
        <h4 style={{ margin: 0 }}>Subeler ({filteredBranches.length})</h4>
        <Select
          placeholder="Il secin"
          allowClear
          showSearch
          value={branchCity}
          onChange={(val: string | undefined) => {
            setBranchCity(val);
            setBranchDistrict(undefined);
          }}
          style={{ width: 200 }}
          options={branchCities.map(c => ({ value: c, label: c }))}
        />
        <Select
          placeholder="Ilce secin"
          allowClear
          showSearch
          value={branchDistrict}
          onChange={setBranchDistrict}
          style={{ width: 200 }}
          options={branchDistricts.map(d => ({ value: d, label: d }))}
        />
      </Space>
      <Table
        columns={branchColumns}
        dataSource={filteredBranches}
        rowKey={(r: BranchInfo) => r.branch_name}
        pagination={{ pageSize: 10 }}
        size="small"
        scroll={{ x: 800 }}
        style={{ marginBottom: 24 }}
      />

      <Space wrap style={{ marginBottom: 8 }}>
        <h4 style={{ margin: 0 }}>ATM ({filteredAtms.length})</h4>
        <Select
          placeholder="Il secin"
          allowClear
          showSearch
          value={atmCity}
          onChange={(val: string | undefined) => {
            setAtmCity(val);
            setAtmDistrict(undefined);
          }}
          style={{ width: 200 }}
          options={atmCities.map(c => ({ value: c, label: c }))}
        />
        <Select
          placeholder="Ilce secin"
          allowClear
          showSearch
          value={atmDistrict}
          onChange={setAtmDistrict}
          style={{ width: 200 }}
          options={atmDistricts.map(d => ({ value: d, label: d }))}
        />
      </Space>
      <Table
        columns={atmColumns}
        dataSource={filteredAtms}
        rowKey={(r: ATMInfo) => `${r.branch_name}-${r.address}`}
        pagination={{ pageSize: 10 }}
        size="small"
        scroll={{ x: 800 }}
      />
    </div>
  );
};

const BankDirectory: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGroup, setSelectedGroup] = useState<string | undefined>();
  const [selectedSubGroup, setSelectedSubGroup] = useState<string | undefined>();

  const { data: allBanks, isLoading: allLoading } = useBanks();
  const { data: searchResults, isLoading: searchLoading } = useBankSearch(searchQuery);

  const baseBanks = searchQuery ? searchResults : allBanks;
  const loading = searchQuery ? searchLoading : allLoading;

  // Derive unique groups from loaded data
  const groups = useMemo(() => {
    if (!allBanks) return [];
    return Array.from(new Set(allBanks.map((b: BankInfo) => b.bank_group).filter(Boolean))).sort() as string[];
  }, [allBanks]);

  // Derive sub-groups filtered by selected group
  const subGroups = useMemo(() => {
    if (!allBanks) return [];
    const filtered = selectedGroup
      ? allBanks.filter((b: BankInfo) => b.bank_group === selectedGroup)
      : allBanks;
    return Array.from(new Set(filtered.map((b: BankInfo) => b.sub_bank_group).filter(Boolean))).sort() as string[];
  }, [allBanks, selectedGroup]);

  // Apply group/sub-group filters
  const banks = useMemo(() => {
    if (!baseBanks) return [];
    return baseBanks.filter((b: BankInfo) => {
      if (selectedGroup && b.bank_group !== selectedGroup) return false;
      if (selectedSubGroup && b.sub_bank_group !== selectedSubGroup) return false;
      return true;
    });
  }, [baseBanks, selectedGroup, selectedSubGroup]);

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
        <Space wrap>
          <Search
            placeholder="Banka ara..."
            allowClear
            onSearch={setSearchQuery}
            onChange={e => {
              if (!e.target.value) setSearchQuery('');
            }}
            style={{ width: 300 }}
          />
          <Select
            placeholder="Grup secin"
            allowClear
            value={selectedGroup}
            onChange={(val: string | undefined) => {
              setSelectedGroup(val);
              setSelectedSubGroup(undefined);
            }}
            style={{ width: 280 }}
            options={groups.map(g => ({ value: g, label: g }))}
          />
          <Select
            placeholder="Alt grup secin"
            allowClear
            value={selectedSubGroup}
            onChange={setSelectedSubGroup}
            style={{ width: 350 }}
            options={subGroups.map(sg => ({ value: sg, label: sg }))}
          />
        </Space>
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
