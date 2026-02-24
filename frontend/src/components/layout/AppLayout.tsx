import React, { useState } from 'react';
import { Layout, Menu, Grid, Drawer, Button } from 'antd';
import {
  DashboardOutlined,
  BarChartOutlined,
  GlobalOutlined,
  AlertOutlined,
  BankOutlined,
  ExperimentOutlined,
  SwapOutlined,
  SafetyOutlined,
  FundOutlined,
  EnvironmentOutlined,
  MenuOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/financial', icon: <BarChartOutlined />, label: 'Mali Tablolar' },
  { key: '/regions', icon: <GlobalOutlined />, label: 'Bolgesel Istatistikler' },
  { key: '/risk-center', icon: <AlertOutlined />, label: 'Risk Merkezi' },
  { key: '/banks', icon: <BankOutlined />, label: 'Banka Rehberi' },
  {
    type: 'group' as const,
    label: 'Likidite Analizleri',
    children: [
      { key: '/liquidity', icon: <ExperimentOutlined />, label: 'Likidite Analizi' },
      { key: '/regional-liquidity', icon: <EnvironmentOutlined />, label: 'Bolgesel Likidite' },
      { key: '/comparison', icon: <SwapOutlined />, label: 'Banka Karsilastirmasi' },
      { key: '/risk', icon: <SafetyOutlined />, label: 'Risk Analizi' },
      { key: '/panel-regression', icon: <FundOutlined />, label: 'Panel Regresyon' },
    ],
  },
];

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
    if (isMobile) setDrawerVisible(false);
  };

  const menuContent = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[location.pathname]}
      items={menuItems}
      onClick={handleMenuClick}
    />
  );

  const logo = (show: boolean) => (
    <div style={{
      height: 64,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#fff',
      fontSize: show ? 20 : 16,
      fontWeight: 'bold',
    }}>
      {show ? 'TBB Data Platform' : 'TBB'}
    </div>
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* Desktop Sidebar */}
      {!isMobile && (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          theme="dark"
        >
          {logo(!collapsed)}
          {menuContent}
        </Sider>
      )}

      {/* Mobile Drawer */}
      {isMobile && (
        <Drawer
          placement="left"
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          width={256}
          styles={{ body: { padding: 0, background: '#001529' } }}
          closable={false}
        >
          {logo(true)}
          {menuContent}
        </Drawer>
      )}

      <Layout>
        <Header style={{
          padding: isMobile ? '0 12px' : '0 24px',
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          fontSize: isMobile ? 14 : 18,
          fontWeight: 500,
          borderBottom: '1px solid #f0f0f0',
          gap: 12,
        }}>
          {isMobile && (
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerVisible(true)}
              style={{ fontSize: 18 }}
            />
          )}
          <span style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {isMobile ? 'TBB Veri Platformu' : 'Turkiye Bankalar Birligi - Veri Platformu'}
          </span>
        </Header>
        <Content style={{
          margin: isMobile ? 8 : 24,
          padding: isMobile ? 12 : 24,
          background: '#fff',
          borderRadius: 8,
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
