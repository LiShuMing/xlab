import { useEffect, useState } from 'react';
import { useDocuments } from '../hooks/useDocuments';
import DocumentCard from '../components/DocumentCard';
import ReaderView from '../components/ReaderView';
import type { Document } from '../types';

export default function LibraryPage() {
  const { documents, loading, loadDocuments, deleteDoc } = useDocuments();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const filteredDocs = documents.filter(doc => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      doc.title.toLowerCase().includes(query) ||
      doc.topics.some(t => t.toLowerCase().includes(query)) ||
      doc.content?.toLowerCase().includes(query)
    );
  });

  if (selectedDoc) {
    return (
      <ReaderView
        document={selectedDoc}
        onBack={() => setSelectedDoc(null)}
      />
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Search Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">知识库</h2>
        <div className="relative max-w-md">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索文章、主题..."
            className="input pl-10"
          />
          <svg 
            className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* Document List */}
      {loading && documents.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <svg className="animate-spin h-8 w-8 text-primary-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <p className="text-gray-500">加载中...</p>
          </div>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="text-6xl mb-4">📚</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {searchQuery ? '没有找到匹配的内容' : '知识库为空'}
            </h3>
            <p className="text-gray-500 mb-4">
              {searchQuery 
                ? '试试其他搜索词' 
                : '捕获你的第一篇文章或想法吧'}
            </p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="grid gap-4">
            {filteredDocs.map(doc => (
              <DocumentCard
                key={doc.id}
                document={doc}
                onClick={() => setSelectedDoc(doc)}
                onDelete={() => deleteDoc(doc.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Stats Footer */}
      <div className="mt-4 pt-4 border-t border-gray-200 text-sm text-gray-500">
        共 {documents.length} 篇文章，{documents.filter(d => d.status === 'analyzed').length} 篇已分析
      </div>
    </div>
  );
}
