import React, { useState } from 'react';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  BarChartOutlined,
  GlobalOutlined,
  AlertOutlined,
  BankOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/financial', icon: <BarChartOutlined />, label: 'Mali Tablolar' },
  { key: '/regions', icon: <GlobalOutlined />, label: 'Bolgesel Istatistikler' },
  { key: '/risk-center', icon: <AlertOutlined />, label: 'Risk Merkezi' },
  { key: '/banks', icon: <BankOutlined />, label: 'Banka Rehberi' },
];

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: collapsed ? 16 : 20,
          fontWeight: 'bold',
        }}>
          {collapsed ? 'TBB' : 'TBB Data Platform'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{
          padding: '0 24px',
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          fontSize: 18,
          fontWeight: 500,
          borderBottom: '1px solid #f0f0f0',
        }}>
          Turkiye Bankalar Birligi - Veri Platformu
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
