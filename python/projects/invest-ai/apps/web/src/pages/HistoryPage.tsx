import React from 'react';
import { Card, Table, Tag, Button, Empty, Space } from 'antd';
import { FileTextOutlined, DeleteOutlined } from '@ant-design/icons';

interface HistoryRecord {
  key: string;
  stockCode: string;
  stockName: string;
  analyzeTime: string;
  rating: string;
  duration: number;
}

const HistoryPage: React.FC = () => {
  // TODO: 从 API 获取历史记录
  const dataSource: HistoryRecord[] = [];

  const columns = [
    {
      title: '股票代码',
      dataIndex: 'stockCode',
      key: 'stockCode',
    },
    {
      title: '股票名称',
      dataIndex: 'stockName',
      key: 'stockName',
    },
    {
      title: '分析时间',
      dataIndex: 'analyzeTime',
      key: 'analyzeTime',
    },
    {
      title: '评级',
      dataIndex: 'rating',
      key: 'rating',
      render: (rating: string) => {
        const colorMap: Record<string, string> = {
          '强烈推荐': 'red',
          '推荐': 'green',
          '中性': 'blue',
          '谨慎': 'orange',
          '不推荐': 'volcano',
        };
        return <Tag color={colorMap[rating] || 'default'}>{rating}</Tag>;
      },
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      render: (duration: number) => `${duration.toFixed(1)}秒`,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: HistoryRecord) => (
        <Space size="middle">
          <Button type="link" icon={<FileTextOutlined />}>
            查看
          </Button>
          <Button type="link" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <Card title="分析历史">
        {dataSource.length > 0 ? (
          <Table columns={columns} dataSource={dataSource} />
        ) : (
          <Empty description="暂无分析记录" />
        )}
      </Card>
    </div>
  );
};

export default HistoryPage;
