import React, { useState, useEffect } from 'react';
import {
  Card, Table, Select, Typography, message, Space, Button, Row, Col, Statistic, Tag,
} from 'antd';
import {
  DownloadOutlined, ReloadOutlined, SafetyCertificateOutlined, UserOutlined, RobotOutlined, FileSearchOutlined, BarChartOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Title, Text } = Typography;

const actorTypeOptions = [
  { value: 'user', label: '用户' },
  { value: 'agent', label: 'Agent' },
  { value: 'system', label: '系统' },
];

const AuditLog: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<any>(null);
  const [actorType, setActorType] = useState<string | undefined>(undefined);
  const [action, setAction] = useState<string | undefined>(undefined);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    loadData();
  }, [actorType, action]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [logsData, statsData] = await Promise.all([
        api.listAudit({ actor_type: actorType, action, limit: 100 }),
        api.getAuditStats().catch(() => null),
      ]);
      setLogs(Array.isArray(logsData) ? logsData : (logsData?.logs || logsData?.value || []));
      setStats(statsData);
    } catch (err: any) {
      message.error(err.message || '加载审计日志失败');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await api.exportAuditCSV({ actor_type: actorType, action });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_log_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch (err: any) {
      message.error(err.message || '导出失败');
    } finally {
      setExporting(false);
    }
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => <Text style={{ fontSize: 12 }}>{text ? new Date(text).toLocaleString() : '-'}</Text>,
      sorter: (a: any, b: any) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      defaultSortOrder: 'descend' as const,
    },
    {
      title: '操作者',
      dataIndex: 'actor_type',
      key: 'actor_type',
      width: 100,
      render: (text: string, record: any) => (
        <Space>
          {text === 'agent' ? <RobotOutlined /> : <UserOutlined />}
          <Text>{record.actor_name || record.actor_id?.slice(0, 8) || text}</Text>
        </Space>
      ),
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 140,
      render: (text: string) => {
        const colorMap: Record<string, string> = {
          create: 'green', update: 'blue', delete: 'red', login: 'purple', logout: 'default',
          register: 'cyan', send_message: 'geekblue', run_workflow: 'volcano',
        };
        return <Tag color={colorMap[text] || 'default'}>{text}</Tag>;
      },
    },
    {
      title: '目标',
      dataIndex: 'target_type',
      key: 'target_type',
      width: 120,
      render: (text: string) => <Tag>{text || '-'}</Tag>,
    },
    {
      title: '目标 ID',
      dataIndex: 'target_id',
      key: 'target_id',
      width: 120,
      ellipsis: true,
      render: (text: string) => <Text type="secondary" style={{ fontSize: 12 }}>{text ? text.slice(0, 12) + '...' : '-'}</Text>,
    },
    {
      title: '详情',
      dataIndex: 'detail',
      key: 'detail',
      ellipsis: true,
      render: (text: string) => <Text type="secondary" style={{ fontSize: 12 }}>{text || '-'}</Text>,
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 130,
      render: (text: string) => <Text code style={{ fontSize: 12 }}>{text || '-'}</Text>,
    },
  ];

  const statCards = stats ? [
    { title: '总操作数', value: stats.total || 0, icon: <BarChartOutlined />, color: '#1677ff' },
    { title: '今日操作', value: stats.today || 0, icon: <FileSearchOutlined />, color: '#52c41a' },
    { title: '用户操作', value: stats.user_count || 0, icon: <UserOutlined />, color: '#722ed1' },
    { title: 'Agent 操作', value: stats.agent_count || 0, icon: <RobotOutlined />, color: '#faad14' },
  ] : [
    { title: '总操作数', value: logs.length, icon: <BarChartOutlined />, color: '#1677ff' },
    { title: '今日操作', value: '-', icon: <FileSearchOutlined />, color: '#52c41a' },
    { title: '用户操作', value: '-', icon: <UserOutlined />, color: '#722ed1' },
    { title: 'Agent 操作', value: '-', icon: <RobotOutlined />, color: '#faad14' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}><SafetyCertificateOutlined style={{ marginRight: 8 }} />审计日志</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={handleExport}>导出 CSV</Button>
        </Space>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        {statCards.map((item, idx) => (
          <Col xs={12} sm={6} key={idx}>
            <Card size="small">
              <Statistic
                title={<Text type="secondary" style={{ fontSize: 13 }}>{item.title}</Text>}
                value={item.value}
                prefix={<span style={{ color: item.color }}>{item.icon}</span>}
                valueStyle={{ fontSize: 24 }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            placeholder="操作者类型"
            allowClear
            style={{ width: 140 }}
            value={actorType}
            onChange={setActorType}
            options={actorTypeOptions}
          />
          <Select
            placeholder="动作类型"
            allowClear
            style={{ width: 140 }}
            value={action}
            onChange={setAction}
            options={[
              { value: 'create', label: '创建' },
              { value: 'update', label: '更新' },
              { value: 'delete', label: '删除' },
              { value: 'login', label: '登录' },
              { value: 'logout', label: '登出' },
              { value: 'register', label: '注册' },
              { value: 'send_message', label: '发送消息' },
              { value: 'run_workflow', label: '运行工作流' },
            ]}
          />
        </Space>
        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 15, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          scroll={{ x: 800 }}
          locale={{ emptyText: '暂无审计日志' }}
        />
      </Card>
    </div>
  );
};

export default AuditLog;
