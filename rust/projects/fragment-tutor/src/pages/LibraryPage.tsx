import { useEffect, useState } from 'react';
import { Database, Loader2, Search } from 'lucide-react';
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
    <div className="flex h-full flex-col">
      {/* Search Header */}
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">知识库</h2>
          <p className="mt-1 text-sm text-slate-500">沉淀已捕获材料、分析结果和复习来源。</p>
        </div>
        <div className="relative w-full max-w-md">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索文章、主题..."
            className="input pl-10"
          />
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </div>
      </div>

      {/* Document List */}
      {loading && documents.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-cyan-600" />
            <p className="text-slate-500">加载中...</p>
          </div>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="panel max-w-md p-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-md bg-slate-950 text-white">
              <Database className="h-6 w-6" />
            </div>
            <h3 className="mb-2 text-lg font-medium text-slate-950">
              {searchQuery ? '没有找到匹配的内容' : '知识库为空'}
            </h3>
            <p className="mb-4 text-slate-500">
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
      <div className="mt-4 border-t border-slate-200 pt-4 text-sm text-slate-500">
        共 {documents.length} 篇文章，{documents.filter(d => d.status === 'analyzed').length} 篇已分析
      </div>
    </div>
  );
}
