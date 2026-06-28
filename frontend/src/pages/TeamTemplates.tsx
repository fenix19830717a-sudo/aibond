import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Typography, message, Space, Button, Modal, Descriptions, Tag, Empty, Spin,
} from 'antd';
import {
  AppstoreOutlined, PlusOutlined, TeamOutlined, RobotOutlined, UserOutlined, CopyOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../store/authStore';
import { api } from '../api';

const { Title, Text, Paragraph } = Typography;

const templateTypeLabels: Record<string, { label: string; color: string }> = {
  'dev_team': { label: '开发团队', color: 'blue' },
  'review_team': { label: '审查团队', color: 'purple' },
  'support_team': { label: '支持团队', color: 'green' },
  'creative_team': { label: '创意团队', color: 'orange' },
  'ops_team': { label: '运维团队', color: 'red' },
  'general': { label: '通用', color: 'default' },
};

const TeamTemplates: React.FC = () => {
  const { user } = useAuthStore();
  const [templates, setTemplates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<any>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await api.listTemplates();
      setTemplates(Array.isArray(data) ? data : (data?.templates || data?.value || []));
    } catch (err: any) {
      console.warn('Templates not available:', err.message);
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetail = async (template: any) => {
    try {
      const detail = await api.getTemplate(template.id);
      setSelectedTemplate(detail);
    } catch {
      setSelectedTemplate(template);
    }
    setDetailModalOpen(true);
  };

  const handleCreateGroup = async () => {
    if (!selectedTemplate || !user) return;
    setCreating(true);
    try {
      const result = await api.createGroupFromTemplate(selectedTemplate.id, user.id);
      message.success(`群组已创建: ${result?.name || '成功'}`);
      setDetailModalOpen(false);
      setSelectedTemplate(null);
    } catch (err: any) {
      message.error(err.message || '创建失败');
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}><AppstoreOutlined style={{ marginRight: 8 }} />团队模板</Title>
        <Button icon={<PlusOutlined />}>创建模板</Button>
      </div>

      {templates.length === 0 ? (
        <Card>
          <Empty description="暂无团队模板">
            <Button onClick={loadTemplates}>刷新</Button>
          </Empty>
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {templates.map((tpl) => {
            const typeInfo = templateTypeLabels[tpl.type] || templateTypeLabels.general;
            return (
              <Col xs={24} sm={12} md={8} lg={6} key={tpl.id}>
                <Card
                  hoverable
                  style={{ height: '100%' }}
                  onClick={() => handleViewDetail(tpl)}
                >
                  <Space direction="vertical" style={{ width: '100%' }} size={8}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <Text strong style={{ fontSize: 16 }}>{tpl.name}</Text>
                      <Tag color={typeInfo.color}>{typeInfo.label}</Tag>
                    </div>
                    <Paragraph type="secondary" ellipsis={{ rows: 3 }} style={{ marginBottom: 0, fontSize: 13 }}>
                      {tpl.description || '暂无描述'}
                    </Paragraph>
                    {tpl.config && (
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {tpl.config.agents?.map((agent: any, idx: number) => (
                          <Tag key={idx} icon={<RobotOutlined />} color="blue">{typeof agent === 'string' ? agent : agent.name || 'Agent'}</Tag>
                        ))}
                        {tpl.config.members?.map((member: any, idx: number) => (
                          <Tag key={idx} icon={<UserOutlined />} color="green">{typeof member === 'string' ? member : member.name || '成员'}</Tag>
                        ))}
                      </div>
                    )}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {tpl.agent_count || tpl.config?.agents?.length || 0} 个 Agent,
                      {' '}{tpl.member_count || tpl.config?.members?.length || 0} 个成员
                    </Text>
                  </Space>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}

      <Modal
        title={
          <Space>
            <TeamOutlined />
            <span>{selectedTemplate?.name || '模板详情'}</span>
          </Space>
        }
        open={detailModalOpen}
        onCancel={() => { setDetailModalOpen(false); setSelectedTemplate(null); }}
        footer={[
          <Button key="cancel" onClick={() => { setDetailModalOpen(false); setSelectedTemplate(null); }}>关闭</Button>,
          <Button key="create" type="primary" loading={creating} onClick={handleCreateGroup}>
            <TeamOutlined /> 基于此模板创建群组
          </Button>,
        ]}
        width={600}
      >
        {selectedTemplate && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="模板名称">{selectedTemplate.name}</Descriptions.Item>
              <Descriptions.Item label="描述">{selectedTemplate.description || '暂无描述'}</Descriptions.Item>
              <Descriptions.Item label="类型">
                <Tag color={templateTypeLabels[selectedTemplate.type]?.color || 'default'}>
                  {templateTypeLabels[selectedTemplate.type]?.label || selectedTemplate.type}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            {selectedTemplate.config && (
              <div>
                <Text strong>模板配置:</Text>
                {selectedTemplate.config.agents?.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">预设 Agent:</Text>
                    <div style={{ marginTop: 4 }}>
                      {(selectedTemplate.config.agents || []).map((agent: any, idx: number) => (
                        <Tag key={idx} icon={<RobotOutlined />} color="blue" style={{ marginBottom: 4 }}>
                          {typeof agent === 'string' ? agent : agent.name || agent.role || 'Agent'}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
                {selectedTemplate.config.members?.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">预设成员:</Text>
                    <div style={{ marginTop: 4 }}>
                      {(selectedTemplate.config.members || []).map((member: any, idx: number) => (
                        <Tag key={idx} icon={<UserOutlined />} color="green" style={{ marginBottom: 4 }}>
                          {typeof member === 'string' ? member : member.name || '成员'}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
                {selectedTemplate.config.workflows?.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">预设工作流:</Text>
                    <div style={{ marginTop: 4 }}>
                      {(selectedTemplate.config.workflows || []).map((wf: any, idx: number) => (
                        <Tag key={idx} icon={<CopyOutlined />} style={{ marginBottom: 4 }}>
                          {typeof wf === 'string' ? wf : wf.name || '工作流'}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
                {selectedTemplate.config.description && (
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">说明:</Text>
                    <Paragraph style={{ marginTop: 4 }}>{selectedTemplate.config.description}</Paragraph>
                  </div>
                )}
              </div>
            )}
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default TeamTemplates;
