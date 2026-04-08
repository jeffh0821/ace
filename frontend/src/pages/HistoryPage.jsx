import { useState, useEffect } from 'react';
import { ThumbsUp, ThumbsDown, AlertTriangle, CheckCircle, Clock, MessageSquare } from 'lucide-react';
import api from '../api/client';

export default function HistoryPage() {
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    api.get('/questions/').then(res => setQuestions(res.data)).finally(() => setLoading(false));
  }, []);

  const statusBadge = (status) => {
    const styles = {
      answered: 'bg-green-100 text-green-700',
      escalated: 'bg-amber-100 text-amber-700',
      resolved: 'bg-blue-100 text-blue-700',
    };
    const icons = { answered: CheckCircle, escalated: AlertTriangle, resolved: MessageSquare };
    const Icon = icons[status] || Clock;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100'}`}>
        <Icon size={12} />
        {status}
      </span>
    );
  };

  if (loading) return <div className="flex justify-center p-8"><p className="text-gray-500">Loading history...</p></div>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Question History</h1>
      {questions.length === 0 ? (
        <p className="text-gray-500 text-center py-12">No questions asked yet.</p>
      ) : (
        <div className="space-y-3">
          {questions.map(q => (
            <div key={q.id} className="bg-white rounded-lg shadow-sm border p-4 cursor-pointer hover:border-blue-200 transition-colors"
              onClick={() => setExpanded(expanded === q.id ? null : q.id)}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <p className="font-medium text-gray-800">{q.question_text}</p>
                  <p className="text-xs text-gray-400 mt-1">{new Date(q.asked_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-2 ml-4">
                  {q.feedback_positive !== null && (
                    q.feedback_positive ? <ThumbsUp size={14} className="text-green-500" /> : <ThumbsDown size={14} className="text-red-500" />
                  )}
                  {statusBadge(q.status)}
                </div>
              </div>
              {expanded === q.id && (
                <div className="mt-4 pt-4 border-t">
                  {q.answer_text && (
                    <div className="mb-3">
                      <p className="text-sm font-medium text-gray-500 mb-1">Answer</p>
                      <p className="text-gray-700">{q.answer_text}</p>
                    </div>
                  )}
                  {q.engineer_response && (
                    <div className="mb-3 bg-blue-50 p-3 rounded">
                      <p className="text-sm font-medium text-blue-600 mb-1">Engineer Response</p>
                      <p className="text-gray-700">{q.engineer_response}</p>
                    </div>
                  )}
                  {q.citations && q.citations.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-gray-500 mb-1">Sources</p>
                      {q.citations.map((cite, i) => (
                        <div key={i} className="text-sm bg-gray-50 rounded p-2 mb-1">
                          <span className="font-medium">{cite.document_title}</span> — p.{cite.page_number}
                        </div>
                      ))}
                    </div>
                  )}
                  {q.confidence_score !== null && (
                    <p className="text-xs text-gray-400 mt-2">Confidence: {(q.confidence_score * 100).toFixed(1)}%</p>
                  )}
                  {q.status === 'escalated' && (
                    <p className="text-sm text-amber-600 mt-2">Waiting for engineer response...</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
