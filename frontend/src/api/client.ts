import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Financial
export const financialApi = {
  getStatements: (params: Record<string, unknown>) =>
    apiClient.get('/financial/statements', { params }),
  getSummary: (params: Record<string, unknown>) =>
    apiClient.get('/financial/summary', { params }),
  getPeriods: () =>
    apiClient.get('/financial/periods'),
  getTimeSeries: (params: Record<string, unknown>) =>
    apiClient.get('/financial/time-series', { params }),
  getBankNames: () =>
    apiClient.get('/financial/bank-names'),
  getMainStatements: () =>
    apiClient.get('/financial/main-statements'),
  getChildStatements: (params: Record<string, unknown>) =>
    apiClient.get('/financial/child-statements', { params }),
  getRatioTypes: () =>
    apiClient.get('/financial/ratio-types'),
  getRatios: (params: { year: number; month: number }) =>
    apiClient.get('/financial/ratios', { params }),
};

// Regions
export const regionsApi = {
  getStats: (params: Record<string, unknown>) =>
    apiClient.get('/regions/stats', { params }),
  getList: () =>
    apiClient.get('/regions/list'),
  getMetrics: () =>
    apiClient.get('/regions/metrics'),
  getPeriods: () =>
    apiClient.get('/regions/periods'),
  getComparison: (params: { metric: string; year: number }) =>
    apiClient.get('/regions/comparison', { params }),
  getLoanDepositRatio: (year: number) =>
    apiClient.get('/regions/loan-deposit-ratio', { params: { year } }),
  getCreditHhi: (year: number) =>
    apiClient.get('/regions/credit-hhi', { params: { year } }),
};

// Risk Center
export const riskCenterApi = {
  getData: (params: Record<string, unknown>) =>
    apiClient.get('/risk-center/data', { params }),
  getReports: () =>
    apiClient.get('/risk-center/reports'),
  getPeriods: () =>
    apiClient.get('/risk-center/periods'),
  getCategories: (reportName: string) =>
    apiClient.get('/risk-center/categories', { params: { report_name: reportName } }),
};

// Banks
export const banksApi = {
  getAll: () =>
    apiClient.get('/banks/'),
  search: (q: string) =>
    apiClient.get('/banks/search', { params: { q } }),
  getDashboardStats: () =>
    apiClient.get('/banks/dashboard-stats'),
  getBranches: (bankName: string, city?: string) =>
    apiClient.get(`/banks/${encodeURIComponent(bankName)}/branches`, { params: { city } }),
  getAtms: (bankName: string, city?: string) =>
    apiClient.get(`/banks/${encodeURIComponent(bankName)}/atms`, { params: { city } }),
  getHistory: (bankName: string) =>
    apiClient.get(`/banks/${encodeURIComponent(bankName)}/history`),
};

export default apiClient;
