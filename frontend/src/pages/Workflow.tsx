import React, { useState, useEffect } from 'react';
import { Card, Button, Modal, Form, Input, List, Tag, Typography, message, Space, Row, Col, Spin } from 'antd';
import {
  PlusOutlined,
  ApartmentOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  AlertOutlined,
  ThunderboltOutlined,
  TeamOutlined,
  SyncOutlined,
  ApiOutlined,
  RobotOutlined,
  EyeOutlined,
  BranchesOutlined,
  ExperimentOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { api } from '../api';

const { Title, Text, Paragraph } = Typography;

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  definition: any;
}

const templateIcons: Record<string, React.ReactNode> = {
  clock: <ClockCircleOutlined />,
  alert: <AlertOutlined />,
  thunderbolt: <ThunderboltOutlined />,
  team: <TeamOutlined />,
  sync: <SyncOutlined />,
  api: <ApiOutlined />,
  robot: <RobotOutlined />,
  eye: <EyeOutlined />,
  branches: <BranchesOutlined />,
  experiment: <ExperimentOutlined />,
  safety: <SafetyCertificateOutlined />,
  file: <FileTextOutlined />,
};

const categoryColorMap: Record<string, string> = {
  '定时任务': 'blue',
  '智能监控': 'orange',
  '任务执行': 'green',
  '多Agent协作': 'purple',
  '持续进化': 'cyan',
};

const presetTemplates: WorkflowTemplate[] = [
  {
    id: 'template-1',
    name: '每日报告生成',
    description: '在每天指定时间自动收集数据并生成报告',
    icon: 'clock',
    category: '定时任务',
    definition: { nodes: [], edges: [], trigger_type: 'schedule' },
  },
  {
    id: 'template-2',
    name: '异常监控告警',
    description: '实时监控系统指标，发现异常立即告警通知',
    icon: 'alert',
    category: '智能监控',
    definition: { nodes: [], edges: [], trigger_type: 'event' },
  },
  {
    id: 'template-3',
    name: '自动化部署流水线',
    description: '代码提交后自动触发构建、测试、部署流程',
    icon: 'thunderbolt',
    category: '任务执行',
    definition: { nodes: [], edges: [], trigger_type: 'webhook' },
  },
  {
    id: 'template-4',
    name: '多Agent协作评审',
    description: '多个AI Agent并行评审文档，汇总评审意见',
    icon: 'team',
    category: '多Agent协作',
    definition: { nodes: [], edges: [], trigger_type: 'manual' },
  },
  {
    id: 'template-5',
    name: '数据同步任务',
    description: '定时从外部系统同步数据到本地数据库',
    icon: 'sync',
    category: '定时任务',
    definition: { nodes: [], edges: [], trigger_type: 'schedule' },
  },
  {
    id: 'template-6',
    name: 'Webhook事件处理',
    description: '接收外部Webhook回调，触发自动化处理流程',
    icon: 'api',
    category: '任务执行',
    definition: { nodes: [], edges: [], trigger_type: 'webhook' },
  },
  {
    id: 'template-7',
    name: '智能客服工作流',
    description: 'AI Agent自动响应用户问题，复杂问题升级人工',
    icon: 'robot',
    category: '多Agent协作',
    definition: { nodes: [], edges: [], trigger_type: 'message' },
  },
  {
    id: 'template-8',
    name: '事件监控与响应',
    description: '监听系统事件，根据事件类型执行不同响应策略',
    icon: 'eye',
    category: '智能监控',
    definition: { nodes: [], edges: [], trigger_type: 'event' },
  },
  {
    id: 'template-9',
    name: '条件分支决策',
    description: '根据输入条件自动选择不同的执行分支',
    icon: 'branches',
    category: '任务执行',
    definition: { nodes: [], edges: [], trigger_type: 'manual' },
  },
  {
    id: 'template-10',
    name: '持续学习进化',
    description: '记录执行结果，持续优化Agent的决策模型',
    icon: 'experiment',
    category: '持续进化',
    definition: { nodes: [], edges: [], trigger_type: 'schedule' },
  },
  {
    id: 'template-11',
    name: '安全审计流程',
    description: '定期执行安全审计，检查系统配置合规性',
    icon: 'safety',
    category: '智能监控',
    definition: { nodes: [], edges: [], trigger_type: 'schedule' },
  },
  {
    id: 'template-12',
    name: '批量数据处理',
    description: '大规模数据批量处理，支持并行执行和结果汇总',
    icon: 'file',
    category: '任务执行',
    definition: { nodes: [], edges: [], trigger_type: 'manual' },
  },
];

const Workflow: React.FC = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    loadWorkflows();
  }, []);

  const loadWorkflows = async () => {
    try {
      const data = await api.listWorkflows();
      setWorkflows(data);
    } catch (err) {
      console.error(err);
    }
  };

  const loadTemplates = async () => {
    setTemplatesLoading(true);
    try {
      const data = await api.getWorkflowTemplates();
      if (Array.isArray(data) && data.length > 0) {
        setTemplates(data);
      } else {
        // Fallback to preset templates when API returns empty
        setTemplates(presetTemplates);
      }
    } catch {
      // Fallback to preset templates on API error
      setTemplates(presetTemplates);
    } finally {
      setTemplatesLoading(false);
    }
  };

  const handleCreate = async (values: any) => {
    try {
      await api.createWorkflow(values.name, values.description || '', user!.id, { nodes: [], edges: [] }, values.trigger_type || 'manual');
      message.success('工作流创建成功');
      setModalOpen(false);
      form.resetFields();
      loadWorkflows();
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const handleOpenTemplateModal = () => {
    setTemplateModalOpen(true);
    loadTemplates();
  };

  const handleCreateFromTemplate = async (template: WorkflowTemplate) => {
    if (!user?.id) {
      message.error('请先登录');
      return;
    }
    try {
      const result = await api.createWorkflowFromTemplate({
        template_id: template.id,
        name: template.name,
        owner_id: user.id,
      });
      message.success('从模板创建成功');
      setTemplateModalOpen(false);
      const workflowId = result.id || result.workflow_id;
      if (workflowId) {
        navigate(`/workflows/${workflowId}`);
      } else {
        loadWorkflows();
      }
    } catch {
      // Fallback: create workflow with template definition directly
      try {
        await api.createWorkflow(
          template.name,
          template.description,
          user.id,
          template.definition,
          template.definition?.trigger_type || 'manual',
        );
        message.success('从模板创建成功');
        setTemplateModalOpen(false);
        loadWorkflows();
      } catch (err: any) {
        message.error(err.message || '创建失败');
      }
    }
  };

  const triggerLabels: Record<string, string> = {
    manual: '手动触发',
    message: '消息触发',
    schedule: '定时触发',
    webhook: 'Webhook触发',
    event: '事件触发',
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>工作流管理</Title>
        <Space>
          <Button icon={<FileTextOutlined />} onClick={handleOpenTemplateModal}>从模板创建</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>创建工作流</Button>
        </Space>
      </div>
      <List
        grid={{ gutter: 16, xs: 1, sm: 2, md: 3 }}
        dataSource={workflows}
        renderItem={(wf: any) => (
          <List.Item>
            <Card
              title={
                <Space>
                  <ApartmentOutlined />
                  <span>{wf.name}</span>
                </Space>
              }
              extra={
                <Space>
                  <Tag>{triggerLabels[wf.trigger_type] || wf.trigger_type}</Tag>
                  <Button type="link" icon={<PlayCircleOutlined />} onClick={() => navigate(`/workflows/${wf.id}`)}>编辑</Button>
                </Space>
              }
              style={{ cursor: 'pointer', height: '100%' }}
              onClick={() => navigate(`/workflows/${wf.id}`)}
            >
              <Text type="secondary">{wf.description || '暂无描述'}</Text>
              <div style={{ marginTop: 12 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>创建时间: {wf.created_at?.split('T')[0]}</Text>
              </div>
            </Card>
          </List.Item>
        )}
        locale={{ emptyText: '暂无工作流' }}
      />

      {/* 创建工作流 Modal */}
      <Modal title="创建工作流" open={modalOpen} onCancel={() => setModalOpen(false)} footer={null}>
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label="工作流名称" rules={[{ required: true }]}>
            <Input placeholder="输入工作流名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="输入工作流描述" rows={3} />
          </Form.Item>
          <Form.Item name="trigger_type" label="触发方式" initialValue="manual">
            <select style={{ width: '100%', padding: '4px 11px', borderRadius: 6, background: '#141414', color: '#fff', border: '1px solid #424242' }}>
              <option value="manual">手动触发</option>
              <option value="message">消息触发</option>
              <option value="schedule">定时触发</option>
              <option value="webhook">Webhook 触发</option>
              <option value="event">事件触发</option>
            </select>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>创建</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 从模板创建 Modal */}
      <Modal
        title={
          <Space>
            <FileTextOutlined />
            <span>从模板创建工作流</span>
          </Space>
        }
        open={templateModalOpen}
        onCancel={() => setTemplateModalOpen(false)}
        footer={null}
        width={900}
      >
        {templatesLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
          </div>
        ) : (
          <Row gutter={[16, 16]}>
            {templates.map((template) => {
              const iconNode = templateIcons[template.icon] || <FileTextOutlined />;
              const categoryColor = categoryColorMap[template.category] || 'default';
              return (
                <Col xs={24} sm={12} md={8} key={template.id}>
                  <Card
                    hoverable
                    style={{ height: '100%', cursor: 'pointer' }}
                    onClick={() => handleCreateFromTemplate(template)}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 28, color: '#1677ff' }}>{iconNode}</span>
                        <Tag color={categoryColor}>{template.category}</Tag>
                      </div>
                      <Text strong style={{ fontSize: 15 }}>{template.name}</Text>
                      <Paragraph
                        type="secondary"
                        style={{ fontSize: 12, margin: 0 }}
                        ellipsis={{ rows: 2 }}
                      >
                        {template.description}
                      </Paragraph>
                    </div>
                  </Card>
                </Col>
              );
            })}
          </Row>
        )}
      </Modal>
    </div>
  );
};

export default Workflow;