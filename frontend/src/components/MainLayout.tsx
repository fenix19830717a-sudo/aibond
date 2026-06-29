import React, { useState } from 'react';
import { Layout, Menu, Avatar, Dropdown, Typography, theme } from 'antd';
import {
  MessageOutlined,
  TeamOutlined,
  RobotOutlined,
  ApartmentOutlined,
  LogoutOutlined,
  UserOutlined,
  WechatOutlined,
  ClockCircleOutlined,
  SafetyCertificateOutlined,
  AppstoreOutlined,
  BankOutlined,
  CheckSquareOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const { Sider, Content, Header } = Layout;
const { Text } = Typography;

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { token: themeToken } = theme.useToken();

  const menuItems = [
    { key: '/app', icon: <MessageOutlined />, label: '对话' },
    { key: '/app/groups', icon: <TeamOutlined />, label: '群组' },
    { key: '/app/agents', icon: <RobotOutlined />, label: 'Agent' },
    { key: '/app/social', icon: <WechatOutlined />, label: '社交' },
    { key: '/app/workflows', icon: <ApartmentOutlined />, label: '工作流' },
    { key: '/app/scheduled', icon: <ClockCircleOutlined />, label: '定时任务' },
    { key: '/app/tasks', icon: <CheckSquareOutlined />, label: '任务管理' },
    { key: '/app/parliament', icon: <BankOutlined />, label: '议会' },
    { key: '/app/audit', icon: <SafetyCertificateOutlined />, label: '审计日志' },
    { type: 'divider' as const },
    { key: '/app/skills', icon: <AppstoreOutlined />, label: 'Skills 市场' },
    { key: '/app/templates', icon: <AppstoreOutlined />, label: '团队模板' },
    { key: '/app/cli-agents', icon: <CodeOutlined />, label: 'CLI Agent' },
  ];

  const userMenu = {
    items: [
      { key: 'profile', icon: <UserOutlined />, label: user?.display_name || user?.username },
      { type: 'divider' as const },
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') {
        logout();
        navigate('/login');
      }
    },
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ background: themeToken.colorBgContainer }}
        theme="light"
      >
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: `1px solid ${themeToken.colorBorderSecondary}` }}>
          <RobotOutlined style={{ fontSize: 24, color: themeToken.colorPrimary }} />
          {!collapsed && <Text strong style={{ marginLeft: 8, fontSize: 18 }}>aibond</Text>}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout>
        <Header style={{ background: themeToken.colorBgContainer, padding: '0 24px', display: 'flex', justifyContent: 'flex-end', alignItems: 'center', borderBottom: `1px solid ${themeToken.colorBorderSecondary}` }}>
          <Dropdown menu={userMenu} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar icon={<UserOutlined />} />
              <Text>{user?.display_name || user?.username}</Text>
            </div>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
