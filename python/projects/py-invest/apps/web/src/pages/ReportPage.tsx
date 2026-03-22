import React from 'react';
import { useParams } from 'react-router-dom';
import { Card, Empty } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const ReportPage: React.FC = () => {
  const { id } = useParams();

  // TODO: 从 API 获取报告
  const reportContent = `# 报告页面

报告 ID: ${id}

> 此页面正在开发中，将展示历史分析报告。
`;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <Card title="分析报告">
        <div className="markdown-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {reportContent}
          </ReactMarkdown>
        </div>
      </Card>
    </div>
  );
};

export default ReportPage;
