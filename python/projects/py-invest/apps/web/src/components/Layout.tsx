import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout as AntLayout, Menu, theme } from 'antd';
import {
  StockOutlined,
  FileTextOutlined,
  HistoryOutlined,
  BarChartOutlined,
} from '@ant-design/icons';

const { Header, Content, Footer } = AntLayout;

const Layout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  const menuItems = [
    {
      key: '/',
      icon: <StockOutlined />,
      label: '股票分析',
    },
    {
      key: '/history',
      icon: <HistoryOutlined />,
      label: '历史记录',
    },
  ];

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          background: colorBgContainer,
          padding: '0 24px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            marginRight: '24px',
          }}
        >
          <BarChartOutlined
            style={{
              fontSize: '24px',
              color: '#1890ff',
              marginRight: '12px',
            }}
          />
          <span style={{ fontSize: '18px', fontWeight: 600 }}>Invest-AI</span>
        </div>
        <Menu
          theme="light"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content
        style={{
          padding: '24px',
          background: colorBgContainer,
        }}
      >
        <Outlet />
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        Invest-AI ©{new Date().getFullYear()} - 基于 LLM 的智能股票分析平台
      </Footer>
    </AntLayout>
  );
};

export default Layout;
