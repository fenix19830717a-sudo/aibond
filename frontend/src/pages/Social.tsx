import React, { useState, useEffect } from 'react';
import {
  Card, Button, List, Avatar, Typography, message, Space, Input, Form, Modal, Tabs, Tag, Empty, Spin, Tooltip, Select, Badge,
} from 'antd';
import {
  PlusOutlined, HeartOutlined, HeartFilled, CommentOutlined, UserOutlined, RobotOutlined, WechatOutlined, UserAddOutlined, CheckOutlined, CloseOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../store/authStore';
import { api } from '../api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const Social: React.FC = () => {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('moments');
  const [moments, setMoments] = useState<any[]>([]);
  const [friends, setFriends] = useState<any[]>([]);
  const [pendingRequests, setPendingRequests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [postModalOpen, setPostModalOpen] = useState(false);
  const [addFriendModalOpen, setAddFriendModalOpen] = useState(false);
  const [postForm] = Form.useForm();
  const [friendForm] = Form.useForm();
  const [posting, setPosting] = useState(false);
  const [commentModalOpen, setCommentModalOpen] = useState(false);
  const [commentMomentId, setCommentMomentId] = useState<string>('');
  const [commentForm] = Form.useForm();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      await Promise.all([loadMoments(), loadFriends(), loadPendingRequests()]);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadMoments = async () => {
    try {
      const data = await api.listMoments(0, 20);
      setMoments(Array.isArray(data) ? data : (data?.moments || data?.value || []));
    } catch (err) {
      console.error(err);
    }
  };

  const loadFriends = async () => {
    try {
      const data = await api.listFriends();
      setFriends(Array.isArray(data) ? data : (data?.friends || data?.value || []));
    } catch (err) {
      console.error(err);
    }
  };

  const loadPendingRequests = async () => {
    try {
      const data = await api.listFriends();
      const friendList = Array.isArray(data) ? data : (data?.friends || data?.value || []);
      setPendingRequests(friendList.filter((f: any) => f.status === 'pending'));
    } catch (err) {
      console.error(err);
    }
  };

  const handlePostMoment = async (values: any) => {
    setPosting(true);
    try {
      await api.postMoment(values.content, values.visibility || 'public');
      message.success('发布成功');
      setPostModalOpen(false);
      postForm.resetFields();
      loadMoments();
    } catch (err: any) {
      message.error(err.message || '发布失败');
    } finally {
      setPosting(false);
    }
  };

  const handleLikeMoment = async (momentId: string) => {
    try {
      await api.likeMoment(momentId);
      loadMoments();
    } catch (err: any) {
      message.error(err.message || '操作失败');
    }
  };

  const handleCommentMoment = async (values: any) => {
    try {
      await api.commentMoment(commentMomentId, values.content);
      message.success('评论成功');
      setCommentModalOpen(false);
      commentForm.resetFields();
      loadMoments();
    } catch (err: any) {
      message.error(err.message || '评论失败');
    }
  };

  const handleAddFriend = async (values: any) => {
    try {
      await api.requestFriend(values.target_id, values.target_type);
      message.success('好友请求已发送');
      setAddFriendModalOpen(false);
      friendForm.resetFields();
    } catch (err: any) {
      message.error(err.message || '请求失败');
    }
  };

  const handleAcceptFriend = async (requestId: string) => {
    try {
      await api.acceptFriend(requestId);
      message.success('已接受');
      loadData();
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const handleRejectFriend = async (requestId: string) => {
    try {
      await api.rejectFriend(requestId);
      message.success('已拒绝');
      loadData();
    } catch (err: any) {
      message.error(err.message);
    }
  };

  const openCommentModal = (momentId: string) => {
    setCommentMomentId(momentId);
    setCommentModalOpen(true);
  };

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}><Spin size="large" /></div>;
  }

  const momentsTab = {
    key: 'moments',
    label: '朋友圈',
    children: (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Title level={5} style={{ margin: 0 }}>动态</Title>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setPostModalOpen(true)}>发布动态</Button>
        </div>
        <List
          dataSource={moments}
          renderItem={(moment: any) => (
            <List.Item>
              <Card style={{ width: '100%' }} size="small">
                <div style={{ display: 'flex', gap: 12 }}>
                  <Avatar icon={<UserOutlined />} style={{ flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <Space>
                        <Text strong>{moment.author_name || moment.author_id || user?.username}</Text>
                        {moment.visibility && <Tag>{moment.visibility === 'public' ? '公开' : '好友可见'}</Tag>}
                      </Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>{moment.created_at ? new Date(moment.created_at).toLocaleString() : ''}</Text>
                    </div>
                    <Paragraph style={{ marginBottom: 8, color: 'rgba(255,255,255,0.85)' }}>{moment.content}</Paragraph>
                    <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                      <Tooltip title="点赞">
                        <Button
                          type="text"
                          size="small"
                          icon={moment.is_liked ? <HeartFilled style={{ color: '#ff4d4f' }} /> : <HeartOutlined />}
                          onClick={() => handleLikeMoment(moment.id)}
                        >
                          {moment.like_count || 0}
                        </Button>
                      </Tooltip>
                      <Tooltip title="评论">
                        <Button type="text" size="small" icon={<CommentOutlined />} onClick={() => openCommentModal(moment.id)}>
                          {moment.comment_count || 0}
                        </Button>
                      </Tooltip>
                    </div>
                    {moment.comments?.length > 0 && (
                      <div style={{ marginTop: 8, background: 'rgba(255,255,255,0.04)', borderRadius: 8, padding: '8px 12px' }}>
                        {moment.comments.map((c: any, idx: number) => (
                          <div key={idx} style={{ marginBottom: 4 }}>
                            <Text strong style={{ fontSize: 13 }}>{c.author_name || '匿名'}：</Text>
                            <Text style={{ fontSize: 13 }}>{c.content}</Text>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            </List.Item>
          )}
          locale={{ emptyText: <Empty description="暂无动态" /> }}
        />
      </div>
    ),
  };

  const friendsTab = {
    key: 'friends',
    label: `好友 (${friends.length})`,
    children: (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Title level={5} style={{ margin: 0 }}>好友列表</Title>
          <Button icon={<UserAddOutlined />} onClick={() => { setAddFriendModalOpen(true); }}>添加好友</Button>
        </div>

        {pendingRequests.length > 0 && (
          <Card size="small" title={<Badge count={pendingRequests.length} offset={[8, 0]}>好友请求</Badge>} style={{ marginBottom: 16 }}>
            <List
              dataSource={pendingRequests}
              renderItem={(req: any) => (
                <List.Item
                  actions={[
                    <Button type="primary" size="small" icon={<CheckOutlined />} onClick={() => handleAcceptFriend(req.id)}>接受</Button>,
                    <Button size="small" danger icon={<CloseOutlined />} onClick={() => handleRejectFriend(req.id)}>拒绝</Button>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={<Avatar icon={req.target_type === 'agent' ? <RobotOutlined /> : <UserOutlined />} />}
                    title={req.target_name || req.target_id}
                    description={`类型: ${req.target_type === 'agent' ? 'Agent' : '用户'} | 状态: 等待验证`}
                  />
                </List.Item>
              )}
            />
          </Card>
        )}

        <List
          grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
          dataSource={friends.filter((f: any) => f.status !== 'pending')}
          renderItem={(friend: any) => (
            <List.Item>
              <Card size="small" style={{ textAlign: 'center' }}>
                <Avatar size={48} icon={friend.target_type === 'agent' ? <RobotOutlined /> : <UserOutlined />} style={{ marginBottom: 8 }} />
                <div>
                  <Text strong>{friend.target_name || friend.target_id?.slice(0, 8)}</Text>
                  <br />
                  <Tag color={friend.target_type === 'agent' ? 'blue' : 'green'}>
                    {friend.target_type === 'agent' ? 'Agent' : '用户'}
                  </Tag>
                </div>
              </Card>
            </List.Item>
          )}
          locale={{ emptyText: '暂无好友' }}
        />
      </div>
    ),
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}><WechatOutlined style={{ marginRight: 8 }} />社交 & 朋友圈</Title>
      </div>
      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[momentsTab, friendsTab]} />
      </Card>

      <Modal title="发布动态" open={postModalOpen} onCancel={() => setPostModalOpen(false)} footer={null}>
        <Form form={postForm} onFinish={handlePostMoment} layout="vertical">
          <Form.Item name="content" label="内容" rules={[{ required: true, message: '请输入动态内容' }]}>
            <TextArea placeholder="分享你的想法..." rows={4} showCount maxLength={500} />
          </Form.Item>
          <Form.Item name="visibility" label="可见范围" initialValue="public">
            <Select style={{ width: '100%' }} options={[
              { value: 'public', label: '公开' },
              { value: 'friends', label: '好友可见' },
              { value: 'private', label: '仅自己可见' },
            ]} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={posting}>发布</Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="添加好友" open={addFriendModalOpen} onCancel={() => setAddFriendModalOpen(false)} footer={null}>
        <Form form={friendForm} onFinish={handleAddFriend} layout="vertical">
          <Form.Item name="target_type" label="类型" rules={[{ required: true }]} initialValue="agent">
            <Select style={{ width: '100%' }} options={[{ value: 'agent', label: 'AI Agent' }, { value: 'user', label: '用户' }]} />
          </Form.Item>
          <Form.Item name="target_id" label="ID" rules={[{ required: true, message: '请输入目标 ID' }]}>
            <Input placeholder="输入用户或 Agent 的 ID" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>发送请求</Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="评论" open={commentModalOpen} onCancel={() => setCommentModalOpen(false)} footer={null}>
        <Form form={commentForm} onFinish={handleCommentMoment} layout="vertical">
          <Form.Item name="content" label="评论内容" rules={[{ required: true, message: '请输入评论内容' }]}>
            <TextArea placeholder="写下你的评论..." rows={3} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>发表评论</Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Social;
