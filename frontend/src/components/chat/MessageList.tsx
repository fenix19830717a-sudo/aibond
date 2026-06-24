import React, { useEffect, useRef } from 'react';
import { Avatar, Typography, Tag, Progress, Empty } from 'antd';
import {
  RobotOutlined, UserOutlined, FileOutlined, DownloadOutlined,
  BellOutlined,
} from '@ant-design/icons';
import type { Message } from '../../store/chatStore';
import { api } from '../../api';
import { renderContentWithMentions } from './constants';

const { Text } = Typography;

// ─── File message card ───────────────────────────────────────────
const FileMessageCard: React.FC<{ metadata: any }> = ({ metadata }) => {
  const file = metadata?.file || metadata;
  if (!file) return null;
  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 8,
        padding: '10px 12px',
        minWidth: 220,
        maxWidth: 320,
        cursor: 'pointer',
      }}
      onClick={() => {
        if (file.id) {
          window.open(api.downloadFile(file.id), '_blank');
        }
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <FileOutlined style={{ fontSize: 20, color: '#1677ff' }} />
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <Text ellipsis style={{ display: 'block', fontSize: 13, maxWidth: 200 }}>
            {file.filename || file.name || '未知文件'}
          </Text>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {file.size ? `${(file.size / 1024).toFixed(1)} KB` : ''}
          </Text>
        </div>
        <DownloadOutlined style={{ color: '#1677ff' }} />
      </div>
    </div>
  );
};

// ─── Task message card ───────────────────────────────────────────
const TaskMessageCard: React.FC<{ metadata: any }> = ({ metadata }) => {
  const task = metadata?.task || metadata;
  if (!task) return null;
  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 8,
        padding: '10px 12px',
        minWidth: 240,
        maxWidth: 360,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <Text strong style={{ fontSize: 13 }}>{task.title || '任务'}</Text>
        <Tag color={
          task.status === 'pending' ? 'default' :
          task.status === 'assigned' ? 'processing' :
          task.status === 'in_progress' ? 'processing' :
          task.status === 'completed' ? 'success' :
          task.status === 'failed' ? 'error' :
          'warning'
        } style={{ fontSize: 10 }}>
          {task.status === 'pending' ? '待处理' :
           task.status === 'assigned' ? '已分配' :
           task.status === 'in_progress' ? '进行中' :
           task.status === 'completed' ? '已完成' :
           task.status === 'failed' ? '失败' :
           task.status === 'cancelled' ? '已取消' :
           task.status}
        </Tag>
      </div>
      {task.progress !== undefined && (
        <Progress
          percent={task.progress}
          size="small"
          status={task.status === 'failed' ? 'exception' : task.status === 'completed' ? 'success' : 'active'}
        />
      )}
      {task.description && (
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
          {task.description}
        </Text>
      )}
    </div>
  );
};

// ─── Props ──────────────────────────────────────────────────────
export interface MessageListProps {
  messages: Message[];
  currentSessionId: string | null;
  currentUserName?: string;
  currentDisplayName?: string;
  userId?: string;
}

// ─── MessageList component ──────────────────────────────────────
const MessageList: React.FC<MessageListProps> = React.memo(({
  messages,
  currentSessionId,
  currentUserName,
  currentDisplayName,
  userId,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const isOwnMessage = (msg: Message) => {
    return msg.sender_type === 'user' && msg.sender_id === userId;
  };

  const renderMessageBubble = (msg: Message) => {
    const own = isOwnMessage(msg);
    const isSystem = msg.sender_type === 'system';
    const isAgent = msg.sender_type === 'agent';

    // System/notification messages
    if (isSystem || msg.msg_type === 'notification') {
      return (
        <div key={msg.id} style={{ display: 'flex', justifyContent: 'center', marginBottom: 12, padding: '0 16px' }}>
          <div
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12,
              padding: '6px 14px',
              maxWidth: '80%',
            }}
          >
            {msg.msg_type === 'notification' && msg.metadata?.task && (
              <TaskMessageCard metadata={msg.metadata} />
            )}
            <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
              {msg.content}
            </Text>
          </div>
        </div>
      );
    }

    return (
      <div
        key={msg.id}
        style={{
          display: 'flex',
          justifyContent: own ? 'flex-end' : 'flex-start',
          marginBottom: 16,
          padding: '0 16px',
        }}
      >
        {!own && (
          <Avatar
            icon={isAgent ? <RobotOutlined /> : <UserOutlined />}
            style={{
              marginRight: 8,
              background: isAgent ? '#52c41a' : '#1677ff',
              flexShrink: 0,
              marginTop: 2,
            }}
          />
        )}
        <div style={{ maxWidth: 500 }}>
          <div style={{ marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>{msg.sender_name}</Text>
            {isAgent && (
              <Tag color="green" style={{ marginLeft: 0, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>
                AI
              </Tag>
            )}
            {msg.mentions?.includes(currentUserName || currentDisplayName || '') && (
              <BellOutlined style={{ color: '#faad14', fontSize: 12 }} />
            )}
          </div>
          <div
            style={{
              padding: '8px 12px',
              borderRadius: own ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
              background: own ? '#1677ff' : 'rgba(255,255,255,0.08)',
              color: own ? '#fff' : 'inherit',
            }}
          >
            {msg.msg_type === 'file' && msg.metadata?.file ? (
              <FileMessageCard metadata={msg.metadata} />
            ) : msg.msg_type === 'task' && msg.metadata?.task ? (
              <TaskMessageCard metadata={msg.metadata} />
            ) : (
              <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {renderContentWithMentions(msg.content, currentDisplayName || currentUserName)}
              </div>
            )}
          </div>
          <Text type="secondary" style={{ fontSize: 10, marginTop: 2, display: 'block' }}>
            {msg.created_at ? new Date(msg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : ''}
          </Text>
        </div>
      </div>
    );
  };

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '16px 0' }}>
      {messages.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Empty description={currentSessionId ? '暂无 Session 消息' : '暂无消息，发送一条开始对话'} />
        </div>
      ) : (
        messages.map(renderMessageBubble)
      )}
      <div ref={messagesEndRef} />
    </div>
  );
});

MessageList.displayName = 'MessageList';

export default MessageList;
