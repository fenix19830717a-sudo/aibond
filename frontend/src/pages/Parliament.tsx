import React, { useState, useEffect } from 'react';
import {
  Card, Button, Tag, Typography, message, Space, List, Modal, Form, Input, Select, InputNumber, Spin, Empty,
} from 'antd';
import {
  PlusOutlined, BankOutlined, ReloadOutlined, RightOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

const { Title, Text } = Typography;

interface ParliamentItem {
  id: string;
  title: string;
  topic: string;
  status: string;
  consensus_type: string;
  round: number;
  max_rounds: number;
  group_id: string;
  created_at: string;
}

const statusConfig: Record<string, { color: string; label: string }> = {
  deliberating: { color: 'blue', label: '协商中' },
  voting: { color: 'orange', label: '投票中' },
  consensus_reached: { color: 'green', label: '达成共识' },
  deadlocked: { color: 'red', label: '僵局' },
  escalated: { color: 'volcano', label: '已升级' },
  resolved: { color: 'purple', label: '已裁决' },
};

const consensusTypeLabels: Record<string, string> = {
  majority: '多数决',
  supermajority: '绝对多数',
  unanimous: '全票一致',
  weighted: '权重投票',
  ranked_choice: '排序选择',
};

const Parliament: React.FC = () => {
  const navigate = useNavigate();
  const [parliaments, setParliaments] = useState<ParliamentItem[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const groupsData = await api.listGroups();
      const groupList = Array.isArray(groupsData) ? groupsData : (groupsData?.value || []);
      setGroups(groupList);

      const allParliaments: ParliamentItem[] = [];
      for (const group of groupList) {
        try {
          const data = await api.listParliaments(group.id);
          const items = Array.isArray(data) ? data : (data?.value || data?.parliaments || []);
          items.forEach((item: ParliamentItem) => {
            allParliaments.push({ ...item, group_id: group.id });
          });
        } catch {
          // Group may not have parliaments yet
        }
      }
      setParliaments(allParliaments);
    } catch (err: any) {
      message.error(err.message || '加载议会列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (values: any) => {
    setSubmitting(true);
    try {
      await api.createParliament({
        group_id: values.group_id,
        title: values.title,
        topic: values.topic,
        consensus_type: values.consensus_type || 'majority',
        min_confidence: values.min_confidence,
        max_rounds: values.max_rounds,
      });
      message.success('议会创建成功');
      setModalOpen(false);
      form.resetFields();
      loadData();
    } catch (err: any) {
      message.error(err.message || '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCardClick = (id: string) => {
    navigate(`/parliament/${id}`);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>
            <BankOutlined style={{ marginRight: 8 }} />
            议会
          </Title>
          <Tag>{parliaments.length} 个议会</Tag>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModalOpen(true); }}>
            创建议会
          </Button>
        </Space>
      </div>

      {parliaments.length === 0 ? (
        <Card>
          <Empty description="暂无议会" />
        </Card>
      ) : (
        <List
          grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 3 }}
          dataSource={parliaments}
          renderItem={(item: ParliamentItem) => {
            const sc = statusConfig[item.status] || { color: 'default', label: item.status };
            return (
              <List.Item>
                <Card
                  title={
                    <Space>
                      <BankOutlined />
                      <span>{item.title}</span>
                    </Space>
                  }
                  extra={
                    <Tag color={sc.color}>{sc.label}</Tag>
                  }
                  style={{ height: '100%', cursor: 'pointer' }}
                  hoverable
                  onClick={() => handleCardClick(item.id)}
                >
                  <Space direction="vertical" style={{ width: '100%' }} size={8}>
                    {item.topic && (
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        议题: {item.topic}
                      </Text>
                    )}
                    <Space size={8}>
                      <Tag color="cyan">
                        {consensusTypeLabels[item.consensus_type] || item.consensus_type}
                      </Tag>
                      <Tag>轮次: {item.round || 0}{item.max_rounds ? `/${item.max_rounds}` : ''}</Tag>
                    </Space>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        创建时间: {item.created_at ? new Date(item.created_at).toLocaleString() : '-'}
                      </Text>
                      <Button type="link" size="small" icon={<RightOutlined />}>
                        详情
                      </Button>
                    </div>
                  </Space>
                </Card>
              </List.Item>
            );
          }}
        />
      )}

      <Modal
        title="创建议会"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={560}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item
            name="group_id"
            label="所属群组"
            rules={[{ required: true, message: '请选择群组' }]}
          >
            <Select
              style={{ width: '100%' }}
              placeholder="选择群组"
              options={groups.map((g: any) => ({
                value: g.id,
                label: g.name,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="title"
            label="议会标题"
            rules={[{ required: true, message: '请输入议会标题' }]}
          >
            <Input placeholder="例如：项目架构决策讨论" />
          </Form.Item>
          <Form.Item
            name="topic"
            label="议题"
            rules={[{ required: true, message: '请输入议题' }]}
          >
            <Input.TextArea placeholder="描述需要讨论的议题" rows={3} />
          </Form.Item>
          <Form.Item name="consensus_type" label="共识类型" initialValue="majority">
            <Select
              style={{ width: '100%' }}
              options={[
                { value: 'majority', label: '多数决' },
                { value: 'supermajority', label: '绝对多数 (2/3)' },
                { value: 'unanimous', label: '全票一致' },
                { value: 'weighted', label: '权重投票' },
                { value: 'ranked_choice', label: '排序选择' },
              ]}
            />
          </Form.Item>
          <Form.Item name="min_confidence" label="最低置信度" initialValue={0.5}>
            <InputNumber
              min={0}
              max={1}
              step={0.1}
              style={{ width: '100%' }}
              placeholder="0.5"
            />
          </Form.Item>
          <Form.Item name="max_rounds" label="最大轮次" initialValue={3}>
            <InputNumber
              min={1}
              max={10}
              style={{ width: '100%' }}
              placeholder="3"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={submitting}>
              创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Parliament;