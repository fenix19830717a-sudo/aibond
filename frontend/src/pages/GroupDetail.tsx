import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Tabs, Card, Button, List, Tag, Typography, message, Space, Input, Form, Modal, Select, Badge, Avatar, Spin, Empty, Popconfirm, Descriptions, Progress,
} from 'antd';
import {
  ArrowLeftOutlined, SendOutlined, PlusOutlined, TeamOutlined, RobotOutlined, UserOutlined, FileOutlined, SettingOutlined, CheckCircleOutlined, ClockCircleOutlined, StarOutlined, CrownOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../store/authStore';
import { api } from '../api';

const { Title, Text } = Typography;
const { TextArea } = Input;

const roleColorMap: Record<string, string> = {
  owner: 'gold', lead: 'blue', admin: 'purple', member: 'default', viewer: 'default',
};
const roleLabelMap: Record<string, string> = {
  owner: '群主', lead: '队长', admin: '管理员', member: '成员', viewer: '观察者',
};
const statusConfig: Record<string, { color: string; label: string }> = {
  active: { color: 'processing', label: '进行中' },
  completed: { color: 'success', label: '已完成' },
  paused: { color: 'warning', label: '已暂停' },
  cancelled: { color: 'default', label: '已取消' },
};
const priorityConfig: Record<string, { color: string; label: string }> = {
  low: { color: 'default', label: '低' },
  normal: { color: 'blue', label: '普通' },
  medium: { color: 'blue', label: '中' },
  high: { color: 'orange', label: '高' },
  urgent: { color: 'red', label: '紧急' },
};

const GroupDetail: React.FC = () => {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [group, setGroup] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [resources, setResources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [messageLoading, setMessageLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [activeTab, setActiveTab] = useState('messages');
  const [messageInput, setMessageInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [memberForm] = Form.useForm();
  const [taskForm] = Form.useForm();
  const [availableAgents, setAvailableAgents] = useState<any[]>([]);
  const [memberType, setMemberType] = useState<string>('agent');
  const [editingGroup, setEditingGroup] = useState(false);
  const [editForm] = Form.useForm();

  useEffect(() => {
    if (groupId) {
      loadGroup();
      loadMessages();
      loadTasks();
      loadResources();
    }
  }, [groupId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadGroup = async () => {
    try {
      const data = await api.getGroupDetail(groupId!);
      setGroup(data);
    } catch (err: any) {
      message.error(err.message || '加载群组失败');
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async () => {
    setMessageLoading(true);
    try {
      const data = await api.getMessages(groupId!, 50, 0);
      setMessages(data.messages || data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setMessageLoading(false);
    }
  };

  const loadTasks = async () => {
    try {
      const data = await api.listTasks(groupId);
      const taskList = Array.isArray(data) ? data : (data?.value || []);
      setTasks(taskList);
    } catch (err) {
      console.error(err);
    }
  };

  const loadResources = async () => {
    try {
      const data = await api.listResources(groupId!);
      setResources(data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSend = async () => {
    if (!messageInput.trim()) return;
    setSending(true);
    try {
      await api.sendMessage(groupId!, 'user', user!.id, messageInput.trim());
      setMessageInput('');
      await loadMessages();
    } catch (err: any) {
      message.error(err.message || '发送失败');
    } finally {
      setSending(false);
    }
  };

  const handleAddMember = async (values: any) => {
    try {
      await api.addMember(groupId!, values.member_type, values.member_id, values.role || 'member');
      message.success('成员添加成功');
      setMemberModalOpen(false);
      memberForm.resetFields();
      loadGroup();
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const handleCreateTask = async (values: any) => {
    try {
      await api.createTask(groupId!, values.title, values.description || '', 'user', user?.id || '', values.assigned_to ? [values.assigned_to] : [], values.priority);
      message.success('任务创建成功');
      setTaskModalOpen(false);
      taskForm.resetFields();
      loadTasks();
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const handleUpdateGroup = async (_values: any) => {
    try {
      // No dedicated update API, so we display a toast
      message.info('群组信息已保存（后端暂不支持直接更新）');
      setEditingGroup(false);
    } catch (err: any) {
      message.error(err.message);
    }
  };

  useEffect(() => {
    const loadAgents = async () => {
      try {
        const data = await api.listAvailableAgents();
        setAvailableAgents(data || []);
      } catch (err) {
        console.error(err);
      }
    };
    loadAgents();
  }, []);

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}><Spin size="large" /></div>;
  }

  if (!group) {
    return <Empty description="群组不存在" />;
  }

  const tabItems = [
    {
      key: 'messages',
      label: `群消息 (${messages.length})`,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', height: 500 }}>
          <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
            {messageLoading ? (
              <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
            ) : messages.length === 0 ? (
              <Empty description="暂无消息" />
            ) : (
              messages.map((msg: any) => (
                <div key={msg.id} style={{ display: 'flex', gap: 8, marginBottom: 12, justifyContent: msg.sender_type === 'user' && msg.sender_user_id === user?.id ? 'flex-end' : 'flex-start' }}>
                  {!(msg.sender_type === 'user' && msg.sender_user_id === user?.id) && (
                    <Avatar size="small" icon={msg.sender_type === 'agent' ? <RobotOutlined /> : <UserOutlined />} />
                  )}
                  <div style={{ maxWidth: '70%' }}>
                    <div style={{ fontSize: 11, color: '#999', marginBottom: 2 }}>
                      {msg.sender_name || (msg.sender_type === 'agent' ? 'Agent' : '用户')}
                      <span style={{ marginLeft: 8 }}>{new Date(msg.created_at).toLocaleTimeString()}</span>
                    </div>
                    <div style={{
                      background: msg.sender_type === 'user' && msg.sender_user_id === user?.id ? '#1677ff' : 'rgba(255,255,255,0.08)',
                      color: msg.sender_type === 'user' && msg.sender_user_id === user?.id ? '#fff' : '#ddd',
                      padding: '8px 12px',
                      borderRadius: 8,
                      fontSize: 14,
                    }}>
                      {msg.content}
                    </div>
                  </div>
                  {msg.sender_type === 'user' && msg.sender_user_id === user?.id && (
                    <Avatar size="small" icon={<UserOutlined />} />
                  )}
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
          <div style={{ display: 'flex', gap: 8, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 12 }}>
            <Input
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              onPressEnter={handleSend}
              placeholder="输入消息..."
              style={{ flex: 1 }}
            />
            <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={handleSend} disabled={!messageInput.trim()}>发送</Button>
          </div>
        </div>
      ),
    },
    {
      key: 'tasks',
      label: `任务 (${tasks.length})`,
      children: (
        <div>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setTaskModalOpen(true)} style={{ marginBottom: 16 }}>创建任务</Button>
          <List
            dataSource={tasks}
            renderItem={(task: any) => {
              const sc = statusConfig[task.status] || statusConfig.active;
              const pc = priorityConfig[task.priority] || priorityConfig.normal;
              return (
                <List.Item
                  actions={[
                    <Popconfirm title="确认完成?" onConfirm={() => api.completeTask(task.id).then(() => loadTasks())}>
                      <Button type="link" size="small" icon={<CheckCircleOutlined />}>完成</Button>
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Badge status={sc.color as any} />
                        <span>{task.title}</span>
                        <Tag color={pc.color}>{pc.label}</Tag>
                        <Tag color={sc.color}>{sc.label}</Tag>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={4}>
                        {task.description && <Text type="secondary">{task.description}</Text>}
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          <ClockCircleOutlined /> {task.created_at?.split('T')[0]}
                          {task.progress !== undefined && <Progress percent={task.progress} size="small" style={{ width: 80, marginLeft: 12 }} />}
                        </Text>
                      </Space>
                    }
                  />
                </List.Item>
              );
            }}
            locale={{ emptyText: '暂无任务' }}
          />
        </div>
      ),
    },
    {
      key: 'resources',
      label: `资源 (${resources.length})`,
      children: (
        <List
          dataSource={resources}
          renderItem={(res: any) => (
            <List.Item>
              <List.Item.Meta
                avatar={<Avatar icon={<FileOutlined />} />}
                title={res.original_name || res.filename || '未命名文件'}
                description={
                  <Space>
                    <Text type="secondary">{res.mime_type || '未知类型'}</Text>
                    <Text type="secondary">{res.file_size ? `${(res.file_size / 1024).toFixed(1)} KB` : ''}</Text>
                  </Space>
                }
              />
              <Button type="link" size="small" href={api.downloadFile(res.id)}>下载</Button>
            </List.Item>
          )}
          locale={{ emptyText: '暂无资源' }}
        />
      ),
    },
    {
      key: 'members',
      label: `成员 (${group.members?.length || 0})`,
      children: (
        <div>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setMemberModalOpen(true); setMemberType('agent'); memberForm.resetFields(); memberForm.setFieldValue('member_type', 'agent'); }} style={{ marginBottom: 16 }}>添加成员</Button>
          <List
            grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
            dataSource={group.members || []}
            renderItem={(member: any) => (
              <List.Item>
                <Card size="small">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Avatar icon={member.type === 'agent' ? <RobotOutlined /> : <UserOutlined />} />
                      <div>
                        <Text strong>{member.name || member.id?.slice(0, 8)}</Text>
                        <br />
                        <Tag color={roleColorMap[member.role]} style={{ marginTop: 2 }}>
                          {roleLabelMap[member.role] || member.role}
                        </Tag>
                      </div>
                    </div>
                    {member.type === 'agent' && member.status && (
                      <Badge status={member.status === 'online' ? 'success' : 'default'} text={member.status === 'online' ? '在线' : '离线'} />
                    )}
                    {member.type === 'agent' && member.skills?.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                        {member.skills.slice(0, 4).map((s: string) => <Tag key={s} color="blue">{s}</Tag>)}
                      </div>
                    )}
                  </Space>
                </Card>
              </List.Item>
            )}
            locale={{ emptyText: '暂无成员' }}
          />
        </div>
      ),
    },
    {
      key: 'settings',
      label: '设置',
      children: editingGroup ? (
        <Form form={editForm} onFinish={handleUpdateGroup} layout="vertical" initialValues={{ name: group.name, description: group.description }}>
          <Form.Item name="name" label="群组名称" rules={[{ required: true }]}>
            <Input placeholder="输入群组名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea placeholder="输入群组描述" rows={3} />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">保存</Button>
            <Button onClick={() => setEditingGroup(false)}>取消</Button>
          </Space>
        </Form>
      ) : (
        <Descriptions bordered column={1}>
          <Descriptions.Item label="群组 ID">{group.id}</Descriptions.Item>
          <Descriptions.Item label="群组名称">{group.name}</Descriptions.Item>
          <Descriptions.Item label="描述">{group.description || '暂无描述'}</Descriptions.Item>
          <Descriptions.Item label="创建者 ID">{group.owner_id}</Descriptions.Item>
          <Descriptions.Item label="成员数量">{group.members?.length || 0}</Descriptions.Item>
          <Descriptions.Item label="操作">
            <Button type="primary" icon={<SettingOutlined />} onClick={() => setEditingGroup(true)}>编辑</Button>
          </Descriptions.Item>
        </Descriptions>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/groups')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>
          <TeamOutlined style={{ marginRight: 8 }} />
          {group.name}
        </Title>
        <Text type="secondary">{group.description || ''}</Text>
      </div>
      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Card>

      <Modal title="添加成员" open={memberModalOpen} onCancel={() => setMemberModalOpen(false)} footer={null}>
        <Form form={memberForm} onFinish={handleAddMember} layout="vertical">
          <Form.Item name="member_type" label="成员类型" rules={[{ required: true }]} initialValue="agent">
            <Select
              style={{ width: '100%' }}
              onChange={(type) => { setMemberType(type); memberForm.setFieldValue('member_id', undefined); }}
              options={[{ value: 'agent', label: 'AI Agent' }, { value: 'user', label: '用户' }]}
            />
          </Form.Item>
          {memberType === 'agent' ? (
            <Form.Item name="member_id" label="选择 Agent" rules={[{ required: true, message: '请选择一个 Agent' }]}>
              <Select
                style={{ width: '100%' }}
                placeholder="选择要添加的 Agent"
                showSearch
                optionFilterProp="children"
                options={availableAgents.map((a: any) => ({ value: a.id, label: `${a.name} (${a.status})` }))}
              />
            </Form.Item>
          ) : (
            <Form.Item name="member_id" label="用户 ID" rules={[{ required: true, message: '请输入用户 ID' }]}>
              <Input placeholder="输入用户ID" />
            </Form.Item>
          )}
          <Form.Item name="role" label="角色" initialValue="member">
            <Select
              style={{ width: '100%' }}
              options={[
                { value: 'lead', label: <Space><StarOutlined /> 队长</Space> },
                { value: 'admin', label: <Space><CrownOutlined /> 管理员</Space> },
                { value: 'member', label: '成员' },
                { value: 'viewer', label: '观察者' },
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>添加</Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="创建任务" open={taskModalOpen} onCancel={() => setTaskModalOpen(false)} footer={null}>
        <Form form={taskForm} onFinish={handleCreateTask} layout="vertical">
          <Form.Item name="title" label="任务标题" rules={[{ required: true, message: '请输入任务标题' }]}>
            <Input placeholder="输入任务标题" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea placeholder="输入任务描述" rows={3} />
          </Form.Item>
          <Form.Item name="assigned_to" label="分配给" rules={[{ required: true, message: '请选择分配对象' }]}>
            <Select
              style={{ width: '100%' }}
              placeholder="选择任务执行者"
              showSearch
              optionFilterProp="children"
              options={[
                { value: user!.id, label: `我自己 (${user!.username})` },
                ...(group.members || [])
                  .filter((m: any) => m.id !== user!.id)
                  .map((m: any) => ({ value: m.id, label: `${m.name} (${m.type === 'agent' ? 'Agent' : '用户'})` })),
                ...(availableAgents || []).map((a: any) => ({ value: a.id, label: `${a.name} (Agent)` })),
              ]}
            />
          </Form.Item>
          <Form.Item name="priority" label="优先级" initialValue="normal">
            <Select
              style={{ width: '100%' }}
              options={[
                { value: 'low', label: '低' },
                { value: 'normal', label: '普通' },
                { value: 'high', label: '高' },
                { value: 'urgent', label: '紧急' },
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>创建</Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default GroupDetail;
