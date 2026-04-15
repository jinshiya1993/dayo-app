import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from '../services/api';

export default function AuthPage() {
  const navigate = useNavigate();
  const [isLogin, setIsLogin] = useState(true);
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (isLogin) {
      const result = await auth.login({ username: form.username, password: form.password });
      if (result.error) {
        setError(result.error === 'unauthorized' ? 'Invalid username or password' : result.error);
      } else {
        navigate('/');
      }
    } else {
      const result = await auth.register(form);
      if (result.error) {
        setError(typeof result.error === 'object' ? Object.values(result.error).flat().join(' ') : result.error);
      } else {
        navigate('/');
      }
    }
    setLoading(false);
  }

  return (
    <div className="auth-screen">
      <div className="auth-logo">
        da<span style={{ color: '#C2855A' }}>yo</span>
      </div>
      <div className="auth-tagline">Your personal AI day planner</div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <input
          className="auth-input"
          placeholder="Username"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
          required
        />
        {!isLogin && (
          <input
            className="auth-input"
            type="email"
            placeholder="Email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
        )}
        <input
          className="auth-input"
          type="password"
          placeholder="Password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          required
          minLength={8}
        />
        {error && <div className="auth-error">{error}</div>}
        <button className="auth-btn" type="submit" disabled={loading}>
          {loading ? 'Please wait...' : isLogin ? 'Log In' : 'Create Account'}
        </button>
      </form>

      <div className="auth-switch">
        {isLogin ? "Don't have an account? " : 'Already have an account? '}
        <button onClick={() => { setIsLogin(!isLogin); setError(''); }}>
          {isLogin ? 'Sign up' : 'Log in'}
        </button>
      </div>
    </div>
  );
}
