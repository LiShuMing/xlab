import { useCallback, useState } from 'react';
import { useStore } from '../store';
import { databaseService, captureService, anthropicService } from '../services';
import type { Document } from '../types';

export function useDocuments() {
  const { 
    documents, setDocuments, addDocument, removeDocument, 
    selectedDocument, setSelectedDocument,
    currentAnalysis, setCurrentAnalysis,
    isAnalyzing, setIsAnalyzing,
    apiKey 
  } = useStore();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const docs = await databaseService.getDocuments(100);
      setDocuments(docs);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, [setDocuments]);

  const captureUrl = useCallback(async (url: string, title?: string) => {
    setLoading(true);
    setError(null);
    try {
      const doc = await captureService.captureUrl(url, title);
      addDocument(doc);
      setSelectedDocument(doc);
      return doc;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to capture URL');
      throw e;
    } finally {
      setLoading(false);
    }
  }, [addDocument, setSelectedDocument]);

  const createNote = useCallback(async (title: string, content: string) => {
    setLoading(true);
    setError(null);
    try {
      const doc = await captureService.createNote(title, content);
      addDocument(doc);
      setSelectedDocument(doc);
      return doc;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create note');
      throw e;
    } finally {
      setLoading(false);
    }
  }, [addDocument, setSelectedDocument]);

  const deleteDoc = useCallback(async (id: string) => {
    try {
      await databaseService.deleteDocument(id);
      removeDocument(id);
      if (selectedDocument?.id === id) {
        setSelectedDocument(null);
        setCurrentAnalysis(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete document');
      throw e;
    }
  }, [removeDocument, selectedDocument, setSelectedDocument, setCurrentAnalysis]);

  const analyzeDocument = useCallback(async (doc: Document) => {
    if (!apiKey) {
      setError('Please set your API key in Settings');
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    try {
      const analysis = await anthropicService.quickDigest(doc.id, apiKey);
      setCurrentAnalysis(analysis);
      await databaseService.updateDocumentStatus(doc.id, 'analyzed');
      
      // Update local state
      setDocuments(documents.map(d => 
        d.id === doc.id ? { ...d, status: 'analyzed' } : d
      ));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to analyze document');
    } finally {
      setIsAnalyzing(false);
    }
  }, [apiKey, documents, setDocuments, setCurrentAnalysis, setIsAnalyzing, setError]);

  const loadAnalysis = useCallback(async (docId: string) => {
    try {
      const analysis = await anthropicService.getAnalysis(docId);
      setCurrentAnalysis(analysis);
    } catch (e) {
      console.error('Failed to load analysis:', e);
    }
  }, [setCurrentAnalysis]);

  return {
    documents,
    loading,
    error,
    selectedDocument,
    currentAnalysis,
    isAnalyzing,
    loadDocuments,
    captureUrl,
    createNote,
    deleteDoc,
    analyzeDocument,
    loadAnalysis,
    setSelectedDocument,
  };
}
