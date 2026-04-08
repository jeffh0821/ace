import { useState } from 'react';
import { ThumbsUp, ThumbsDown, AlertTriangle, Send, Loader2 } from 'lucide-react';
import api from '../api/client';

export default function AskPage() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [feedbackGiven, setFeedbackGiven] = useState(false);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setResult(null);
    setFeedbackGiven(false);
    try {
      const res = await api.post('/questions/', { question: question.trim() });
      setResult(res.data);
    } catch (err) {
      setResult({ error: err.response?.data?.detail || 'Failed to get answer' });
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (positive) => {
    if (!result?.id || feedbackGiven) return;
    try {
      await api.post('/feedback/', { question_id: result.id, positive });
      setFeedbackGiven(true);
    } catch {}
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Ask a Question</h1>

      <form onSubmit={handleAsk} className="mb-8">
        <div className="flex gap-2">
          <input
            type="text" value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about connectors, specifications, compatibility..."
            className="flex-1 border rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button
            type="submit" disabled={loading || !question.trim()}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            {loading ? 'Thinking...' : 'Ask'}
          </button>
        </div>
      </form>

      {result && !result.error && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          {result.status === 'escalated' ? (
            <div className="flex items-center gap-3 text-amber-600">
              <AlertTriangle size={24} />
              <div>
                <p className="font-medium">Question Escalated</p>
                <p className="text-sm text-gray-500">
                  Your question has been sent to an engineer for review.
                  Check back later for a response.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="prose max-w-none mb-4">
                <p className="text-gray-800 leading-relaxed">{result.answer_text}</p>
              </div>

              {result.citations && result.citations.length > 0 && (
                <div className="border-t pt-4 mt-4">
                  <h3 className="text-sm font-medium text-gray-500 mb-2">Sources</h3>
                  {result.citations.map((cite, i) => (
                    <div key={i} className="text-sm bg-gray-50 rounded p-3 mb-2">
                      <span className="font-medium">{cite.document_title}</span>
                      <span className="text-gray-400"> — p.{cite.page_number}</span>
                      <p className="text-gray-600 mt-1 italic">"{cite.excerpt}"</p>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-4 mt-4 border-t pt-4">
                <span className="text-sm text-gray-500">Was this helpful?</span>
                <button
                  onClick={() => handleFeedback(true)}
                  disabled={feedbackGiven}
                  className={`p-2 rounded hover:bg-green-50 ${feedbackGiven ? 'opacity-50' : ''}`}
                >
                  <ThumbsUp size={18} className="text-green-600" />
                </button>
                <button
                  onClick={() => handleFeedback(false)}
                  disabled={feedbackGiven}
                  className={`p-2 rounded hover:bg-red-50 ${feedbackGiven ? 'opacity-50' : ''}`}
                >
                  <ThumbsDown size={18} className="text-red-600" />
                </button>
                {feedbackGiven && <span className="text-sm text-green-600">Thanks for the feedback!</span>}
              </div>
            </>
          )}
        </div>
      )}

      {result?.error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">{result.error}</div>
      )}
    </div>
  );
}
