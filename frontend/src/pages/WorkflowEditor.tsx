import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button, Space, Typography, message, Card, Select, Input, InputNumber, Tag, Drawer, Divider, Empty, Tooltip, Segmented, Badge,
} from 'antd';
import {
  SaveOutlined,
  PlayCircleOutlined,
  ArrowLeftOutlined,
  PlusOutlined,
  RobotOutlined,
  UserOutlined,
  BranchesOutlined,
  ThunderboltOutlined,
  SendOutlined,
  SettingOutlined,
  ApartmentOutlined,
  ApiOutlined,
  EyeOutlined,
  AppstoreOutlined,
  PartitionOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import ReactFlow, {
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  Controls,
  Background,
  type Node,
  type Edge,
  type Connection,
  type NodeChange,
  type EdgeChange,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';

const { Title, Text } = Typography;
const { TextArea } = Input;

const nodeTypesConfig: Record<string, { label: string; icon: React.ReactNode; color: string; description: string }> = {
  trigger: { label: '触发节点', icon: <ThunderboltOutlined />, color: '#faad14', description: '工作流的起始触发点' },
  ai: { label: 'AI 执行', icon: <RobotOutlined />, color: '#52c41a', description: '由 AI Agent 执行任务' },
  human: { label: '人工审核', icon: <UserOutlined />, color: '#1677ff', description: '需要人工介入审核' },
  condition: { label: '条件分支', icon: <BranchesOutlined />, color: '#722ed1', description: '根据条件选择分支' },
  output: { label: '输出节点', icon: <SendOutlined />, color: '#eb2f96', description: '输出结果到指定目标' },
  parallel: { label: '并行执行', icon: <ApartmentOutlined />, color: '#9c27b0', description: '并行执行多个子任务' },
  webhook: { label: '外部调用', icon: <ApiOutlined />, color: '#00bcd4', description: '通过 Webhook 调用外部服务' },
  event_watcher: { label: '事件监控', icon: <EyeOutlined />, color: '#ff9800', description: '监听系统事件并触发响应' },
};

const defaultNodes: Node[] = [
  {
    id: '1',
    type: 'default',
    position: { x: 250, y: 50 },
    data: { label: '开始', nodeType: 'trigger', config: {} },
    style: { background: '#faad14', color: '#fff', padding: '10px 20px', borderRadius: 8, fontSize: 14 },
  },
];

const defaultEdges: Edge[] = [];

interface KanbanTask {
  id: string;
  nodeId: string;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  agent?: string;
}

const kanbanColumns = [
  { key: 'pending', title: '待分配', icon: <ClockCircleOutlined />, color: '#faad14' },
  { key: 'running', title: '执行中', icon: <SyncOutlined spin />, color: '#1677ff' },
  { key: 'completed', title: '已完成', icon: <CheckCircleOutlined />, color: '#52c41a' },
  { key: 'failed', title: '失败', icon: <CloseCircleOutlined />, color: '#ff4d4f' },
];

const WorkflowEditor: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [nodes, setNodes] = useState<Node[]>(defaultNodes);
  const [edges, setEdges] = useState<Edge[]>(defaultEdges);
  const [workflow, setWorkflow] = useState<any>(null);
  const [addingNode, setAddingNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [availableAgents, setAvailableAgents] = useState<any[]>([]);
  const [viewMode, setViewMode] = useState<'flow' | 'kanban'>('flow');
  const [triggerType, setTriggerType] = useState<string>('manual');
  const [kanbanTasks, setKanbanTasks] = useState<KanbanTask[]>([]);

  useEffect(() => {
    if (id) loadWorkflow();
    loadAgents();
  }, [id]);

  const loadWorkflow = async () => {
    try {
      const { api } = await import('../api');
      const data = await api.getWorkflow(id!);
      setWorkflow(data);
      if (data.definition?.nodes?.length > 0) {
        setNodes(data.definition.nodes);
        setEdges(data.definition.edges || []);
      }
      if (data.trigger_type) {
        setTriggerType(data.trigger_type);
      }
      // Build kanban tasks from nodes
      if (data.definition?.nodes) {
        const tasks: KanbanTask[] = data.definition.nodes.map((n: Node) => ({
          id: `${n.id}-task`,
          nodeId: n.id,
          title: n.data?.label || '未命名节点',
          status: 'pending' as const,
          agent: n.data?.config?.agent_id || undefined,
        }));
        setKanbanTasks(tasks);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadAgents = async () => {
    try {
      const { api } = await import('../api');
      const data = await api.listAvailableAgents();
      setAvailableAgents(data);
    } catch (err) {
      console.error(err);
    }
  };

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge({ ...connection, markerEnd: { type: MarkerType.ArrowClosed } }, eds));
  }, []);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
    setDrawerOpen(true);
  }, []);

  const handleAddNode = (type: string) => {
    const config = nodeTypesConfig[type];
    if (!config) return;
    const newNode: Node = {
      id: `${Date.now()}`,
      type: 'default',
      position: { x: 250 + Math.random() * 200, y: 100 + nodes.length * 120 },
      data: {
        label: config.label,
        nodeType: type,
        config: type === 'ai' ? { agent_id: '', task_description: '', timeout: 60 }
          : type === 'parallel' ? { sub_tasks: [], max_concurrency: 3 }
          : type === 'webhook' ? { url: '', method: 'POST', headers: '{}' }
          : type === 'event_watcher' ? { event_type: '', filter_condition: '' }
          : {},
      },
      style: { background: config.color, color: '#fff', padding: '10px 20px', borderRadius: 8, fontSize: 14, minWidth: 120 },
    };
    setNodes((nds) => [...nds, newNode]);
    // Also add to kanban
    setKanbanTasks((prev) => [...prev, {
      id: `${newNode.id}-task`,
      nodeId: newNode.id,
      title: config.label,
      status: 'pending',
      agent: type === 'ai' ? undefined : undefined,
    }]);
    setAddingNode(null);
  };

  const updateNodeConfig = (key: string, value: any) => {
    if (!selectedNode) return;
    const updatedData = {
      ...selectedNode.data,
      config: { ...selectedNode.data.config, [key]: value },
    };
    if (key === 'agent_id') {
      const agent = availableAgents.find((a: any) => a.id === value);
      if (agent) {
        updatedData.label = agent.name;
      }
    }
    const updatedNode = { ...selectedNode, data: updatedData };
    setSelectedNode(updatedNode);
    setNodes((nds) => nds.map((n) => (n.id === updatedNode.id ? updatedNode : n)));
  };

  const handleSave = async () => {
    try {
      const { api } = await import('../api');
      await api.updateWorkflowDefinition(id!, { nodes, edges, trigger_type: triggerType });
      message.success('工作流已保存');
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const handleRun = async () => {
    try {
      const { api } = await import('../api');
      const data = await api.runWorkflow(id!);
      if (data.first_ai_agent) {
        message.success('工作流已启动，AI 执行者已指定');
      } else {
        message.success(`工作流已启动，实例ID: ${data.instance_id}`);
      }
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const handleKanbanStatusChange = (taskId: string, newStatus: KanbanTask['status']) => {
    setKanbanTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t))
    );
  };

  const selectedNodeType = selectedNode?.data?.nodeType;
  const selectedConfig = selectedNode?.data?.config || {};

  // Render config drawer content based on node type
  const renderNodeConfig = () => {
    if (!selectedNode) return null;
    return (
      <>
        {/* AI 节点 */}
        {selectedNodeType === 'ai' && (
          <>
            <Divider style={{ margin: '8px 0' }}>AI 执行者</Divider>
            {availableAgents.length > 0 ? (
              <Select
                style={{ width: '100%' }}
                placeholder="选择执行此任务的 Agent"
                value={selectedConfig.agent_id || undefined}
                onChange={(val) => updateNodeConfig('agent_id', val)}
                showSearch
                options={availableAgents.map((a: any) => ({
                  value: a.id,
                  label: `${a.name} (${a.status})`,
                }))}
              />
            ) : (
              <Empty description="暂无可用 Agent，请先注册 Agent" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
            {selectedConfig.agent_id && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>Agent Skills：</Text>
                <div style={{ marginTop: 4 }}>
                  {availableAgents
                    .filter((a) => a.id === selectedConfig.agent_id)
                    .flatMap((a) => a.skills || [])
                    .map((skill: string) => (
                      <Tag key={skill} color="blue" style={{ marginBottom: 2 }}>{skill}</Tag>
                    ))}
                  {availableAgents.filter((a) => a.id === selectedConfig.agent_id).flatMap((a) => a.skills || []).length === 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>暂无 Skills</Text>
                  )}
                </div>
              </div>
            )}
            <Divider style={{ margin: '8px 0' }}>任务描述</Divider>
            <TextArea
              value={selectedConfig.task_description || ''}
              onChange={(e) => updateNodeConfig('task_description', e.target.value)}
              placeholder="描述这个 AI 节点需要执行的任务..."
              rows={3}
            />
            <Divider style={{ margin: '8px 0' }}>超时设置</Divider>
            <InputNumber
              style={{ width: '100%' }}
              min={5}
              max={3600}
              value={selectedConfig.timeout || 60}
              onChange={(val) => updateNodeConfig('timeout', val)}
              addonAfter="秒"
            />
          </>
        )}

        {/* 人工审核节点 */}
        {selectedNodeType === 'human' && (
          <>
            <Divider style={{ margin: '8px 0' }}>审核说明</Divider>
            <TextArea
              value={selectedConfig.review_instruction || ''}
              onChange={(e) => updateNodeConfig('review_instruction', e.target.value)}
              placeholder="描述审核标准和要求..."
              rows={3}
            />
          </>
        )}

        {/* 触发节点 */}
        {selectedNodeType === 'trigger' && (
          <>
            <Divider style={{ margin: '8px 0' }}>触发方式</Divider>
            <Select
              style={{ width: '100%' }}
              value={selectedConfig.trigger_type || 'manual'}
              onChange={(val) => updateNodeConfig('trigger_type', val)}
              options={[
                { value: 'manual', label: '手动触发' },
                { value: 'message', label: '消息触发' },
                { value: 'schedule', label: '定时触发' },
                { value: 'webhook', label: 'Webhook 触发' },
                { value: 'event', label: '事件触发' },
              ]}
            />
          </>
        )}

        {/* 输出节点 */}
        {selectedNodeType === 'output' && (
          <>
            <Divider style={{ margin: '8px 0' }}>输出目标</Divider>
            <Select
              style={{ width: '100%' }}
              value={selectedConfig.output_target || 'group'}
              onChange={(val) => updateNodeConfig('output_target', val)}
              options={[
                { value: 'group', label: '发送到群组' },
                { value: 'log', label: '记录日志' },
                { value: 'webhook', label: 'Webhook 回调' },
              ]}
            />
          </>
        )}

        {/* 并行节点 */}
        {selectedNodeType === 'parallel' && (
          <>
            <Divider style={{ margin: '8px 0' }}>并行配置</Divider>
            <div style={{ marginBottom: 12 }}>
              <Text strong style={{ display: 'block', marginBottom: 4 }}>最大并发数</Text>
              <InputNumber
                style={{ width: '100%' }}
                min={1}
                max={20}
                value={selectedConfig.max_concurrency || 3}
                onChange={(val) => updateNodeConfig('max_concurrency', val)}
                addonAfter="个"
              />
            </div>
            <Divider style={{ margin: '8px 0' }}>子任务描述</Divider>
            <TextArea
              value={selectedConfig.sub_tasks_description || ''}
              onChange={(e) => updateNodeConfig('sub_tasks_description', e.target.value)}
              placeholder="描述需要并行执行的子任务列表..."
              rows={3}
            />
          </>
        )}

        {/* Webhook 节点 */}
        {selectedNodeType === 'webhook' && (
          <>
            <Divider style={{ margin: '8px 0' }}>Webhook 配置</Divider>
            <div style={{ marginBottom: 12 }}>
              <Text strong style={{ display: 'block', marginBottom: 4 }}>请求 URL</Text>
              <Input
                value={selectedConfig.url || ''}
                onChange={(e) => updateNodeConfig('url', e.target.value)}
                placeholder="https://example.com/webhook"
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <Text strong style={{ display: 'block', marginBottom: 4 }}>请求方法</Text>
              <Select
                style={{ width: '100%' }}
                value={selectedConfig.method || 'POST'}
                onChange={(val) => updateNodeConfig('method', val)}
                options={[
                  { value: 'GET', label: 'GET' },
                  { value: 'POST', label: 'POST' },
                  { value: 'PUT', label: 'PUT' },
                  { value: 'DELETE', label: 'DELETE' },
                ]}
              />
            </div>
            <Divider style={{ margin: '8px 0' }}>请求头 (JSON)</Divider>
            <TextArea
              value={selectedConfig.headers || '{}'}
              onChange={(e) => updateNodeConfig('headers', e.target.value)}
              placeholder='{"Content-Type": "application/json"}'
              rows={2}
            />
          </>
        )}

        {/* 事件监控节点 */}
        {selectedNodeType === 'event_watcher' && (
          <>
            <Divider style={{ margin: '8px 0' }}>事件监控配置</Divider>
            <div style={{ marginBottom: 12 }}>
              <Text strong style={{ display: 'block', marginBottom: 4 }}>事件类型</Text>
              <Select
                style={{ width: '100%' }}
                value={selectedConfig.event_type || 'system'}
                onChange={(val) => updateNodeConfig('event_type', val)}
                options={[
                  { value: 'system', label: '系统事件' },
                  { value: 'message', label: '消息事件' },
                  { value: 'status_change', label: '状态变更' },
                  { value: 'error', label: '错误事件' },
                  { value: 'custom', label: '自定义事件' },
                ]}
              />
            </div>
            <Divider style={{ margin: '8px 0' }}>过滤条件</Divider>
            <TextArea
              value={selectedConfig.filter_condition || ''}
              onChange={(e) => updateNodeConfig('filter_condition', e.target.value)}
              placeholder={'JSON 格式的过滤条件，如 {"level": "error"}'}
              rows={3}
            />
          </>
        )}
      </>
    );
  };

  // Kanban view
  const renderKanbanView = () => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, height: '100%', padding: 8 }}>
      {kanbanColumns.map((col) => {
        const colTasks = kanbanTasks.filter((t) => t.status === col.key);
        return (
          <div
            key={col.key}
            style={{
              background: 'rgba(255,255,255,0.04)',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.08)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <Space>
                <span style={{ color: col.color }}>{col.icon}</span>
                <Text strong style={{ color: col.color }}>{col.title}</Text>
              </Space>
              <Badge count={colTasks.length} overflowCount={99} style={{ backgroundColor: col.color }} />
            </div>
            <div style={{ flex: 1, padding: 8, overflowY: 'auto' }}>
              {colTasks.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 24, color: 'rgba(255,255,255,0.25)' }}>
                  <Text type="secondary">暂无任务</Text>
                </div>
              ) : (
                colTasks.map((task) => (
                  <Card
                    key={task.id}
                    size="small"
                    style={{
                      marginBottom: 8,
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      cursor: 'pointer',
                    }}
                    onClick={() => {
                      const node = nodes.find((n) => n.id === task.nodeId);
                      if (node) {
                        setSelectedNode(node);
                        setDrawerOpen(true);
                      }
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <Text strong style={{ fontSize: 13 }}>{task.title}</Text>
                      {task.agent && (
                        <Tag color="blue" style={{ fontSize: 11 }}>{task.agent}</Tag>
                      )}
                      <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                        {kanbanColumns
                          .filter((c) => c.key !== task.status)
                          .map((c) => (
                            <Tooltip key={c.key} title={`移至${c.title}`}>
                              <Button
                                size="small"
                                type="text"
                                style={{ fontSize: 11, padding: '0 4px' }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleKanbanStatusChange(task.id, c.key as KanbanTask['status']);
                                }}
                              >
                                {c.icon}
                              </Button>
                            </Tooltip>
                          ))}
                      </div>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div style={{ height: 'calc(100vh - 160px)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/workflows')}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>{workflow?.name || '工作流编辑器'}</Title>
        </Space>
        <Space>
          {/* Trigger type selector */}
          <Select
            value={triggerType}
            onChange={setTriggerType}
            style={{ width: 120 }}
            options={[
              { value: 'manual', label: '手动触发' },
              { value: 'message', label: '消息触发' },
              { value: 'schedule', label: '定时触发' },
              { value: 'webhook', label: 'Webhook' },
              { value: 'event', label: '事件触发' },
            ]}
          />
          {/* View mode toggle */}
          <Segmented
            value={viewMode}
            onChange={(val) => setViewMode(val as 'flow' | 'kanban')}
            options={[
              { value: 'flow', icon: <PartitionOutlined />, label: '流程图' },
              { value: 'kanban', icon: <AppstoreOutlined />, label: 'Kanban' },
            ]}
          />
          {viewMode === 'flow' && (
            <div style={{ position: 'relative' }}>
              <Button icon={<PlusOutlined />} onClick={() => setAddingNode(addingNode ? null : 'menu')}>添加节点</Button>
              {addingNode && (
                <Card style={{ position: 'absolute', top: '100%', right: 0, zIndex: 100, width: 220, marginTop: 4 }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {Object.entries(nodeTypesConfig).map(([type, config]) => (
                      <Tooltip key={type} title={config.description} placement="left">
                        <Button
                          block
                          style={{ textAlign: 'left', borderColor: config.color }}
                          onClick={() => handleAddNode(type)}
                        >
                          <Space>
                            <span style={{ color: config.color }}>{config.icon}</span>
                            <span>{config.label}</span>
                          </Space>
                        </Button>
                      </Tooltip>
                    ))}
                  </Space>
                </Card>
              )}
            </div>
          )}
          <Button icon={<SaveOutlined />} onClick={handleSave}>保存</Button>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRun}>运行</Button>
        </Space>
      </div>

      <div style={{ height: 'calc(100% - 50px)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8 }}>
        {viewMode === 'flow' ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            fitView
          >
            <Controls />
            <Background />
          </ReactFlow>
        ) : (
          renderKanbanView()
        )}
      </div>

      {/* 节点配置抽屉 */}
      <Drawer
        title={
          <Space>
            <SettingOutlined />
            <span>节点配置</span>
            {selectedNode && (
              <Tag color={nodeTypesConfig[selectedNodeType as keyof typeof nodeTypesConfig]?.color}>
                {nodeTypesConfig[selectedNodeType as keyof typeof nodeTypesConfig]?.label}
              </Tag>
            )}
          </Space>
        }
        placement="right"
        width={360}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {selectedNode ? (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text strong>节点 ID：</Text>
              <Text code>{selectedNode.id}</Text>
            </div>
            <Divider style={{ margin: '8px 0' }}>节点名称</Divider>
            <Input
              value={selectedNode.data?.label || ''}
              onChange={(e) => {
                const updatedNode = { ...selectedNode, data: { ...selectedNode.data, label: e.target.value } };
                setSelectedNode(updatedNode);
                setNodes((nds) => nds.map((n) => (n.id === updatedNode.id ? updatedNode : n)));
              }}
              placeholder="节点名称"
            />
            {renderNodeConfig()}
          </Space>
        ) : (
          <Empty description="点击画布中的节点进行配置" />
        )}
      </Drawer>
    </div>
  );
};

export default WorkflowEditor;