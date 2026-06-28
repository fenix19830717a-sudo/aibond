import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Typography, Spin, Empty, Input, Tag, Space, Statistic, Badge, Button,
} from 'antd';
import {
  AppstoreOutlined, ApiOutlined, SearchOutlined, ToolOutlined, ThunderboltOutlined, CodeOutlined, DatabaseOutlined, CloudOutlined, FileTextOutlined, SafetyCertificateOutlined, RobotOutlined, MessageOutlined, PictureOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Title, Text, Paragraph } = Typography;

interface ToolInfo {
  name: string;
  description: string;
  category: string;
  tier: string;
  icon?: string;
}

const categoryIcons: Record<string, React.ReactNode> = {
  'core': <ToolOutlined />,
  'communication': <MessageOutlined />,
  'data': <DatabaseOutlined />,
  'ai': <RobotOutlined />,
  'media': <PictureOutlined />,
  'utility': <ThunderboltOutlined />,
  'dev': <CodeOutlined />,
  'cloud': <CloudOutlined />,
  'security': <SafetyCertificateOutlined />,
  'file': <FileTextOutlined />,
};

const categoryLabels: Record<string, string> = {
  'core': '核心工具',
  'communication': '通讯工具',
  'data': '数据处理',
  'ai': 'AI 工具',
  'media': '媒体工具',
  'utility': '实用工具',
  'dev': '开发工具',
  'cloud': '云服务',
  'security': '安全工具',
  'file': '文件工具',
};

const tierColors: Record<string, string> = {
  'free': 'green',
  'basic': 'blue',
  'pro': 'purple',
  'enterprise': 'gold',
};

const SkillsMarket: React.FC = () => {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [manifestData, statsData] = await Promise.all([
        api.getHubManifest(),
        api.getHubStats().catch(() => null),
      ]);
      const toolList = Array.isArray(manifestData) ? manifestData : (manifestData?.tools || manifestData?.value || []);
      setTools(toolList);
      setStats(statsData);
    } catch (err: any) {
      // Fallback: show mock data if API not available
      console.warn('Hub manifest not available, showing placeholder:', err.message);
      setTools([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  const filteredTools = tools.filter((tool) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      tool.name.toLowerCase().includes(s) ||
      tool.description.toLowerCase().includes(s) ||
      tool.category.toLowerCase().includes(s)
    );
  });

  const toolsByCategory = filteredTools.reduce<Record<string, ToolInfo[]>>((acc, tool) => {
    const cat = tool.category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(tool);
    return acc;
  }, {});

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}><AppstoreOutlined style={{ marginRight: 8 }} />Skills 市场</Title>
      </div>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={8} sm={6}>
            <Card size="small">
              <Statistic title="工具总数" value={stats.total_tools || tools.length} prefix={<ApiOutlined />} />
            </Card>
          </Col>
          <Col xs={8} sm={6}>
            <Card size="small">
              <Statistic title="分类数" value={stats.total_categories || Object.keys(toolsByCategory).length} prefix={<AppstoreOutlined />} />
            </Card>
          </Col>
          <Col xs={8} sm={6}>
            <Card size="small">
              <Statistic title="调用次数" value={stats.total_calls || 0} prefix={<ThunderboltOutlined />} />
            </Card>
          </Col>
        </Row>
      )}

      <Card style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索工具（名称、描述、分类）..."
          prefix={<SearchOutlined />}
          allowClear
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          size="large"
        />
      </Card>

      {filteredTools.length === 0 ? (
        <Card>
          <Empty description={search ? '没有匹配的工具' : '暂无工具数据，请确认 Hub 服务是否可用'}>
            <Button onClick={loadData}>重新加载</Button>
          </Empty>
        </Card>
      ) : (
        Object.entries(toolsByCategory).map(([category, categoryTools]) => (
          <Card
            key={category}
            title={
              <Space>
                <span style={{ color: '#1677ff' }}>{categoryIcons[category] || <ToolOutlined />}</span>
                <span>{categoryLabels[category] || category}</span>
                <Badge count={categoryTools.length} style={{ backgroundColor: '#1677ff' }} />
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Row gutter={[12, 12]}>
              {categoryTools.map((tool) => (
                <Col xs={24} sm={12} md={8} lg={6} key={tool.name}>
                  <Card
                    size="small"
                    hoverable
                    style={{ height: '100%' }}
                  >
                    <Space direction="vertical" style={{ width: '100%' }} size={4}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <Text strong style={{ fontSize: 14 }}>{tool.name}</Text>
                        <Tag color={tierColors[tool.tier] || 'default'} style={{ fontSize: 11 }}>
                          {tool.tier || 'free'}
                        </Tag>
                      </div>
                      <Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ fontSize: 12, marginBottom: 0 }}>
                        {tool.description}
                      </Paragraph>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        ))
      )}
    </div>
  );
};

export default SkillsMarket;
