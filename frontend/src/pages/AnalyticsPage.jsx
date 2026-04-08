import { useState, useEffect } from 'react';
import { MessageSquare, AlertTriangle, ThumbsUp, FileText, Users, BarChart3, Target, TrendingUp } from 'lucide-react';
import api from '../api/client';

export default function AnalyticsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/analytics/').then(res => setData(res.data)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center p-8"><p className="text-gray-500">Loading analytics...</p></div>;
  if (!data) return <div className="text-red-500 text-center p-8">Failed to load analytics</div>;

  const cards = [
    { label: 'Total Questions', value: data.total_questions, icon: MessageSquare, color: 'blue' },
    { label: 'Answered Directly', value: data.answered_directly, icon: Target, color: 'green' },
    { label: 'Escalated', value: data.escalated, icon: AlertTriangle, color: 'amber' },
    { label: 'Pending Escalations', value: data.pending_escalations, icon: AlertTriangle, color: 'red' },
    { label: 'Escalation Rate', value: `${(data.escalation_rate * 100).toFixed(1)}%`, icon: TrendingUp, color: 'amber' },
    { label: 'Satisfaction Rate', value: `${(data.feedback_satisfaction_rate * 100).toFixed(1)}%`, icon: ThumbsUp, color: 'green' },
    { label: 'Avg Confidence', value: `${(data.average_confidence * 100).toFixed(1)}%`, icon: BarChart3, color: 'blue' },
    { label: 'Documents', value: data.document_count, icon: FileText, color: 'purple' },
    { label: 'Users', value: data.user_count, icon: Users, color: 'indigo' },
  ];

  const colorMap = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
    indigo: 'bg-indigo-50 text-indigo-600',
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Analytics Dashboard</h1>
      <div className="grid grid-cols-3 gap-4">
        {cards.map((card, i) => {
          const Icon = card.icon;
          return (
            <div key={i} className="bg-white rounded-lg shadow-sm border p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-gray-500">{card.label}</span>
                <div className={`p-2 rounded-lg ${colorMap[card.color]}`}>
                  <Icon size={16} />
                </div>
              </div>
              <p className="text-2xl font-bold">{card.value}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="bg-white rounded-lg shadow-sm border p-5">
          <h3 className="font-semibold mb-2">Feedback</h3>
          <p className="text-sm text-gray-500">Positive: <span className="font-medium text-green-600">{data.positive_feedback}</span></p>
          <p className="text-sm text-gray-500">Negative: <span className="font-medium text-red-600">{data.negative_feedback}</span></p>
        </div>
      </div>
    </div>
  );
}
