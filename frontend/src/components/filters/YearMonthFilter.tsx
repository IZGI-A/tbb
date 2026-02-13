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
  selectedYear,
  selectedMonth,
  onYearChange,
  onMonthChange,
  showMonth = true,
}) => {
  return (
    <Space>
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
          options={Array.from({ length: 12 }, (_, i) => ({
            value: i + 1,
            label: monthNames[i],
          }))}
        />
      )}
    </Space>
  );
};

export default YearMonthFilter;
