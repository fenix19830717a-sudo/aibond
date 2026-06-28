import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Switch, Typography, message, Space, Tag, Popconfirm, Tooltip, Badge, Spin, Alert,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, ClockCircleOutlined, PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, BulbOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Title, Text } = Typography;

const actionTypeOptions = [
  { value: 'run_workflow', label: '运行工作流' },
  { value: 'send_message', label: '发送消息' },
  { value: 'call_api', label: '调用 API' },
  { value: 'trigger_session', label: '触发会话' },
];

const timezoneOptions = [
  { value: 'Asia/Shanghai', label: 'Asia/Shanghai (UTC+8)' },
  { value: 'UTC', label: 'UTC (UTC+0)' },
  { value: 'America/New_York', label: 'America/New_York (UTC-5)' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles (UTC-8)' },
  { value: 'Europe/London', label: 'Europe/London (UTC+0)' },
  { value: 'Europe/Berlin', label: 'Europe/Berlin (UTC+1)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
];

const quickOptions = [
  { label: '每天早上8点', nl: '每天早上8点', cron: '0 8 * * *' },
  { label: '每天下午6点', nl: '每天下午6点', cron: '0 18 * * *' },
  { label: '每周一早上9点', nl: '每周一早上9点', cron: '0 9 * * 1' },
  { label: '每30分钟', nl: '每30分钟', cron: '*/30 * * * *' },
  { label: '每小时', nl: '每小时', cron: '0 * * * *' },
  { label: '每周末凌晨2点', nl: '每周末凌晨2点', cron: '0 2 * * 0,6' },
];

interface CronParseResult {
  cron_expression: string;
  description: string;
}

const ScheduledTasks: React.FC = () => {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [currentTask, setCurrentTask] = useState<any>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  // NL Cron state
  const [nlCronInput, setNlCronInput] = useState('');
  const [parsingCron, setParsingCron] = useState(false);
  const [cronResult, setCronResult] = useState<CronParseResult | null>(null);
  const [nlCronInputEdit, setNlCronInputEdit] = useState('');
  const [parsingCronEdit, setParsingCronEdit] = useState(false);
  const [cronResultEdit, setCronResultEdit] = useState<CronParseResult | null>(null);

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const data = await api.listScheduledTasks();
      setTasks(Array.isArray(data) ? data : (data?.value || data?.tasks || []));
    } catch (err: any) {
      message.error(err.message || '加载定时任务失败');
    } finally {
      setLoading(false);
    }
  };

  const handleParseCron = async (nlValue: string, isEdit: boolean = false) => {
    if (!nlValue.trim()) return;
    if (isEdit) {
      setParsingCronEdit(true);
      setCronResultEdit(null);
    } else {
      setParsingCron(true);
      setCronResult(null);
    }
    try {
      const result = await api.parseCron(nlValue);
      if (isEdit) {
        setCronResultEdit(result);
        if (result.cron_expression) {
          editForm.setFieldsValue({ cron_expression: result.cron_expression });
        }
      } else {
        setCronResult(result);
        if (result.cron_expression) {
          form.setFieldsValue({ cron_expression: result.cron_expression });
        }
      }
    } catch {
      // Fallback: simple client-side mapping
      const fallback = quickOptions.find(
        (q) => q.nl === nlValue || q.label === nlValue
      );
      if (fallback) {
        const fallbackResult = { cron_expression: fallback.cron, description: fallback.label };
        if (isEdit) {
          setCronResultEdit(fallbackResult);
          editForm.setFieldsValue({ cron_expression: fallback.cron });
        } else {
          setCronResult(fallbackResult);
          form.setFieldsValue({ cron_expression: fallback.cron });
        }
      }
    } finally {
      if (isEdit) {
        setParsingCronEdit(false);
      } else {
        setParsingCron(false);
      }
    }
  };

  const handleQuickSelect = (option: { label: string; nl: string; cron: string }, isEdit: boolean = false) => {
    if (isEdit) {
      setNlCronInputEdit(option.nl);
      setCronResultEdit({ cron_expression: option.cron, description: option.label });
      editForm.setFieldsValue({ cron_expression: option.cron });
    } else {
      setNlCronInput(option.nl);
      setCronResult({ cron_expression: option.cron, description: option.label });
      form.setFieldsValue({ cron_expression: option.cron });
    }
  };

  const handleCreate = async (values: any) => {
    setSubmitting(true);
    try {
      await api.createScheduledTask(
        values.name,
        values.cron_expression,
        values.timezone || 'Asia/Shanghai',
        values.action_type,
        values.action_config ? JSON.parse(values.action_config) : {},
      );
      message.success('定时任务创建成功');
      setModalOpen(false);
      form.resetFields();
      setNlCronInput('');
      setCronResult(null);
      loadTasks();
    } catch (err: any) {
      message.error(err.message || '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdate = async (values: any) => {
    setSubmitting(true);
    try {
      const updateData: any = { name: values.name, cron_expression: values.cron_expression, timezone: values.timezone, enabled: values.enabled };
      if (values.action_config) {
        try { updateData.action_config = JSON.parse(values.action_config); } catch { updateData.action_config = {}; }
      }
      await api.updateScheduledTask(currentTask.id, updateData);
      message.success('更新成功');
      setEditModalOpen(false);
      editForm.resetFields();
      setCurrentTask(null);
      setNlCronInputEdit('');
      setCronResultEdit(null);
      loadTasks();
    } catch (err: any) {
      message.error(err.message || '更新失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (taskId: string, enabled: boolean) => {
    try {
      await api.updateScheduledTask(taskId, { enabled });
      message.success(enabled ? '已启用' : '已禁用');
      loadTasks();
    } catch (err: any) {
      message.error(err.message || '操作失败');
    }
  };

  const handleDelete = async (taskId: string) => {
    try {
      await api.deleteScheduledTask(taskId);
      message.success('已删除');
      loadTasks();
    } catch (err: any) {
      message.error(err.message || '删除失败');
    }
  };

  const openEditModal = (task: any) => {
    setCurrentTask(task);
    editForm.setFieldsValue({
      name: task.name,
      cron_expression: task.cron_expression,
      timezone: task.timezone || 'Asia/Shanghai',
      enabled: task.enabled !== false,
      action_config: task.action_config ? JSON.stringify(task.action_config, null, 2) : '',
    });
    setNlCronInputEdit('');
    setCronResultEdit(null);
    setEditModalOpen(true);
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: 'Cron 表达式',
      dataIndex: 'cron_expression',
      key: 'cron_expression',
      render: (text: string) => <Text code>{text}</Text>,
    },
    {
      title: '时区',
      dataIndex: 'timezone',
      key: 'timezone',
      render: (text: string) => <Tag>{text || 'Asia/Shanghai'}</Tag>,
    },
    {
      title: 'Action 类型',
      dataIndex: 'action_type',
      key: 'action_type',
      render: (text: string) => {
        const found = actionTypeOptions.find(o => o.value === text);
        return <Tag color="blue">{found?.label || text}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean, record: any) => (
        <Switch
          checked={enabled !== false}
          onChange={(val) => handleToggle(record.id, val)}
          checkedChildren={<PlayCircleOutlined />}
          unCheckedChildren={<PauseCircleOutlined />}
        />
      ),
    },
    {
      title: '上次执行',
      dataIndex: 'last_run_at',
      key: 'last_run_at',
      render: (text: string) => <Text type="secondary" style={{ fontSize: 12 }}>{text ? new Date(text).toLocaleString() : '从未执行'}</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: any) => (
        <Space>
          <Tooltip title="编辑"><Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)} /></Tooltip>
          <Popconfirm title="确认删除此定时任务?" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除"><Button type="text" size="small" danger icon={<DeleteOutlined />} /></Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const renderNLCronSection = (
    nlInput: string,
    setNlInput: (v: string) => void,
    parsing: boolean,
    result: CronParseResult | null,
    _formInstance: any,
    isEdit: boolean,
  ) => (
    <>
      <Form.Item label="自然语言描述">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Input
            prefix={<BulbOutlined style={{ color: '#faad14' }} />}
            value={nlInput}
            onChange={(e) => setNlInput(e.target.value)}
            onBlur={(e) => {
              if (e.target.value.trim()) {
                handleParseCron(e.target.value, isEdit);
              }
            }}
            placeholder="例如：每天早上9点、每周一上午10点、每30分钟"
            suffix={
              parsing ? <Spin size="small" /> : (
                <Button
                  type="link"
                  size="small"
                  style={{ padding: 0 }}
                  onClick={() => handleParseCron(nlInput, isEdit)}
                >
                  解析
                </Button>
              )
            }
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {quickOptions.map((opt) => (
              <Tag
                key={opt.label}
                style={{ cursor: 'pointer' }}
                color="blue"
                onClick={() => handleQuickSelect(opt, isEdit)}
              >
                {opt.label}
              </Tag>
            ))}
          </div>
        </div>
      </Form.Item>
      {result && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          message={
            <Space direction="vertical" size={0}>
              <Text>
                <Text strong>Cron 表达式：</Text>
                <Text code>{result.cron_expression}</Text>
              </Text>
              {result.description && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  描述：{result.description}
                </Text>
              )}
            </Space>
          }
        />
      )}
    </>
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}><ClockCircleOutlined style={{ marginRight: 8 }} />定时任务</Title>
          <Badge count={tasks.length} />
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadTasks}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setNlCronInput(''); setCronResult(null); setModalOpen(true); }}>创建任务</Button>
        </Space>
      </div>
      <Card>
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '暂无定时任务' }}
        />
      </Card>

      {/* 创建定时任务 Modal */}
      <Modal title="创建定时任务" open={modalOpen} onCancel={() => setModalOpen(false)} footer={null} width={600}>
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}>
            <Input placeholder="例如：每日报告生成" />
          </Form.Item>
          {renderNLCronSection(nlCronInput, setNlCronInput, parsingCron, cronResult, form, false)}
          <Form.Item name="cron_expression" label="Cron 表达式" rules={[{ required: true, message: '请输入 Cron 表达式' }]} extra="格式: 分 时 日 月 星期 (例如: 0 8 * * * 表示每天8点)">
            <Input placeholder="0 8 * * *" />
          </Form.Item>
          <Form.Item name="timezone" label="时区" initialValue="Asia/Shanghai">
            <Select style={{ width: '100%' }} options={timezoneOptions} />
          </Form.Item>
          <Form.Item name="action_type" label="Action 类型" rules={[{ required: true, message: '请选择 Action 类型' }]}>
            <Select style={{ width: '100%' }} options={actionTypeOptions} />
          </Form.Item>
          <Form.Item name="action_config" label="Action 配置 (JSON)" extra="JSON 格式的配置参数">
            <Input.TextArea placeholder='{"workflow_id": "xxx"}' rows={3} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={submitting}>创建</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑定时任务 Modal */}
      <Modal title="编辑定时任务" open={editModalOpen} onCancel={() => { setEditModalOpen(false); setCurrentTask(null); }} footer={null} width={600}>
        <Form form={editForm} onFinish={handleUpdate} layout="vertical">
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="任务名称" />
          </Form.Item>
          {renderNLCronSection(nlCronInputEdit, setNlCronInputEdit, parsingCronEdit, cronResultEdit, editForm, true)}
          <Form.Item name="cron_expression" label="Cron 表达式" rules={[{ required: true }]}>
            <Input placeholder="0 8 * * *" />
          </Form.Item>
          <Form.Item name="timezone" label="时区">
            <Select style={{ width: '100%' }} options={timezoneOptions} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
          <Form.Item name="action_config" label="Action 配置 (JSON)">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={submitting}>保存</Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ScheduledTasks;