import React, { useState, useEffect } from 'react';
import { Typography, Tag, Progress, Empty, Divider, Avatar, Button, Modal, Form, Select, Input, message } from 'antd';
import {
  CloseOutlined, TeamOutlined, FileOutlined, PaperClipOutlined,
  ClockCircleOutlined, PlusOutlined, RobotOutlined, UserOutlined,
} from '@ant-design/icons';
import type { Session } from '../../store/chatStore';
import { api } from '../../api';
import {
  roleColorMap,
  roleLabelMap,
  statusColorMap,
  statusLabelMap,
  priorityColorMap,
  priorityLabelMap,
} from './constants';

const { Text } = Typography;

// ─── Session list item ───────────────────────────────────────────
const SessionListItem: React.FC<{
  session: Session;
  isActive: boolean;
  onClick: () => void;
}> = ({ session, isActive, onClick }) => (
  <div
    onClick={onClick}
    style={{
      padding: '10px 12px',
      cursor: 'pointer',
      background: isActive ? 'rgba(22,119,255,0.1)' : 'transparent',
      borderRadius: 6,
      marginBottom: 2,
      borderLeft: isActive ? '3px solid #1677ff' : '3px solid transparent',
      transition: 'all 0.2s',
    }}
  >
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <Text ellipsis style={{ fontSize: 13, maxWidth: 140, fontWeight: isActive ? 600 : 400 }}>
        {session.title}
      </Text>
      <Tag color={statusColorMap[session.status]} style={{ fontSize: 10, marginLeft: 4 }}>
        {statusLabelMap[session.status] || session.status}
      </Tag>
    </div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
      <Text type="secondary" style={{ fontSize: 11 }}>
        {session.assigned_to_name || session.assigned_to?.slice(0, 8)}
      </Text>
      <Tag color={priorityColorMap[session.priority]} style={{ fontSize: 10 }}>
        {priorityLabelMap[session.priority] || session.priority}
      </Tag>
    </div>
    {session.status === 'in_progress' && (
      <Progress percent={session.progress || 0} size="small" style={{ marginTop: 4 }} />
    )}
  </div>
);

// ─── Create session modal ───────────────────────────────────────
interface CreateSessionModalProps {
  open: boolean;
  onClose: () => void;
  groupId: string;
  agents: any[];
  onSuccess: () => void;
}

const CreateSessionModal: React.FC<CreateSessionModalProps> = ({
  open,
  onClose,
  groupId,
  agents,
  onSuccess,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleCreate = async (values: any) => {
    setLoading(true);
    try {
      await api.createSession(
        groupId,
        values.title,
        values.description || '',
        values.assigned_to,
        values.priority || 'medium'
      );
      message.success('Session 创建成功');
      form.resetFields();
      onClose();
      onSuccess();
    } catch (err: any) {
      message.error(err.message || '创建失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="创建 Session"
      open={open}
      onCancel={onClose}
      footer={null}
      destroyOnClose
    >
      <Form form={form} onFinish={handleCreate} layout="vertical">
        <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
          <Input placeholder="输入 Session 标题" />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea placeholder="输入描述" rows={3} />
        </Form.Item>
        <Form.Item name="assigned_to" label="分配给" rules={[{ required: true, message: '请选择分配对象' }]}>
          <Select
            placeholder="选择 Agent 或用户"
            showSearch
            optionFilterProp="children"
            options={agents.map((a: any) => ({
              value: a.id,
              label: `${a.name || a.username || a.id.slice(0, 8)}`,
            }))}
          />
        </Form.Item>
        <Form.Item name="priority" label="优先级" initialValue="medium">
          <Select
            options={[
              { value: 'low', label: '低' },
              { value: 'medium', label: '中' },
              { value: 'high', label: '高' },
              { value: 'critical', label: '紧急' },
            ]}
          />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            创建
          </Button>
        </Form.Item>
      </Form>
    </Modal>
  );
};

// ─── Right panel: Group info ────────────────────────────────────
interface GroupInfoPanelProps {
  group: any;
  onClose: () => void;
  sessions: Session[];
  onSelectSession: (id: string) => void;
}

const GroupInfoPanel: React.FC<GroupInfoPanelProps> = ({
  group,
  onClose,
  sessions,
  onSelectSession,
}) => {
  const [files, setFiles] = useState<any[]>([]);

  useEffect(() => {
    if (group?.id) {
      api.listFiles(group.id).then(setFiles).catch(() => {});
    }
  }, [group?.id]);

  if (!group) return null;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <Text strong>群组信息</Text>
        <Button type="text" icon={<CloseOutlined />} size="small" onClick={onClose} />
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
        {/* Group name & description */}
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ fontSize: 15 }}>{group.name}</Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>{group.description || '暂无描述'}</Text>
        </div>

        <Divider style={{ margin: '12px 0' }} />

        {/* Members */}
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
            <TeamOutlined style={{ marginRight: 4 }} />
            成员 ({group.members?.length || 0})
          </Text>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(group.members || []).map((member: any, idx: number) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Avatar
                  size={28}
                  icon={member.type === 'agent' || member.member_type === 'agent' ? <RobotOutlined /> : <UserOutlined />}
                  style={{
                    background: member.type === 'agent' || member.member_type === 'agent' ? '#52c41a' : '#1677ff',
                    fontSize: 12,
                  }}
                />
                <div style={{ flex: 1 }}>
                  <Text style={{ fontSize: 12 }}>{member.name || member.member_name || member.id || member.member_id?.slice(0, 12)}</Text>
                </div>
                <Tag color={roleColorMap[member.role]} style={{ fontSize: 10 }}>
                  {roleLabelMap[member.role] || member.role || '成员'}
                </Tag>
              </div>
            ))}
          </div>
        </div>

        <Divider style={{ margin: '12px 0' }} />

        {/* Files */}
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
            <PaperClipOutlined style={{ marginRight: 4 }} />
            文件 ({files.length})
          </Text>
          {files.length === 0 ? (
            <Text type="secondary" style={{ fontSize: 12 }}>暂无文件</Text>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {files.map((file: any, idx: number) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 8px',
                    background: 'rgba(255,255,255,0.03)',
                    borderRadius: 4,
                    cursor: 'pointer',
                  }}
                  onClick={() => window.open(api.downloadFile(file.id), '_blank')}
                >
                  <FileOutlined style={{ color: '#1677ff' }} />
                  <Text ellipsis style={{ flex: 1, fontSize: 12 }}>{file.filename || file.name}</Text>
                  <Text type="secondary" style={{ fontSize: 10 }}>
                    {file.size ? `${(file.size / 1024).toFixed(1)}KB` : ''}
                  </Text>
                </div>
              ))}
            </div>
          )}
        </div>

        <Divider style={{ margin: '12px 0' }} />

        {/* Sessions / Tasks */}
        <div>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            Sessions / 任务 ({sessions.length})
          </Text>
          {sessions.length === 0 ? (
            <Text type="secondary" style={{ fontSize: 12 }}>暂无 Session</Text>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {sessions.map((session) => (
                <div
                  key={session.id}
                  style={{
                    padding: '6px 8px',
                    background: 'rgba(255,255,255,0.03)',
                    borderRadius: 4,
                    cursor: 'pointer',
                  }}
                  onClick={() => onSelectSession(session.id)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text ellipsis style={{ fontSize: 12, maxWidth: 120 }}>{session.title}</Text>
                    <Tag color={statusColorMap[session.status]} style={{ fontSize: 10 }}>
                      {statusLabelMap[session.status] || session.status}
                    </Tag>
                  </div>
                  {session.status === 'in_progress' && (
                    <Progress percent={session.progress || 0} size="small" style={{ marginTop: 4 }} />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ─── Session list panel (shown in session tab) ───────────────────
export interface SessionListPanelProps {
  sessions: Session[];
  onSelectSession: (sessionId: string) => void;
  onCreateSession: () => void;
}

const SessionListPanel: React.FC<SessionListPanelProps> = React.memo(({
  sessions,
  onSelectSession,
  onCreateSession,
}) => (
  <div
    style={{
      width: 280,
      borderLeft: '1px solid rgba(255,255,255,0.06)',
      overflow: 'auto',
      padding: '8px',
      flexShrink: 0,
    }}
  >
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
      <Text strong style={{ fontSize: 13 }}>Session 列表</Text>
      <Button
        type="text"
        icon={<PlusOutlined />}
        size="small"
        onClick={onCreateSession}
      />
    </div>
    {sessions.length === 0 ? (
      <Empty description="暂无 Session" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    ) : (
      sessions.map((session) => (
        <SessionListItem
          key={session.id}
          session={session}
          isActive={false}
          onClick={() => onSelectSession(session.id)}
        />
      ))
    )}
  </div>
));

SessionListPanel.displayName = 'SessionListPanel';

// ─── Re-exports ─────────────────────────────────────────────────
export { CreateSessionModal, GroupInfoPanel };
export default SessionListPanel;
