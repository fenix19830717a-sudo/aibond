import React, { useState } from 'react';
import { Input, Button, Upload, Space, message } from 'antd';
import { SendOutlined, PaperClipOutlined } from '@ant-design/icons';

// ─── Props ──────────────────────────────────────────────────────
export interface MessageInputProps {
  currentGroupId: string | null;
  currentSessionId: string | null;
  userId: string | undefined;
  onSend: (content: string) => Promise<void>;
  onFileUpload: (file: File) => Promise<boolean>;
}

// ─── MessageInput component ─────────────────────────────────────
const MessageInput: React.FC<MessageInputProps> = React.memo(({
  currentGroupId,
  currentSessionId,
  userId,
  onSend,
  onFileUpload,
}) => {
  const [inputValue, setInputValue] = useState('');

  const handleSend = async () => {
    if (!inputValue.trim() || !currentGroupId || !userId) return;
    const content = inputValue.trim();
    try {
      await onSend(content);
      setInputValue('');
    } catch (err) {
      console.error('Failed to send message:', err);
      // 不清空输入框，让用户可以重试
    }
  };

  const handleFileUpload = async (file: File) => {
    if (!currentGroupId || !userId) {
      message.error('请先选择群组');
      return false;
    }
    try {
      await onFileUpload(file);
    } catch (err: any) {
      message.error(err.message || '文件上传失败');
    }
    return false; // prevent default upload
  };

  return (
    <div style={{ padding: '12px 16px 0', borderTop: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
      <Space.Compact style={{ width: '100%' }}>
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onPressEnter={handleSend}
          placeholder={currentSessionId ? '发送 Session 消息...' : '输入消息...'}
          size="large"
        />
        <Upload
          beforeUpload={handleFileUpload}
          showUploadList={false}
        >
          <Button icon={<PaperClipOutlined />} size="large" />
        </Upload>
        <Button type="primary" icon={<SendOutlined />} size="large" onClick={handleSend} />
      </Space.Compact>
    </div>
  );
});

MessageInput.displayName = 'MessageInput';

export default MessageInput;
