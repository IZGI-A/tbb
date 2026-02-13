import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import trTR from 'antd/locale/tr_TR';

import AppLayout from './components/layout/AppLayout';
import Dashboard from './pages/Dashboard';
import FinancialStatements from './pages/FinancialStatements';
import RegionalStats from './pages/RegionalStats';
import RiskCenter from './pages/RiskCenter';
import BankDirectory from './pages/BankDirectory';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 2,
    },
  },
});

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={trTR}>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/financial" element={<FinancialStatements />} />
              <Route path="/regions" element={<RegionalStats />} />
              <Route path="/risk-center" element={<RiskCenter />} />
              <Route path="/banks" element={<BankDirectory />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  );
};

export default App;
