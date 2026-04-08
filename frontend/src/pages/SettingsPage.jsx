import { useState, useEffect } from 'react';
import { Save, RefreshCw } from 'lucide-react';
import api from '../api/client';

export default function SettingsPage() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({ llm_model: '', confidence_threshold: 0.8, retrieval_top_k: 5 });

  useEffect(() => {
    api.get('/config/').then(res => {
      setConfig(res.data);
      setForm({
        llm_model: res.data.llm_model,
        confidence_threshold: res.data.confidence_threshold,
        retrieval_top_k: res.data.retrieval_top_k,
      });
    }).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.patch('/config/', form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex justify-center p-8"><p className="text-gray-500">Loading settings...</p></div>;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">LLM Model</label>
          <input
            type="text" value={form.llm_model}
            onChange={e => setForm({...form, llm_model: e.target.value})}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="e.g. gpt-4o-mini, claude-3-haiku-20240307"
          />
          <p className="text-xs text-gray-400 mt-1">OpenRouter model identifier. Changes take effect on next question.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Confidence Threshold: {(form.confidence_threshold * 100).toFixed(0)}%
          </label>
          <input
            type="range" min="0" max="1" step="0.05"
            value={form.confidence_threshold}
            onChange={e => setForm({...form, confidence_threshold: parseFloat(e.target.value)})}
            className="w-full"
          />
          <p className="text-xs text-gray-400 mt-1">Below this threshold, questions are escalated to engineers.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Retrieval Top-K</label>
          <input
            type="number" min="1" max="20" value={form.retrieval_top_k}
            onChange={e => setForm({...form, retrieval_top_k: parseInt(e.target.value) || 5})}
            className="w-32 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 mt-1">Number of document chunks retrieved per question.</p>
        </div>

        <div className="flex items-center gap-3 pt-4 border-t">
          <button onClick={handleSave} disabled={saving}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
            <Save size={16} />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          {saved && <span className="text-sm text-green-600">Settings saved successfully!</span>}
        </div>

        {config && (
          <div className="pt-4 border-t">
            <p className="text-xs text-gray-400">Embedding model: {config.embedding_model} (restart required to change)</p>
          </div>
        )}
      </div>
    </div>
  );
}
