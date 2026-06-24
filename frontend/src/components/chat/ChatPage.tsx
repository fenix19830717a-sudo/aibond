import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout, List, Typography, Space, Tabs, Badge, Avatar, Button, Empty, message, Tag,
} from 'antd';
import {
  PlusOutlined, InfoCircleOutlined, RightOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../../store/authStore';
import { useChatStore } from '../../store/chatStore';
import { api } from '../../api';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import SessionListPanel, { CreateSessionModal, GroupInfoPanel } from './SessionPanel';
import { statusColorMap, statusLabelMap } from './constants';

const { Sider, Content } = Layout;
const { Text } = Typography;

// ─── Group info type ────────────────────────────────────────────
interface GroupInfo {
  id: string;
  name: string;
  description: string;
  members: any[];
}

// ─── Main ChatPage orchestrator ────────────────────────────────
const ChatPage: React.FC = () => {
  const { user } = useAuthStore();
  const {
    currentGroupId,
    currentSessionId,
    sessions,
    messages,
    unreadCounts,
    setGroupId,
    setSessionId,
    setSessions,
    updateSession,
    addMessage,
    setMessages,
    incrementUnread,
    clearUnread,
  } = useChatStore();

  const [groups, setGroups] = useState<GroupInfo[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [currentGroupDetail, setCurrentGroupDetail] = useState<any>(null);
  const [availableAgents, setAvailableAgents] = useState<any[]>([]);
  const [createSessionOpen, setCreateSessionOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('group');

  // ─── Load groups & agents on mount ───────────────────────────
  useEffect(() => {
    loadGroups();
    loadAvailableAgents();
  }, []);

  // ─── When group changes, load messages, sessions, connect WS ──
  useEffect(() => {
    if (currentGroupId) {
      loadMessages();
      loadSessions();
      loadGroupDetail();
      connectWebSocket();
      clearUnread(currentGroupId);
    }
    return () => {
      if (ws) ws.close();
    };
  }, [currentGroupId]);

  // ─── When session changes, load session messages ──────────────
  useEffect(() => {
    if (currentSessionId) {
      loadSessionMessages();
    }
  }, [currentSessionId]);

  // ─── Data loading functions ───────────────────────────────────
  const loadAvailableAgents = async () => {
    try {
      const data = await api.listAvailableAgents();
      setAvailableAgents(data);
    } catch (err) {
      console.error('Failed to load agents:', err);
    }
  };

  const loadGroups = async () => {
    try {
      const data = await api.listGroups();
      setGroups(data);
      if (data.length > 0 && !currentGroupId) {
        setGroupId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load groups:', err);
    }
  };

  const loadGroupDetail = async () => {
    if (!currentGroupId) return;
    try {
      const detail = await api.getGroup(currentGroupId);
      setCurrentGroupDetail(detail);
    } catch (err) {
      console.error('Failed to load group detail:', err);
    }
  };

  const loadMessages = async () => {
    if (!currentGroupId) return;
    try {
      const data = await api.getMessages(currentGroupId);
      setMessages(data.messages || data);
    } catch (err) {
      console.error('Failed to load messages:', err);
    }
  };

  const loadSessions = async () => {
    if (!currentGroupId) return;
    try {
      const data = await api.listSessions(currentGroupId);
      setSessions(data || []);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  const loadSessionMessages = async () => {
    if (!currentSessionId) return;
    try {
      const session = await api.getSession(currentSessionId);
      if (session.messages) {
        setMessages(session.messages);
      }
    } catch (err) {
      console.error('Failed to load session messages:', err);
    }
  };

  // ─── WebSocket connection management ───────────────────────────
  const connectWebSocket = () => {
    if (!user || !currentGroupId) return;
    if (ws) ws.close();

    const wsBase = import.meta.env.VITE_WS_BASE || `wss://${window.location.host}`;
    const socket = new WebSocket(`${wsBase}/ws/user/${user.id}`);
    socket.onopen = () => console.log('WebSocket connected');
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWsMessage(data);
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };
    socket.onclose = () => console.log('WebSocket disconnected');
    setWs(socket);
  };

  const handleWsMessage = useCallback((data: any) => {
    const payload = data.data && typeof data.data === 'object' ? data.data : data;

    switch (data.type) {
      case 'message':
        if (payload.group_id === currentGroupId && !currentSessionId) {
          addMessage(payload);
        } else if (payload.group_id && payload.group_id !== currentGroupId) {
          incrementUnread(payload.group_id);
        }
        break;

      case 'session_message':
        if (payload.session_id === currentSessionId) {
          addMessage(payload);
        }
        if (payload.session) {
          updateSession(payload.session);
        }
        break;

      case 'task_assign':
        if (payload.group_id === currentGroupId) {
          addMessage({
            id: `task-assign-${Date.now()}`,
            sender_type: 'system',
            sender_name: '系统',
            msg_type: 'notification',
            content: `任务分配: ${payload.title || '新任务'} -> ${payload.assigned_to_name || payload.assigned_to || '未知'}`,
            metadata: { task: payload },
            created_at: new Date().toISOString(),
          });
        }
        break;

      case 'task_progress':
        if (payload.session_id) {
          updateSession({
            id: payload.session_id,
            group_id: payload.group_id || '',
            title: '',
            description: '',
            status: payload.status || 'in_progress',
            priority: '',
            progress: payload.progress || 0,
            progress_description: payload.progress_description || '',
            assigned_to: payload.assigned_to || '',
            created_at: '',
          });
        }
        if (payload.group_id === currentGroupId) {
          addMessage({
            id: `task-progress-${Date.now()}`,
            sender_type: 'system',
            sender_name: '系统',
            msg_type: 'notification',
            content: `任务进度更新: ${payload.title || ''} - ${payload.progress || 0}%`,
            metadata: { task: payload },
            created_at: new Date().toISOString(),
          });
        }
        break;

      case 'task_complete':
        if (payload.session_id) {
          updateSession({
            id: payload.session_id,
            group_id: payload.group_id || '',
            title: '',
            description: '',
            status: 'completed',
            priority: '',
            progress: 100,
            progress_description: payload.summary || '已完成',
            assigned_to: payload.assigned_to || '',
            created_at: '',
          });
        }
        if (payload.group_id === currentGroupId) {
          addMessage({
            id: `task-complete-${Date.now()}`,
            sender_type: 'system',
            sender_name: '系统',
            msg_type: 'notification',
            content: `任务完成: ${payload.title || '任务'}${payload.summary ? '\n' + payload.summary : ''}`,
            metadata: { task: payload },
            created_at: new Date().toISOString(),
          });
        }
        break;

      case 'mention':
        if (payload.group_id === currentGroupId) {
          addMessage({
            id: `mention-${Date.now()}`,
            sender_type: payload.sender_type || 'system',
            sender_name: payload.sender_name || '系统',
            msg_type: 'mention',
            content: payload.content || '',
            metadata: payload,
            created_at: new Date().toISOString(),
            mentions: payload.mentions || [],
          });
        }
        break;

      default:
        if (payload && payload.content) {
          addMessage(payload);
        }
        break;
    }
  }, [currentGroupId, currentSessionId, addMessage, incrementUnread, updateSession]);

  // ─── Message send handler ─────────────────────────────────────
  const handleSend = async (content: string) => {
    if (!currentGroupId || !user) return;

    if (currentSessionId) {
      const msg = await api.sendSessionMessage(currentSessionId, 'user', user.id, content);
      addMessage(msg);
    } else {
      const msg = await api.sendMessage(currentGroupId, 'user', user.id, content);
      addMessage(msg);
    }
  };

  // ─── File upload handler ─────────────────────────────────────
  const handleFileUpload = async (file: File) => {
    if (!currentGroupId || !user) return false;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('group_id', currentGroupId);
    if (currentSessionId) {
      formData.append('session_id', currentSessionId);
    }

    try {
      const result = await api.uploadFile(formData);
      if (currentSessionId) {
        await api.sendSessionMessage(currentSessionId, 'user', user.id, `[文件] ${file.name}`, 'file');
      } else {
        await api.sendMessage(currentGroupId, 'user', user.id, `[文件] ${file.name}`, 'file', { file: result });
      }
      message.success('文件上传成功');
    } catch (err: any) {
      message.error(err.message || '文件上传失败');
    }
    return false;
  };

  // ─── Navigation handlers ─────────────────────────────────────
  const handleGroupSelect = (groupId: string) => {
    setGroupId(groupId);
    setActiveTab('group');
  };

  const handleSessionSelect = (sessionId: string) => {
    setSessionId(sessionId);
    setActiveTab('session');
  };

  const handleBackToGroup = () => {
    setSessionId(null);
    setActiveTab('group');
    loadMessages();
  };

  const handleCreateSessionSuccess = () => {
    loadSessions();
  };

  // ─── Render ─────────────────────────────────────────────────
  return (
    <Layout style={{ height: 'calc(100vh - 112px)', background: 'transparent' }}>
      {/* ─── Left sidebar: Group list ──────────────────────────── */}
      <Sider
        width={260}
        style={{
          background: 'transparent',
          borderRight: '1px solid rgba(255,255,255,0.06)',
          marginRight: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text strong>对话列表</Text>
          <Button type="text" icon={<PlusOutlined />} size="small" />
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <List
            dataSource={groups}
            renderItem={(group) => {
              const unread = unreadCounts[group.id] || 0;
              return (
                <List.Item
                  onClick={() => handleGroupSelect(group.id)}
                  style={{
                    padding: '12px 16px',
                    cursor: 'pointer',
                    background: currentGroupId === group.id && !currentSessionId ? 'rgba(22,119,255,0.1)' : 'transparent',
                    borderRadius: 8,
                    marginBottom: 2,
                  }}
                >
                  <List.Item.Meta
                    avatar={
                      <Badge count={unread} size="small" offset={[-4, 4]}>
                        <Avatar style={{ background: '#1677ff' }}>{group.name[0]}</Avatar>
                      </Badge>
                    }
                    title={
                      <Text style={{ color: currentGroupId === group.id && !currentSessionId ? '#1677ff' : 'inherit' }}>
                        {group.name}
                      </Text>
                    }
                    description={<Text type="secondary" style={{ fontSize: 12 }}>{group.description || '暂无描述'}</Text>}
                  />
                </List.Item>
              );
            }}
            locale={{ emptyText: <Empty description="暂无群组" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          />
        </div>
      </Sider>

      {/* ─── Middle: Message area ──────────────────────────────── */}
      <Content style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
        {currentGroupId ? (
          <>
            {/* Header bar */}
            <div
              style={{
                padding: '10px 16px',
                borderBottom: '1px solid rgba(255,255,255,0.06)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexShrink: 0,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {currentSessionId && (
                  <Button type="text" icon={<RightOutlined />} size="small" onClick={handleBackToGroup} style={{ transform: 'rotate(180deg)' }} />
                )}
                <Text strong>
                  {currentSessionId
                    ? sessions.find(s => s.id === currentSessionId)?.title || 'Session'
                    : groups.find(g => g.id === currentGroupId)?.name || '群组聊天'}
                </Text>
                {currentSessionId && (
                  <Tag color={statusColorMap[sessions.find(s => s.id === currentSessionId)?.status || 'pending']} style={{ fontSize: 10 }}>
                    {statusLabelMap[sessions.find(s => s.id === currentSessionId)?.status || 'pending']}
                  </Tag>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Button
                  type="text"
                  icon={<PlusOutlined />}
                  size="small"
                  onClick={() => setCreateSessionOpen(true)}
                  title="创建 Session"
                />
                <Button
                  type="text"
                  icon={<InfoCircleOutlined />}
                  size="small"
                  onClick={() => setRightPanelOpen(!rightPanelOpen)}
                  title="群组信息"
                />
              </div>
            </div>

            {/* Sub-tabs: Group messages / Sessions */}
            {!currentSessionId && (
              <div style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
                <Tabs
                  activeKey={activeTab}
                  onChange={(key) => {
                    if (key === 'group') {
                      handleBackToGroup();
                    }
                    setActiveTab(key);
                  }}
                  size="small"
                  style={{ marginBottom: 0, paddingLeft: 16 }}
                  items={[
                    { key: 'group', label: '群组消息' },
                    {
                      key: 'session',
                      label: (
                        <Space size={4}>
                          Sessions
                          {sessions.length > 0 && (
                            <Tag style={{ fontSize: 10, marginLeft: 0 }}>{sessions.length}</Tag>
                          )}
                        </Space>
                      ),
                    },
                  ]}
                />
              </div>
            )}

            {/* Content area: Messages + optional session list */}
            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
              {/* Messages column */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                <MessageList
                  messages={messages}
                  currentSessionId={currentSessionId}
                  currentUserName={user?.username}
                  currentDisplayName={user?.display_name}
                  userId={user?.id}
                />

                {/* Input area */}
                <MessageInput
                  currentGroupId={currentGroupId}
                  currentSessionId={currentSessionId}
                  userId={user?.id}
                  onSend={handleSend}
                  onFileUpload={handleFileUpload}
                />
              </div>

              {/* Session list panel (when session tab is active) */}
              {activeTab === 'session' && !currentSessionId && (
                <SessionListPanel
                  sessions={sessions}
                  onSelectSession={handleSessionSelect}
                  onCreateSession={() => setCreateSessionOpen(true)}
                />
              )}
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Empty description="选择一个群组开始对话" />
          </div>
        )}
      </Content>

      {/* ─── Right panel: Group info (collapsible) ─────────────── */}
      {rightPanelOpen && currentGroupDetail && (
        <Sider
          width={300}
          style={{
            background: 'rgba(255,255,255,0.02)',
            borderLeft: '1px solid rgba(255,255,255,0.06)',
            flexShrink: 0,
          }}
        >
          <GroupInfoPanel
            group={currentGroupDetail}
            onClose={() => setRightPanelOpen(false)}
            sessions={sessions}
            onSelectSession={(id) => {
              handleSessionSelect(id);
              setRightPanelOpen(false);
            }}
          />
        </Sider>
      )}

      {/* ─── Create session modal ─────────────────────────────── */}
      <CreateSessionModal
        open={createSessionOpen}
        onClose={() => setCreateSessionOpen(false)}
        groupId={currentGroupId || ''}
        agents={availableAgents}
        onSuccess={handleCreateSessionSuccess}
      />
    </Layout>
  );
};

export default ChatPage;
