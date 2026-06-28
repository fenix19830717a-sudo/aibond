import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Tag, Typography, message, Space, Button, Modal, Form,
  Select, Input, InputNumber, Tabs, Descriptions, Switch, Tooltip,
  Badge, Empty, Row, Col, Statistic
} from 'antd';
import {
  CodeOutlined, ReloadOutlined, SettingOutlined, PlayCircleOutlined,
  SendOutlined, NodeIndexOutlined, ApiOutlined, ThunderboltOutlined,
  CloudServerOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ClockCircleOutlined, SyncOutlined, ExperimentOutlined
} from '@ant-design/icons';
import { api } from '../api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const statusConfig: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  queued: { color: 'default', label: '排队中', icon: <ClockCircleOutlined /> },
  running: { color: 'processing', label: '执行中', icon: <SyncOutlined spin /> },
  completed: { color: 'success', label: '已完成', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', label: '失败', icon: <CloseCircleOutlined /> },
  cancelled: { color: 'default', label: '已取消', icon: <CloseCircleOutlined /> },
};

const gateStatusConfig: Record<string, { color: string; label: string }> = {
  primary_pending: { color: 'default', label: '待处理' },
  primary_running: { color: 'processing', label: '执行中' },
  primary_completed: { color: 'blue', label: '已完成' },
  review_pending: { color: 'orange', label: '待评审' },
  review_running: { color: 'processing', label: '评审中' },
  review_passed: { color: 'green', label: '评审通过' },
  review_attention: { color: 'red', label: '需关注' },
  verification_pending: { color: 'purple', label: '待验证' },
  verification_running: { color: 'processing', label: '验证中' },
  accepted: { color: 'success', label: '已接受' },
  failed: { color: 'error', label: '已失败' },
};

const modeConfig: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  websocket: { color: 'blue', label: 'WebSocket', icon: <CloudServerOutlined /> },
  command: { color: 'green', label: 'CLI 命令', icon: <CodeOutlined /> },
  mock: { color: 'orange', label: 'Mock', icon: <ExperimentOutlined /> },
};

const tierConfig: Record<string, { color: string; label: string }> = {
  budget: { color: 'default', label: '经济型' },
  standard: { color: 'blue', label: '标准型' },
  premium: { color: 'gold', label: '高级型' },
};

const CliAgents: React.FC = () => {
  const [agents, setAgents] = useState<any[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [taskLoading, setTaskLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('agents');
  const [configureOpen, setConfigureOpen] = useState(false);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [modelPool, setModelPool] = useState<any>({});
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [configForm] = Form.useForm();
  const [submitForm] = Form.useForm();
  const [taskDetail, setTaskDetail] = useState<any>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const loadAgents = useCallback(async () => {
    try {
      const data = await api.listAgents();
      const agentList = Array.isArray(data) ? data : (data?.value || data?.agents || []);
      // Load specs for each agent
      const enriched = await Promise.all(
        agentList.map(async (a: any) => {
          try {
            const spec = await api.getCliAgentSpec(a.id);
            return { ...a, cliSpec: spec };
          } catch {
            return { ...a, cliSpec: null };
          }
        })
      );
      setAgents(enriched);
    } catch (err: any) {
      message.error(err.message || '加载 Agent 列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTasks = useCallback(async () => {
    setTaskLoading(true);
    try {
      const data = await api.listCliTasks();
      setTasks(data?.tasks || []);
    } catch (err: any) {
      message.error(err.message || '加载任务列表失败');
    } finally {
      setTaskLoading(false);
    }
  }, []);

  const loadModelPool = useCallback(async () => {
    try {
      const data = await api.getCliModelPool();
      setModelPool(data?.models || {});
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadAgents();
    loadTasks();
    loadModelPool();
  }, [loadAgents, loadTasks, loadModelPool]);

  const handleConfigure = (agent: any) => {
    setSelectedAgent(agent);
    const spec = agent.cliSpec || {};
    configForm.setFieldsValue({
      mode: spec.mode || 'websocket',
      command: (spec.command || []).join(' '),
      timeout: spec.timeout || 1800,
      cwd: spec.cwd || '',
      model_tier: spec.model_tier || 'standard',
      model_strengths: (spec.model_strengths || []).join(', '),
    });
    setConfigureOpen(true);
  };

  const handleConfigureSubmit = async () => {
    try {
      const values = await configForm.validateFields();
      const cmdStr = values.command?.trim() || '';
      const command = cmdStr ? cmdStr.split(/\s+/) : [];
      await api.configureCliAgent(
        selectedAgent.id,
        values.mode,
        command,
        values.timeout,
        values.cwd || '',
        {},
        values.model_tier,
        (values.model_strengths || '').split(',').map((s: string) => s.trim()).filter(Boolean),
      );
      message.success('Agent CLI 配置成功');
      setConfigureOpen(false);
      loadAgents();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err.message || '配置失败');
    }
  };

  const handleSubmitTask = (agent: any) => {
    setSelectedAgent(agent);
    submitForm.resetFields();
    submitForm.setFieldsValue({ target_agent: agent.id, task_type: 'general' });
    setSubmitOpen(true);
  };

  const handleSubmitTaskOk = async () => {
    try {
      const values = await submitForm.validateFields();
      const result = await api.submitCliTask(
        values.target_agent,
        values.prompt,
        values.task_type,
        values.cwd || '',
      );
      message.success(`任务已提交: ${result.task_id}`);
      setSubmitOpen(false);
      loadTasks();
      setActiveTab('tasks');
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err.message || '提交失败');
    }
  };

  const handleTaskDetail = async (task: any) => {
    try {
      const detail = await api.getCliTask(task.id);
      setTaskDetail(detail);
      setDetailOpen(true);
    } catch (err: any) {
      message.error(err.message || '加载任务详情失败');
    }
  };

  const handleGateTransition = async (taskId: string, toStatus: string) => {
    try {
      const result = await api.transitionGate(taskId, toStatus);
      message.success(`Gate 状态已转换: ${result.from_status} → ${result.to_status}`);
      loadTasks();
      if (taskDetail?.id === taskId) {
        setTaskDetail({ ...taskDetail, gate_status: toStatus });
      }
    } catch (err: any) {
      message.error(err.message || '状态转换失败');
    }
  };

  // Agent columns
  const agentColumns = [
    {
      title: 'Agent',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <Space>
          <Badge status={record.status === 'online' ? 'success' : 'default'} />
          <Text strong>{text}</Text>
        </Space>
      ),
    },
    {
      title: '适配器模式',
      key: 'mode',
      render: (_: any, record: any) => {
        const mode = record.cliSpec?.mode || 'websocket';
        const mc = modeConfig[mode] || modeConfig.websocket;
        return <Tag color={mc.color} icon={mc.icon}>{mc.label}</Tag>;
      },
    },
    {
      title: 'CLI 命令',
      key: 'command',
      render: (_: any, record: any) => {
        const cmd = record.cliSpec?.command;
        if (!cmd || cmd.length === 0) return <Text type="secondary">-</Text>;
        return <Text code style={{ fontSize: 12 }}>{Array.isArray(cmd) ? cmd.join(' ') : cmd}</Text>;
      },
    },
    {
      title: '模型层级',
      key: 'tier',
      render: (_: any, record: any) => {
        const tier = record.cliSpec?.model_tier || 'standard';
        const tc = tierConfig[tier] || tierConfig.standard;
        return <Tag color={tc.color}>{tc.label}</Tag>;
      },
    },
    {
      title: '模型优势',
      key: 'strengths',
      render: (_: any, record: any) => {
        const strengths = record.cliSpec?.model_strengths || [];
        if (!strengths || strengths.length === 0) return <Text type="secondary">-</Text>;
        return (
          <Space size={4} wrap>
            {strengths.map((s: string) => <Tag key={s} color="geekblue" style={{ fontSize: 11 }}>{s}</Tag>)}
          </Space>
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button size="small" icon={<SettingOutlined />} onClick={() => handleConfigure(record)}>
            配置
          </Button>
          <Button size="small" type="primary" icon={<SendOutlined />} onClick={() => handleSubmitTask(record)}>
            提交任务
          </Button>
        </Space>
      ),
    },
  ];

  // Task columns
  const taskColumns = [
    {
      title: '任务 ID',
      dataIndex: 'id',
      key: 'id',
      width: 120,
      render: (text: string) => <Text code style={{ fontSize: 12 }}>{text}</Text>,
    },
    {
      title: '目标 Agent',
      dataIndex: 'target_agent',
      key: 'target_agent',
      render: (text: string) => <Text code style={{ fontSize: 12 }}>{text?.slice(0, 8)}</Text>,
    },
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 90,
      render: (text: string) => <Tag>{text}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const sc = statusConfig[status] || { color: 'default', label: status || '未知', icon: null };
        return <Tag color={sc.color} icon={sc.icon}>{sc.label}</Tag>;
      },
    },
    {
      title: 'Gate',
      dataIndex: 'gate_status',
      key: 'gate_status',
      width: 100,
      render: (gs: string) => {
        if (!gs) return <Text type="secondary">-</Text>;
        const gc = gateStatusConfig[gs] || { color: 'default', label: gs };
        return <Tag color={gc.color}>{gc.label}</Tag>;
      },
    },
    {
      title: '提示词',
      dataIndex: 'prompt',
      key: 'prompt',
      ellipsis: true,
      render: (text: string) => <Text style={{ fontSize: 12 }}>{text}</Text>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (text: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {text ? new Date(text).toLocaleString() : '-'}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: any, record: any) => (
        <Button size="small" onClick={() => handleTaskDetail(record)}>详情</Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>
            <CodeOutlined style={{ marginRight: 8 }} />
            CLI Agent 管理
          </Title>
          <Tag color="green">v1.4.0</Tag>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => { loadAgents(); loadTasks(); }}>
            刷新
          </Button>
        </Space>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="Agent 总数" value={agents.length} prefix={<ApiOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="CLI 模式"
              value={agents.filter(a => a.cliSpec?.mode === 'command').length}
              prefix={<CodeOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="排队任务"
              value={tasks.filter(t => t.status === 'queued').length}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="模型池"
              value={Object.keys(modelPool).length}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
      </Row>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
        {
          key: 'agents',
          label: <span><ApiOutlined /> Agent 列表</span>,
          children: (
            <Card>
              <Table
                columns={agentColumns}
                dataSource={agents}
                rowKey="id"
                loading={loading}
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: <Empty description="暂无 Agent" /> }}
              />
            </Card>
          ),
        },
        {
          key: 'tasks',
          label: <span><NodeIndexOutlined /> Pull Queue ({tasks.length})</span>,
          children: (
            <Card>
              <Table
                columns={taskColumns}
                dataSource={tasks}
                rowKey="id"
                loading={taskLoading}
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: <Empty description="暂无任务" /> }}
              />
            </Card>
          ),
        },
        {
          key: 'models',
          label: <span><ThunderboltOutlined /> 模型池</span>,
          children: (
            <Card>
              {Object.keys(modelPool).length === 0 ? (
                <Empty description="暂无模型池数据" />
              ) : (
                <Table
                  dataSource={Object.entries(modelPool).map(([name, info]: [string, any]) => ({
                    key: name, name, ...info,
                  }))}
                  columns={[
                    { title: '模型名称', dataIndex: 'name', key: 'name', render: (t: string) => <Text strong>{t}</Text> },
                    { title: '层级', dataIndex: 'tier', key: 'tier', render: (t: string) => {
                      const tc = tierConfig[t] || { color: 'default', label: t };
                      return <Tag color={tc.color}>{tc.label}</Tag>;
                    }},
                    { title: 'API 类型', dataIndex: 'api_type', key: 'api_type', render: (t: string) => <Tag>{t}</Tag> },
                    { title: '优势', dataIndex: 'strengths', key: 'strengths', render: (s: string[]) => (
                      <Space size={4} wrap>
                        {(s || []).map((st: string) => <Tag key={st} color="geekblue">{st}</Tag>)}
                      </Space>
                    )},
                  ]}
                  pagination={false}
                />
              )}
            </Card>
          ),
        },
      ]} />

      {/* Configure Agent Modal */}
      <Modal
        title={<Space><SettingOutlined /> 配置 CLI Agent: {selectedAgent?.name}</Space>}
        open={configureOpen}
        onOk={handleConfigureSubmit}
        onCancel={() => setConfigureOpen(false)}
        width={600}
        destroyOnClose
      >
        <Form form={configForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="mode" label="适配器模式" rules={[{ required: true }]}>
            <Select options={[
              { value: 'websocket', label: 'WebSocket (跨网络)' },
              { value: 'command', label: 'CLI 命令 (本地)' },
              { value: 'mock', label: 'Mock (测试)' },
            ]} />
          </Form.Item>
          <Form.Item name="command" label="CLI 命令"
            tooltip="支持占位符: {prompt}, {cwd}, {task_id}, {task_type}">
            <Input placeholder="node cli-agent.js --prompt {prompt}" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="cwd" label="工作目录">
                <Input placeholder="/path/to/workspace" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout" label="超时 (秒)">
                <InputNumber min={10} max={36000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="model_tier" label="模型层级" rules={[{ required: true }]}>
                <Select options={[
                  { value: 'budget', label: '经济型 (budget)' },
                  { value: 'standard', label: '标准型 (standard)' },
                  { value: 'premium', label: '高级型 (premium)' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="model_strengths" label="模型优势" tooltip="逗号分隔">
                <Input placeholder="code_review, debugging, architecture" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* Submit Task Modal */}
      <Modal
        title={<Space><SendOutlined /> 提交任务到: {selectedAgent?.name}</Space>}
        open={submitOpen}
        onOk={handleSubmitTaskOk}
        onCancel={() => setSubmitOpen(false)}
        width={600}
        destroyOnClose
      >
        <Form form={submitForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="target_agent" label="目标 Agent" hidden>
            <Input />
          </Form.Item>
          <Form.Item name="task_type" label="任务类型" rules={[{ required: true }]}>
            <Select options={[
              { value: 'general', label: '通用任务' },
              { value: 'code_review', label: '代码评审' },
              { value: 'refactor', label: '重构' },
              { value: 'debug', label: '调试' },
              { value: 'test', label: '测试' },
              { value: 'deploy', label: '部署' },
              { value: 'docs', label: '文档' },
              { value: 'security', label: '安全审计' },
            ]} />
          </Form.Item>
          <Form.Item name="prompt" label="任务提示词" rules={[{ required: true, min: 1 }]}>
            <TextArea rows={4} placeholder="描述需要 Agent 执行的任务..." />
          </Form.Item>
          <Form.Item name="cwd" label="工作目录">
            <Input placeholder="可选，留空使用默认目录" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Task Detail Modal */}
      <Modal
        title={<Space><NodeIndexOutlined /> 任务详情</Space>}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={700}
      >
        {taskDetail ? (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="任务 ID">{taskDetail.id}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusConfig[taskDetail.status]?.color}>
                {statusConfig[taskDetail.status]?.label || taskDetail.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="来源 Agent">{taskDetail.source_agent || '-'}</Descriptions.Item>
            <Descriptions.Item label="目标 Agent">{taskDetail.target_agent}</Descriptions.Item>
            <Descriptions.Item label="任务类型">{taskDetail.task_type}</Descriptions.Item>
            <Descriptions.Item label="Gate 状态">
              {taskDetail.gate_status ? (
                <Tag color={gateStatusConfig[taskDetail.gate_status]?.color}>
                  {gateStatusConfig[taskDetail.gate_status]?.label || taskDetail.gate_status}
                </Tag>
              ) : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间" span={2}>
              {taskDetail.created_at ? new Date(taskDetail.created_at).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="开始时间" span={2}>
              {taskDetail.started_at ? new Date(taskDetail.started_at).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="完成时间" span={2}>
              {taskDetail.finished_at ? new Date(taskDetail.finished_at).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="提示词" span={2}>
              <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 13, maxHeight: 120, overflow: 'auto' }}>
                {taskDetail.prompt}
              </Paragraph>
            </Descriptions.Item>
            {taskDetail.result && (
              <Descriptions.Item label="执行结果" span={2}>
                <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12, maxHeight: 200, overflow: 'auto' }}>
                  {taskDetail.result}
                </Paragraph>
              </Descriptions.Item>
            )}
            {taskDetail.error && (
              <Descriptions.Item label="错误信息" span={2}>
                <Text type="danger" style={{ fontSize: 12 }}>{taskDetail.error}</Text>
              </Descriptions.Item>
            )}
            {taskDetail.acceptance_status && (
              <Descriptions.Item label="验收状态">
                <Tag color={taskDetail.acceptance_status === 'accepted' ? 'success' : 'error'}>
                  {taskDetail.acceptance_status}
                </Tag>
              </Descriptions.Item>
            )}
            {taskDetail.acceptance_reason && (
              <Descriptions.Item label="验收原因">{taskDetail.acceptance_reason}</Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Empty description="加载中..." />
        )}

        {/* Gate 操作 */}
        {taskDetail && taskDetail.gate_status && (
          <Card title="Gate 状态机操作" size="small" style={{ marginTop: 16 }}>
            <Space wrap>
              {taskDetail.gate_status === 'primary_completed' && (
                <>
                  <Button size="small" type="primary" onClick={() => handleGateTransition(taskDetail.id, 'review_pending')}>
                    提交评审
                  </Button>
                  <Button size="small" onClick={() => handleGateTransition(taskDetail.id, 'accepted')}>
                    直接接受
                  </Button>
                </>
              )}
              {taskDetail.gate_status === 'review_pending' && (
                <Button size="small" type="primary" onClick={() => handleGateTransition(taskDetail.id, 'review_running')}>
                  开始评审
                </Button>
              )}
              {taskDetail.gate_status === 'review_running' && (
                <Space>
                  <Button size="small" type="primary" onClick={() => handleGateTransition(taskDetail.id, 'review_passed')}>
                    评审通过
                  </Button>
                  <Button size="small" danger onClick={() => handleGateTransition(taskDetail.id, 'review_attention')}>
                    需关注
                  </Button>
                </Space>
              )}
              {taskDetail.gate_status === 'review_passed' && (
                <Button size="small" type="primary" onClick={() => handleGateTransition(taskDetail.id, 'verification_pending')}>
                  提交验证
                </Button>
              )}
              {taskDetail.gate_status === 'verification_pending' && (
                <Button size="small" type="primary" onClick={() => handleGateTransition(taskDetail.id, 'verification_running')}>
                  开始验证
                </Button>
              )}
              {taskDetail.gate_status === 'verification_running' && (
                <Button size="small" type="primary" onClick={() => handleGateTransition(taskDetail.id, 'accepted')}>
                  接受
                </Button>
              )}
              {taskDetail.gate_status === 'review_attention' && (
                <Button size="small" danger onClick={() => handleGateTransition(taskDetail.id, 'failed')}>
                  标记失败
                </Button>
              )}
            </Space>
          </Card>
        )}
      </Modal>
    </div>
  );
};

export default CliAgents;