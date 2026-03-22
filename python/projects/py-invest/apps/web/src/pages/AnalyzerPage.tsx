import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Button,
  Space,
  message,
  Spin,
  Divider,
  Row,
  Col,
  Collapse,
} from 'antd';
import { SearchOutlined, RocketOutlined } from '@ant-design/icons';
import { stockApi, AnalysisResponse } from '@/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const AnalyzerPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<string>('');
  const [duration, setDuration] = useState(0);

  const handleAnalyze = async (values: { stock_code: string; query: string }) => {
    setLoading(true);
    setReport('');

    try {
      const response: AnalysisResponse = await stockApi.analyze({
        stock_code: values.stock_code,
        query: values.query || '请进行全面分析并给出投资建议',
      });

      if (response.success) {
        setReport(response.report || '');
        setDuration(response.duration);
        message.success(`分析完成！耗时 ${response.duration.toFixed(1)}秒`);
      } else {
        message.error(response.error || '分析失败');
      }
    } catch (error: any) {
      message.error(`分析失败：${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickView = async (stockCode: string) => {
    try {
      const priceData = await stockApi.getPrice(stockCode);
      if (priceData.success) {
        const data = priceData.data;
        message.info(
          `${data.name} 当前价格：${data.current_price.toFixed(2)} ${data.currency}，` +
            `涨跌幅：${data.change_percent > 0 ? '+' : ''}${data.change_percent}%`
        );
      }
    } catch (error: any) {
      message.error('获取价格失败');
    }
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <Card
        title={
          <Space>
            <RocketOutlined style={{ color: '#1890ff' }} />
            <span>股票分析</span>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleAnalyze}
          initialValues={{
            query: '请进行全面分析并给出投资建议',
          }}
        >
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="stock_code"
                label="股票代码"
                rules={[{ required: true, message: '请输入股票代码' }]}
                placeholder="如：sh600519, sz000001, AAPL"
              >
                <Input
                  prefix={<SearchOutlined />}
                  placeholder="输入股票代码"
                  onPressEnter={() => form.submit()}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="query" label="分析要求">
                <Input placeholder="请输入具体分析要求（可选）" />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item label=" ">
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  block
                  size="large"
                >
                  开始分析
                </Button>
              </Form.Item>
            </Col>
          </Row>
        </Form>

        <Divider />

        <Space wrap>
          <span style={{ color: '#666' }}>快速查看:</span>
          <Button size="small" onClick={() => handleQuickView('sh600519')}>
            贵州茅台
          </Button>
          <Button size="small" onClick={() => handleQuickView('sz000001')}>
            平安银行
          </Button>
          <Button size="small" onClick={() => handleQuickView('AAPL')}>
            苹果
          </Button>
          <Button size="small" onClick={() => handleQuickView('TSLA')}>
            特斯拉
          </Button>
        </Space>
      </Card>

      {loading && (
        <Card style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" tip="正在分析股票数据，请稍候..." />
          <div style={{ marginTop: 24, color: '#666' }}>
            正在获取股价、K 线、财务指标、市场新闻...
          </div>
        </Card>
      )}

      {report && !loading && (
        <Card
          title={`分析报告 - 耗时 ${duration.toFixed(1)}秒`}
          extra={
            <Button onClick={() => {}}>
              导出报告
            </Button>
          }
        >
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {report}
            </ReactMarkdown>
          </div>
        </Card>
      )}
    </div>
  );
};

export default AnalyzerPage;
