import { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, Send, ChevronDown, ChevronUp } from 'lucide-react';
import api from '../api/client';

export default function EscalationsPage() {
  const [escalations, setEscalations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending');
  const [responseText, setResponseText] = useState({});
  const [submitting, setSubmitting] = useState(null);
  const [expanded, setExpanded] = useState(null);

  const fetchEscalations = () => {
    setLoading(true);
    const params = filter !== 'all' ? { status_filter: filter } : {};
    api.get('/escalations/', { params }).then(res => setEscalations(res.data)).finally(() => setLoading(false));
  };

  useEffect(() => { fetchEscalations(); }, [filter]);

  const handleRespond = async (id) => {
    const text = responseText[id];
    if (!text?.trim()) return;
    setSubmitting(id);
    try {
      await api.post(`/escalations/${id}/respond`, { response: text.trim() });
      setResponseText(prev => ({ ...prev, [id]: '' }));
      fetchEscalations();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to submit response');
    } finally {
      setSubmitting(null);
    }
  };

  if (loading) return <div className="flex justify-center p-8"><p className="text-gray-500">Loading escalations...</p></div>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Escalations</h1>
        <div className="flex gap-2">
          {['pending', 'resolved', 'all'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                filter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >{f.charAt(0).toUpperCase() + f.slice(1)}</button>
          ))}
        </div>
      </div>

      {escalations.length === 0 ? (
        <p className="text-gray-500 text-center py-12">No {filter !== 'all' ? filter : ''} escalations.</p>
      ) : (
        <div className="space-y-4">
          {escalations.map(esc => (
            <div key={esc.id} className="bg-white rounded-lg shadow-sm border p-5">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <p className="font-medium text-gray-800">{esc.question_text}</p>
                  <p className="text-xs text-gray-400 mt-1">From: {esc.asked_by_name} • {new Date(esc.created_at).toLocaleString()}</p>
                </div>
                {esc.status === 'pending' ?
                  <span className="flex items-center gap-1 text-xs font-medium text-amber-600 bg-amber-50 px-2 py-1 rounded-full"><AlertTriangle size={12} />Pending</span> :
                  <span className="flex items-center gap-1 text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded-full"><CheckCircle size={12} />Resolved</span>
                }
              </div>

              {esc.retrieved_context && esc.retrieved_context.length > 0 && (
                <div className="mb-3">
                  <button onClick={() => setExpanded(expanded === esc.id ? null : esc.id)}
                    className="text-xs text-blue-600 flex items-center gap-1 mb-1"
                  >
                    {expanded === esc.id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    Retrieved context ({esc.retrieved_context.length} chunks)
                  </button>
                  {expanded === esc.id && (
                    <div className="space-y-2 mt-2">
                      {esc.retrieved_context.map((ctx, i) => (
                        <div key={i} className="text-xs bg-gray-50 p-3 rounded border">
                          <div className="font-medium text-gray-600 mb-1">{ctx.document_title} — p.{ctx.page_number} (similarity: {(ctx.similarity * 100).toFixed(1)}%)</div>
                          <p className="text-gray-500 line-clamp-3">{ctx.text}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {esc.status === 'resolved' && esc.engineer_response && (
                <div className="bg-green-50 p-3 rounded mt-3">
                  <p className="text-sm font-medium text-green-700 mb-1">Engineer Response</p>
                  <p className="text-gray-700 text-sm">{esc.engineer_response}</p>
                </div>
              )}

              {esc.status === 'pending' && (
                <div className="mt-4 flex gap-2">
                  <textarea
                    value={responseText[esc.id] || ''}
                    onChange={(e) => setResponseText(prev => ({ ...prev, [esc.id]: e.target.value }))}
                    placeholder="Type your response..."
                    className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[80px]"
                  />
                  <button
                    onClick={() => handleRespond(esc.id)}
                    disabled={!responseText[esc.id]?.trim() || submitting === esc.id}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 self-end flex items-center gap-1"
                  >
                    <Send size={14} />
                    {submitting === esc.id ? 'Sending...' : 'Reply'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
