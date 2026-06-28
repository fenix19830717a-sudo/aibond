import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Button, Tag, Typography, message, Space, Descriptions, List, Progress, Steps, Modal, Form, Input, Select, InputNumber, Spin, Empty, Avatar, Alert,
} from 'antd';
import {
  ArrowLeftOutlined, BankOutlined, SendOutlined, CheckCircleOutlined,
  MinusCircleOutlined, RobotOutlined, UserOutlined, PlayCircleOutlined, PlusOutlined,
  ExclamationCircleOutlined, TrophyOutlined, LikeOutlined, DislikeOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Title, Text } = Typography;

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

const voteColorMap: Record<string, string> = {
  favor: '#52c41a',
  against: '#ff4d4f',
  abstain: '#faad14',
};

const voteIconMap: Record<string, React.ReactNode> = {
  favor: <LikeOutlined />,
  against: <DislikeOutlined />,
  abstain: <MinusCircleOutlined />,
};

const ParliamentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [parliament, setParliament] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  // Modals
  const [proposalModalOpen, setProposalModalOpen] = useState(false);
  const [voteModalOpen, setVoteModalOpen] = useState(false);
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [proposalForm] = Form.useForm();
  const [voteForm] = Form.useForm();
  const [resolveForm] = Form.useForm();

  useEffect(() => {
    if (id) {
      loadParliament();
    }
  }, [id]);

  const loadParliament = async () => {
    setLoading(true);
    try {
      const data = await api.getParliament(id!);
      setParliament(data);
    } catch (err: any) {
      message.error(err.message || '加载议会详情失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action: string, fn: () => Promise<any>) => {
    setActionLoading((prev) => ({ ...prev, [action]: true }));
    try {
      await fn();
      message.success('操作成功');
      loadParliament();
    } catch (err: any) {
      message.error(err.message || '操作失败');
    } finally {
      setActionLoading((prev) => ({ ...prev, [action]: false }));
    }
  };

  const handleSubmitProposal = async (values: any) => {
    setActionLoading((prev) => ({ ...prev, submitProposal: true }));
    try {
      await api.submitProposal(id!, values.proposer_id, values.content, values.confidence);
      message.success('提案已提交');
      setProposalModalOpen(false);
      proposalForm.resetFields();
      loadParliament();
    } catch (err: any) {
      message.error(err.message || '提交失败');
    } finally {
      setActionLoading((prev) => ({ ...prev, submitProposal: false }));
    }
  };

  const handleCastVote = async (values: any) => {
    setActionLoading((prev) => ({ ...prev, castVote: true }));
    try {
      await api.castVote(id!, values.proposal_id, values.voter_id, values.vote, values.confidence, values.reasoning);
      message.success('投票成功');
      setVoteModalOpen(false);
      voteForm.resetFields();
      loadParliament();
    } catch (err: any) {
      message.error(err.message || '投票失败');
    } finally {
      setActionLoading((prev) => ({ ...prev, castVote: false }));
    }
  };

  const handleResolve = async (values: any) => {
    setActionLoading((prev) => ({ ...prev, resolve: true }));
    try {
      let resolution: any;
      try {
        resolution = JSON.parse(values.resolution);
      } catch {
        resolution = values.resolution;
      }
      await api.resolveParliament(id!, resolution);
      message.success('裁决完成');
      setResolveModalOpen(false);
      resolveForm.resetFields();
      loadParliament();
    } catch (err: any) {
      message.error(err.message || '裁决失败');
    } finally {
      setActionLoading((prev) => ({ ...prev, resolve: false }));
    }
  };

  const getCurrentStep = () => {
    if (!parliament) return 0;
    const status = parliament.status;
    if (status === 'deliberating') return 0;
    if (status === 'voting') return 1;
    if (status === 'consensus_reached') return 2;
    if (status === 'deadlocked' || status === 'escalated') return 2;
    if (status === 'resolved') return 3;
    return 0;
  };

  const getStepStatus = (stepIndex: number) => {
    const current = getCurrentStep();
    if (stepIndex < current) return 'finish';
    if (stepIndex === current) return 'process';
    return 'wait';
  };

  // Compute vote totals for a proposal
  const computeVoteStats = (proposal: any) => {
    const votes = proposal.votes || [];
    const total = votes.length;
    const favor = votes.filter((v: any) => v.vote === 'favor').length;
    const against = votes.filter((v: any) => v.vote === 'against').length;
    const abstain = votes.filter((v: any) => v.vote === 'abstain').length;
    const favorPct = total > 0 ? Math.round((favor / total) * 100) : 0;
    const againstPct = total > 0 ? Math.round((against / total) * 100) : 0;
    const abstainPct = total > 0 ? Math.round((abstain / total) * 100) : 0;
    return { total, favor, against, abstain, favorPct, againstPct, abstainPct };
  };

  const stepsItems = [
    {
      title: '协商中',
      description: '成员提交提案并讨论',
    },
    {
      title: '投票中',
      description: '对提案进行投票表决',
    },
    {
      title: parliament?.status === 'deadlocked' || parliament?.status === 'escalated' ? '升级/僵局' : '达成共识',
      description: parliament?.status === 'deadlocked' || parliament?.status === 'escalated'
        ? '协商陷入僵局，等待升级仲裁'
        : '各方达成共识',
    },
    {
      title: '仲裁裁决',
      description: '仲裁方做出最终裁决',
    },
  ];

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!parliament) {
    return <Empty description="议会不存在" />;
  }

  const sc = statusConfig[parliament.status] || { color: 'default', label: parliament.status };
  const members = parliament.members || [];
  const proposals = parliament.proposals || [];

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/parliament')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>
          <BankOutlined style={{ marginRight: 8 }} />
          {parliament.title}
        </Title>
        <Tag color={sc.color}>{sc.label}</Tag>
      </div>

      {/* Flow Steps */}
      <Card style={{ marginBottom: 16 }}>
        <Steps
          current={getCurrentStep()}
          status={parliament.status === 'deadlocked' ? 'error' : undefined}
          items={stepsItems.map((item, idx) => ({
            ...item,
            status: getStepStatus(idx) === 'finish' ? 'finish' : getStepStatus(idx) === 'process' ? 'process' : 'wait',
          }))}
        />
      </Card>

      {/* Basic Info */}
      <Card title="基本信息" style={{ marginBottom: 16 }}>
        <Descriptions bordered column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="标题">{parliament.title}</Descriptions.Item>
          <Descriptions.Item label="议题">{parliament.topic || '-'}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={sc.color}>{sc.label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="共识类型">
            <Tag color="cyan">{consensusTypeLabels[parliament.consensus_type] || parliament.consensus_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="当前轮次">
            {parliament.round || 0}{parliament.max_rounds ? ` / ${parliament.max_rounds}` : ''}
          </Descriptions.Item>
          <Descriptions.Item label="最低置信度">{parliament.min_confidence ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {parliament.created_at ? new Date(parliament.created_at).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {parliament.updated_at ? new Date(parliament.updated_at).toLocaleString() : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Resolution display */}
      {(parliament.status === 'consensus_reached' || parliament.status === 'resolved') && parliament.resolution && (
        <Card title="决议内容" style={{ marginBottom: 16 }}>
          <Alert
            type={parliament.status === 'resolved' ? 'info' : 'success'}
            message={parliament.status === 'resolved' ? '仲裁裁决' : '达成共识'}
            description={
              typeof parliament.resolution === 'string'
                ? parliament.resolution
                : JSON.stringify(parliament.resolution, null, 2)
            }
            showIcon
            icon={parliament.status === 'resolved' ? <TrophyOutlined /> : <CheckCircleOutlined />}
          />
        </Card>
      )}

      {/* Members */}
      <Card title={`成员 (${members.length})`} style={{ marginBottom: 16 }}>
        {members.length === 0 ? (
          <Empty description="暂无成员" />
        ) : (
          <List
            grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
            dataSource={members}
            renderItem={(member: any) => (
              <List.Item>
                <Card size="small">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Avatar icon={member.type === 'agent' ? <RobotOutlined /> : <UserOutlined />} />
                      <div>
                        <Text strong>{member.name || member.id?.slice(0, 8)}</Text>
                        <br />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {member.role || 'member'}
                        </Text>
                      </div>
                    </div>
                    {member.level !== undefined && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        层级: {member.level}
                      </Text>
                    )}
                    {member.weight !== undefined && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        权重: {member.weight}
                      </Text>
                    )}
                  </Space>
                </Card>
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* Proposals & Voting */}
      <Card title={`提案 (${proposals.length})`} style={{ marginBottom: 16 }}>
        {proposals.length === 0 ? (
          <Empty description="暂无提案" />
        ) : (
          <List
            dataSource={proposals}
            renderItem={(proposal: any) => {
              const voteStats = computeVoteStats(proposal);
              const proposalStatus = proposal.status || 'pending';
              const proposalStatusColor =
                proposalStatus === 'accepted' ? 'green' :
                proposalStatus === 'rejected' ? 'red' :
                proposalStatus === 'pending' ? 'blue' : 'default';
              return (
                <List.Item>
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                      <Space direction="vertical" size={4}>
                        <Space>
                          <Text strong>{proposal.content}</Text>
                          <Tag color={proposalStatusColor}>{proposalStatus}</Tag>
                        </Space>
                        <Space size={12}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            提出者: {proposal.proposer_name || proposal.proposer_id?.slice(0, 8)}
                          </Text>
                          {proposal.confidence !== undefined && (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              置信度: {Math.round(proposal.confidence * 100)}%
                            </Text>
                          )}
                        </Space>
                      </Space>
                    </div>

                    {/* Vote summary */}
                    {voteStats.total > 0 && (
                      <div style={{ marginTop: 8 }}>
                        <div style={{ display: 'flex', gap: 16, marginBottom: 4 }}>
                          <Space size={4}>
                            <LikeOutlined style={{ color: voteColorMap.favor }} />
                            <Text style={{ fontSize: 12 }}>赞成 {voteStats.favor}</Text>
                          </Space>
                          <Space size={4}>
                            <DislikeOutlined style={{ color: voteColorMap.against }} />
                            <Text style={{ fontSize: 12 }}>反对 {voteStats.against}</Text>
                          </Space>
                          <Space size={4}>
                            <MinusCircleOutlined style={{ color: voteColorMap.abstain }} />
                            <Text style={{ fontSize: 12 }}>弃权 {voteStats.abstain}</Text>
                          </Space>
                        </div>
                        <Progress
                          percent={voteStats.favorPct}
                          success={{ percent: voteStats.favorPct, strokeColor: voteColorMap.favor }}
                          strokeColor={voteColorMap.against}
                          format={() => `${voteStats.favorPct}% / ${voteStats.againstPct}% / ${voteStats.abstainPct}%`}
                          style={{ marginBottom: 0 }}
                        />
                      </div>
                    )}

                    {/* Individual votes */}
                    {(proposal.votes || []).length > 0 && (
                      <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {(proposal.votes || []).map((vote: any, idx: number) => (
                          <Tag
                            key={idx}
                            color={voteColorMap[vote.vote] || 'default'}
                            style={{ fontSize: 11 }}
                          >
                            {voteIconMap[vote.vote]} {vote.voter_name || vote.voter_id?.slice(0, 6)}
                            {vote.confidence !== undefined && ` (${Math.round(vote.confidence * 100)}%)`}
                          </Tag>
                        ))}
                      </div>
                    )}
                  </div>
                </List.Item>
              );
            }}
          />
        )}
      </Card>

      {/* Action Buttons */}
      <Card title="操作" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={actionLoading['deliberate']}
            onClick={() => handleAction('deliberate', () => api.deliberateParliament(id!))}
          >
            开始协商
          </Button>
          <Button
            icon={<PlusOutlined />}
            loading={actionLoading['submitProposal']}
            onClick={() => {
              proposalForm.resetFields();
              setProposalModalOpen(true);
            }}
          >
            提交提案
          </Button>
          <Button
            icon={<SendOutlined />}
            loading={actionLoading['castVote']}
            onClick={() => {
              voteForm.resetFields();
              setVoteModalOpen(true);
            }}
          >
            投票
          </Button>
          <Button
            icon={<CheckCircleOutlined />}
            loading={actionLoading['tally']}
            onClick={() => handleAction('tally', () => api.tallyParliament(id!))}
          >
            计票
          </Button>
          <Button
            icon={<ExclamationCircleOutlined />}
            loading={actionLoading['escalate']}
            danger
            onClick={() => handleAction('escalate', () => api.escalateParliament(id!))}
          >
            升级仲裁
          </Button>
          <Button
            icon={<TrophyOutlined />}
            loading={actionLoading['resolve']}
            onClick={() => {
              resolveForm.resetFields();
              setResolveModalOpen(true);
            }}
          >
            手动裁决
          </Button>
        </Space>
      </Card>

      {/* Submit Proposal Modal */}
      <Modal
        title="提交提案"
        open={proposalModalOpen}
        onCancel={() => setProposalModalOpen(false)}
        footer={null}
        width={520}
      >
        <Form form={proposalForm} onFinish={handleSubmitProposal} layout="vertical">
          <Form.Item
            name="proposer_id"
            label="提案者 ID"
            rules={[{ required: true, message: '请输入提案者 ID' }]}
          >
            <Select
              style={{ width: '100%' }}
              placeholder="选择提案者"
              showSearch
              optionFilterProp="children"
              options={members.map((m: any) => ({
                value: m.id || m.member_id,
                label: `${m.name || m.id?.slice(0, 8)} (${m.role || 'member'})`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="content"
            label="提案内容"
            rules={[{ required: true, message: '请输入提案内容' }]}
          >
            <Input.TextArea placeholder="描述你的提案内容" rows={4} />
          </Form.Item>
          <Form.Item name="confidence" label="置信度" initialValue={0.5}>
            <InputNumber
              min={0}
              max={1}
              step={0.1}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={actionLoading['submitProposal']}>
              提交
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Vote Modal */}
      <Modal
        title="投票"
        open={voteModalOpen}
        onCancel={() => setVoteModalOpen(false)}
        footer={null}
        width={520}
      >
        <Form form={voteForm} onFinish={handleCastVote} layout="vertical">
          <Form.Item
            name="proposal_id"
            label="选择提案"
            rules={[{ required: true, message: '请选择提案' }]}
          >
            <Select
              style={{ width: '100%' }}
              placeholder="选择要投票的提案"
              options={proposals.map((p: any) => ({
                value: p.id,
                label: `${p.content?.slice(0, 50)}${p.content?.length > 50 ? '...' : ''}`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="voter_id"
            label="投票者 ID"
            rules={[{ required: true, message: '请选择投票者' }]}
          >
            <Select
              style={{ width: '100%' }}
              placeholder="选择投票者"
              showSearch
              optionFilterProp="children"
              options={members.map((m: any) => ({
                value: m.id || m.member_id,
                label: `${m.name || m.id?.slice(0, 8)} (${m.role || 'member'})`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="vote"
            label="投票类型"
            rules={[{ required: true, message: '请选择投票类型' }]}
          >
            <Select
              style={{ width: '100%' }}
              options={[
                { value: 'favor', label: '赞成' },
                { value: 'against', label: '反对' },
                { value: 'abstain', label: '弃权' },
              ]}
            />
          </Form.Item>
          <Form.Item name="confidence" label="置信度" initialValue={0.5}>
            <InputNumber
              min={0}
              max={1}
              step={0.1}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item name="reasoning" label="投票理由">
            <Input.TextArea placeholder="可选：输入投票理由" rows={2} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={actionLoading['castVote']}>
              确认投票
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Resolve Modal */}
      <Modal
        title="手动裁决"
        open={resolveModalOpen}
        onCancel={() => setResolveModalOpen(false)}
        footer={null}
        width={520}
      >
        <Form form={resolveForm} onFinish={handleResolve} layout="vertical">
          <Form.Item
            name="resolution"
            label="裁决内容"
            rules={[{ required: true, message: '请输入裁决内容' }]}
            extra="支持纯文本或 JSON 格式"
          >
            <Input.TextArea
              placeholder='输入裁决结果，例如：{"decision": "approved", "reason": "..."}'
              rows={6}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={actionLoading['resolve']}>
              确认裁决
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ParliamentDetail;