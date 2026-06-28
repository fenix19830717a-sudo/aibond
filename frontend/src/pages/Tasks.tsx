import React, { useState, useEffect } from 'react';
import { Card, Table, Tag, Typography, message, Space, Button } from 'antd';
import { CheckSquareOutlined, ReloadOutlined } from '@ant-design/icons';
import { api } from '../api';

const { Title, Text } = Typography;

const statusConfig: Record<string, { color: string; label: string }> = {
  active: { color: 'processing', label: '进行中' },
  completed: { color: 'success', label: '已完成' },
  paused: { color: 'warning', label: '已暂停' },
  cancelled: { color: 'default', label: '已取消' },
  pending: { color: 'blue', label: '待处理' },
};

const priorityConfig: Record<string, { color: string; label: string }> = {
  low: { color: 'default', label: '低' },
  normal: { color: 'blue', label: '普通' },
  medium: { color: 'blue', label: '中' },
  high: { color: 'orange', label: '高' },
  urgent: { color: 'red', label: '紧急' },
};

const Tasks: React.FC = () => {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const data = await api.listTasks();
      const taskList = Array.isArray(data) ? data : (data?.value || data?.sessions || []);
      setTasks(taskList);
    } catch (err: any) {
      message.error(err.message || '加载任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (text: string) => <Text strong>{text || '未命名任务'}</Text>,
    },
    {
      title: '群组',
      dataIndex: 'group_id',
      key: 'group_id',
      render: (text: string) => <Text code style={{ fontSize: 12 }}>{text?.slice(0, 8) || '-'}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const sc = statusConfig[status] || { color: 'default', label: status || '未知' };
        return <Tag color={sc.color}>{sc.label}</Tag>;
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      render: (priority: string) => {
        const pc = priorityConfig[priority] || priorityConfig.normal;
        return <Tag color={pc.color}>{pc.label}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {text ? new Date(text).toLocaleString() : '-'}
        </Text>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>
            <CheckSquareOutlined style={{ marginRight: 8 }} />
            任务管理
          </Title>
          <Tag>{tasks.length} 个任务</Tag>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={loadTasks}>刷新</Button>
      </div>
      <Card>
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '暂无任务' }}
        />
      </Card>
    </div>
  );
};

export default Tasks;