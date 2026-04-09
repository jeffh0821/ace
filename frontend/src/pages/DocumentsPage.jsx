import { useState, useEffect, useRef } from 'react';
import { Upload, FileText, Trash2, CheckCircle, Clock, AlertCircle, Loader2, Pencil } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import api from '../api/client';

export default function DocumentsPage() {
  const { user } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const fileRef = useRef(null);

  const fetchDocs = () => {
    api.get('/documents/').then(res => setDocuments(res.data)).finally(() => setLoading(false));
  };

  useEffect(() => { fetchDocs(); }, []);

  // Auto-refresh while any doc is processing
  useEffect(() => {
    const hasProcessing = documents.some(d => d.status === 'pending' || d.status === 'processing');
    if (hasProcessing) {
      const interval = setInterval(fetchDocs, 5000);
      return () => clearInterval(interval);
    }
  }, [documents]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      await api.post('/documents/', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      fetchDocs();
    } catch (err) {
      alert(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleDelete = async (id, title) => {
    if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/documents/${id}`);
      fetchDocs();
    } catch (err) {
      alert(err.response?.data?.detail || 'Delete failed');
    }
  };

  const startEdit = (doc) => {
    setEditingId(doc.id);
    setEditTitle(doc.title);
  };

  const saveEdit = async (id) => {
    if (!editTitle.trim()) {
      alert('Title cannot be empty');
      return;
    }
    try {
      await api.patch(`/documents/${id}`, { title: editTitle.trim() });
      setEditingId(null);
      fetchDocs();
    } catch (err) {
      alert(err.response?.data?.detail || 'Update failed');
    }
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditTitle('');
  };

  const statusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircle size={16} className="text-green-500" />;
      case 'processing': return <Loader2 size={16} className="text-blue-500 animate-spin" />;
      case 'pending': return <Clock size={16} className="text-gray-400" />;
      case 'failed': return <AlertCircle size={16} className="text-red-500" />;
      default: return null;
    }
  };

  if (loading) return <div className="flex justify-center p-8"><p className="text-gray-500">Loading documents...</p></div>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Documents</h1>
        <label className={`bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 cursor-pointer flex items-center gap-2 ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
          {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          {uploading ? 'Uploading...' : 'Upload PDF'}
          <input ref={fileRef} type="file" accept=".pdf" onChange={handleUpload} className="hidden" />
        </label>
      </div>

      {documents.length === 0 ? (
        <p className="text-gray-500 text-center py-12">No documents uploaded yet.</p>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Document</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Pages</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Chunks</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Size</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Uploaded</th>
                {user?.role === 'admin' && <th className="px-4 py-3"></th>}
              </tr>
            </thead>
            <tbody className="divide-y">
              {documents.map(doc => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText size={16} className="text-gray-400" />
                      <div>
                        {editingId === doc.id ? (
                          <div className="flex items-center gap-1">
                            <input
                              type="text"
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              onKeyDown={(e) => e.key === 'Enter' && saveEdit(doc.id)}
                              className="border rounded px-2 py-1 text-sm w-48"
                              autoFocus
                            />
                            <button onClick={() => saveEdit(doc.id)} className="text-green-600 hover:text-green-800 text-xs">Save</button>
                            <button onClick={cancelEdit} className="text-gray-500 hover:text-gray-700 text-xs">Cancel</button>
                          </div>
                        ) : (
                          <>
                            <p className="font-medium text-sm">{doc.title}</p>
                            <p className="text-xs text-gray-400">{doc.filename}</p>
                          </>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      {statusIcon(doc.status)}
                      <span className="text-sm capitalize">{doc.status}</span>
                    </div>
                    {doc.error_message && <p className="text-xs text-red-500 mt-1 max-w-xs truncate">{doc.error_message}</p>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{doc.page_count ?? '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{doc.chunk_count || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{(doc.file_size_bytes / 1024 / 1024).toFixed(1)} MB</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{new Date(doc.uploaded_at).toLocaleDateString()}</td>
                  {user?.role === 'admin' && (
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {editingId !== doc.id && (
                          <button onClick={() => startEdit(doc)} className="text-gray-500 hover:text-blue-600" title="Edit title">
                            <Pencil size={16} />
                          </button>
                        )}
                        <button onClick={() => handleDelete(doc.id, doc.title)} className="text-red-500 hover:text-red-700" title="Delete">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
