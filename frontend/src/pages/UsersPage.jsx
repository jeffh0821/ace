import { useState, useEffect } from 'react';
import { UserPlus, UserX, Shield, Wrench, ShoppingBag } from 'lucide-react';
import api from '../api/client';

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ username: '', email: '', display_name: '', password: '', role: 'sales' });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const fetchUsers = () => {
    api.get('/users/').then(res => setUsers(res.data)).finally(() => setLoading(false));
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    try {
      await api.post('/users/', form);
      setForm({ username: '', email: '', display_name: '', password: '', role: 'sales' });
      setShowForm(false);
      fetchUsers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setCreating(false);
    }
  };

  const handleDeactivate = async (id, username) => {
    if (!confirm(`Deactivate user "${username}"?`)) return;
    try {
      await api.patch(`/users/${id}/deactivate`);
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to deactivate');
    }
  };

  const roleIcon = (role) => {
    switch (role) {
      case 'admin': return <Shield size={14} className="text-purple-500" />;
      case 'engineer': return <Wrench size={14} className="text-blue-500" />;
      case 'sales': return <ShoppingBag size={14} className="text-green-500" />;
      default: return null;
    }
  };

  if (loading) return <div className="flex justify-center p-8"><p className="text-gray-500">Loading users...</p></div>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">User Management</h1>
        <button onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center gap-2">
          <UserPlus size={16} /> Add User
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Create New User</h2>
          {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <input type="text" value={form.username} onChange={e => setForm({...form, username: e.target.value})}
                className="w-full border rounded-lg px-3 py-2 text-sm" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})}
                className="w-full border rounded-lg px-3 py-2 text-sm" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
              <input type="text" value={form.display_name} onChange={e => setForm({...form, display_name: e.target.value})}
                className="w-full border rounded-lg px-3 py-2 text-sm" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})}
                className="w-full border rounded-lg px-3 py-2 text-sm" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
              <select value={form.role} onChange={e => setForm({...form, role: e.target.value})}
                className="w-full border rounded-lg px-3 py-2 text-sm">
                <option value="sales">Sales</option>
                <option value="engineer">Engineer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="flex items-end">
              <button type="submit" disabled={creating}
                className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm">
                {creating ? 'Creating...' : 'Create User'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">User</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Role</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {users.map(u => (
              <tr key={u.id} className={`hover:bg-gray-50 ${!u.is_active ? 'opacity-50' : ''}`}>
                <td className="px-4 py-3">
                  <p className="font-medium text-sm">{u.display_name}</p>
                  <p className="text-xs text-gray-400">{u.username} • {u.email}</p>
                </td>
                <td className="px-4 py-3">
                  <span className="flex items-center gap-1.5 text-sm capitalize">
                    {roleIcon(u.role)} {u.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-1 rounded-full ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {u.is_active && (
                    <button onClick={() => handleDeactivate(u.id, u.username)} className="text-red-500 hover:text-red-700" title="Deactivate">
                      <UserX size={16} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
