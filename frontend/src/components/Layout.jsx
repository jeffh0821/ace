import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LogOut, MessageSquare, Clock, AlertTriangle, FileText, Users, BarChart3, Settings } from 'lucide-react';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navLink = (to, label, icon) => {
    const active = location.pathname === to;
    const Icon = icon;
    return (
      <Link
        to={to}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          active ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`}
      >
        <Icon size={16} />
        {label}
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
          <div className="flex items-center gap-1">
            <Link to="/" className="text-xl font-bold text-blue-600 mr-4">ACE</Link>
            {navLink('/', 'Ask', MessageSquare)}
            {navLink('/history', 'History', Clock)}
            {(user?.role === 'engineer' || user?.role === 'admin') && (
              <>
                {navLink('/escalations', 'Escalations', AlertTriangle)}
                {navLink('/documents', 'Documents', FileText)}
              </>
            )}
            {user?.role === 'admin' && (
              <>
                {navLink('/users', 'Users', Users)}
                {navLink('/analytics', 'Analytics', BarChart3)}
                {navLink('/settings', 'Settings', Settings)}
              </>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{user?.display_name} <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">{user?.role}</span></span>
            <button onClick={handleLogout} className="flex items-center gap-1 text-sm text-red-600 hover:text-red-800">
              <LogOut size={14} />
              Logout
            </button>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
