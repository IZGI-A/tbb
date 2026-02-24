import React from 'react';
import { Select, Space } from 'antd';

interface YearMonthFilterProps {
  years: number[];
  months?: number[];
  selectedYear: number | undefined;
  selectedMonth?: number | undefined;
  onYearChange: (year: number | undefined) => void;
  onMonthChange?: (month: number | undefined) => void;
  showMonth?: boolean;
}

const monthNames = [
  'Ocak', 'Subat', 'Mart', 'Nisan', 'Mayis', 'Haziran',
  'Temmuz', 'Agustos', 'Eylul', 'Ekim', 'Kasim', 'Aralik'
];

const YearMonthFilter: React.FC<YearMonthFilterProps> = ({
  years,
  months,
  selectedYear,
  selectedMonth,
  onYearChange,
  onMonthChange,
  showMonth = true,
}) => {
  const monthOptions = months && months.length > 0
    ? months.map(m => ({ value: m, label: monthNames[m - 1] }))
    : Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: monthNames[i] }));

  return (
    <Space wrap>
      <Select
        placeholder="Yil secin"
        allowClear
        value={selectedYear}
        onChange={onYearChange}
        style={{ width: 120 }}
        options={years.map(y => ({ value: y, label: String(y) }))}
      />
      {showMonth && onMonthChange && (
        <Select
          placeholder="Ay secin"
          allowClear
          value={selectedMonth}
          onChange={onMonthChange}
          style={{ width: 140 }}
          options={monthOptions}
        />
      )}
    </Space>
  );
};

export default YearMonthFilter;
