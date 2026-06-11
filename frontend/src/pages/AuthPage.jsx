import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from '../services/api';

const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

export default function AuthPage() {
  const navigate = useNavigate();
  const [isLogin, setIsLogin] = useState(true);
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const googleBtnRef = useRef(null);

  // Render the Google Identity Services button once its script has loaded.
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !googleBtnRef.current) return;
    let cancelled = false;

    async function handleGoogleResponse(response) {
      setError('');
      const result = await auth.google(response.credential);
      if (cancelled) return;
      if (result.error) {
        setError(result.error === 'unauthorized' ? 'Google sign-in failed' : result.error);
      } else {
        navigate('/');
      }
    }

    function tryRender() {
      if (cancelled) return;
      if (!window.google?.accounts?.id) {
        setTimeout(tryRender, 200); // GIS script still loading
        return;
      }
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleResponse,
      });
      window.google.accounts.id.renderButton(googleBtnRef.current, {
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'pill',
        width: 300,
      });
    }

    tryRender();
    return () => { cancelled = true; };
  }, [navigate]);

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

      {GOOGLE_CLIENT_ID && (
        <>
          <div ref={googleBtnRef} style={{ display: 'flex', justifyContent: 'center', marginBottom: 18 }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#9b8f86', fontSize: 13, marginBottom: 18 }}>
            <span style={{ flex: 1, height: 1, background: '#EDE8E3' }} />
            or
            <span style={{ flex: 1, height: 1, background: '#EDE8E3' }} />
          </div>
        </>
      )}

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
