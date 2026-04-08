import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import AskPage from './pages/AskPage';
import HistoryPage from './pages/HistoryPage';
import EscalationsPage from './pages/EscalationsPage';
import DocumentsPage from './pages/DocumentsPage';
import UsersPage from './pages/UsersPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<AskPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="escalations" element={
              <ProtectedRoute allowedRoles={['engineer', 'admin']}><EscalationsPage /></ProtectedRoute>
            } />
            <Route path="documents" element={
              <ProtectedRoute allowedRoles={['engineer', 'admin']}><DocumentsPage /></ProtectedRoute>
            } />
            <Route path="users" element={
              <ProtectedRoute allowedRoles={['admin']}><UsersPage /></ProtectedRoute>
            } />
            <Route path="analytics" element={
              <ProtectedRoute allowedRoles={['admin']}><AnalyticsPage /></ProtectedRoute>
            } />
            <Route path="settings" element={
              <ProtectedRoute allowedRoles={['admin']}><SettingsPage /></ProtectedRoute>
            } />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
