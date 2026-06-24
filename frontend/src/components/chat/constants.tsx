import React from 'react';
import { Tag } from 'antd';

// ─── Role color maps ────────────────────────────────────────────
export const roleColorMap: Record<string, string> = {
  owner: 'gold',
  lead: 'blue',
  admin: 'purple',
  member: 'default',
  viewer: 'default',
};

export const roleLabelMap: Record<string, string> = {
  owner: '群主',
  lead: '队长',
  admin: '管理员',
  member: '成员',
  viewer: '观察者',
};

export const statusColorMap: Record<string, string> = {
  pending: 'default',
  assigned: 'processing',
  in_progress: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
};

export const statusLabelMap: Record<string, string> = {
  pending: '待处理',
  assigned: '已分配',
  in_progress: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export const priorityColorMap: Record<string, string> = {
  low: 'default',
  medium: 'blue',
  high: 'orange',
  critical: 'red',
};

export const priorityLabelMap: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '紧急',
};

// ─── Mention highlight renderer ─────────────────────────────────
export const renderContentWithMentions = (content: string, currentUserName?: string) => {
  const parts = content.split(/(@\S+)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('@')) {
      const isMe = currentUserName && part.toLowerCase() === `@${currentUserName.toLowerCase()}`;
      return (
        <span
          key={idx}
          style={{
            color: isMe ? '#1677ff' : '#52c41a',
            fontWeight: isMe ? 600 : 500,
            cursor: 'pointer',
          }}
        >
          {part}
        </span>
      );
    }
    return <span key={idx}>{part}</span>;
  });
};

// ─── Status Tag helper ──────────────────────────────────────────
export const StatusTag: React.FC<{ status: string; style?: React.CSSProperties }> = ({ status, style }) => (
  <Tag color={statusColorMap[status]} style={{ fontSize: 10, ...style }}>
    {statusLabelMap[status] || status}
  </Tag>
);

// ─── Priority Tag helper ───────────────────────────────────────
export const PriorityTag: React.FC<{ priority: string; style?: React.CSSProperties }> = ({ priority, style }) => (
  <Tag color={priorityColorMap[priority]} style={{ fontSize: 10, ...style }}>
    {priorityLabelMap[priority] || priority}
  </Tag>
);
