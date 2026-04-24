import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { profile as profileApi, children as childrenApi, auth } from '../services/api';

export default function ProfilePage() {
  const navigate = useNavigate();
  const [profileData, setProfileData] = useState(null);
  const [childList, setChildList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [showChildForm, setShowChildForm] = useState(false);
  const [childForm, setChildForm] = useState({ name: '', date_of_birth: '', interests: '', school_name: '' });
  const [editingModules, setEditingModules] = useState(false);
  const [newModule, setNewModule] = useState('');

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    setLoading(true);
    const [prof, ch] = await Promise.all([
      profileApi.get(),
      childrenApi.list(),
    ]);
    if (!prof.error) {
      setProfileData(prof);
      setForm(prof);
    }
    if (!ch.error) setChildList(Array.isArray(ch) ? ch : []);
    setLoading(false);
  }

  async function handleSave() {
    const result = await profileApi.update({
      display_name: form.display_name,
      user_type: form.user_type,
      timezone: form.timezone,
      wake_time: form.wake_time,
      sleep_time: form.sleep_time,
      dietary_restrictions: form.dietary_restrictions,
      cuisine_preferences: form.cuisine_preferences,
      location_city: form.location_city,
      notes: form.notes,
    });
    if (!result.error) {
      setProfileData(result);
      setEditing(false);
    }
  }

  async function handleAddChild(e) {
    e.preventDefault();
    const data = {
      ...childForm,
      interests: childForm.interests ? childForm.interests.split(',').map((s) => s.trim()) : [],
    };
    const result = await childrenApi.create(data);
    if (!result.error) {
      setShowChildForm(false);
      setChildForm({ name: '', date_of_birth: '', interests: '', school_name: '' });
      loadProfile();
    }
  }

  async function handleDeleteChild(id) {
    await childrenApi.delete(id);
    loadProfile();
  }

  async function handleAddModule() {
    const trimmed = newModule.trim();
    if (!trimmed || !profileData) return;
    const updated = [...(profileData.planning_modules || []), trimmed];
    const result = await profileApi.update({ planning_modules: updated });
    if (!result.error) { setProfileData(result); setNewModule(''); }
  }

  async function handleRemoveModule(mod) {
    if (!profileData) return;
    const updated = (profileData.planning_modules || []).filter((m) => m !== mod);
    const result = await profileApi.update({ planning_modules: updated });
    if (!result.error) setProfileData(result);
  }

  async function handleLogout() {
    await auth.logout();
    navigate('/auth');
  }

  if (loading) {
    return <div className="loading"><div className="spinner" />Loading profile...</div>;
  }

  if (!profileData) return null;

  const initial = profileData.display_name?.[0]?.toUpperCase() || '?';

  return (
    <div className="profile-screen">
      <div className="profile-header">
        <div className="profile-avatar-lg">{initial}</div>
        <div className="profile-name">{profileData.display_name}</div>
        <div className="profile-type">{profileData.user_type}</div>
      </div>

      {!editing ? (
        <>
          <div className="profile-section">
            <div className="profile-section-title">About</div>
            <div className="profile-field">
              <span className="profile-field-label">Name</span>
              <span className="profile-field-value">{profileData.display_name}</span>
            </div>
            <div className="profile-field">
              <span className="profile-field-label">Type</span>
              <span className="profile-field-value">{profileData.user_type}</span>
            </div>
            <div className="profile-field">
              <span className="profile-field-label">City</span>
              <span className="profile-field-value">{profileData.location_city || '—'}</span>
            </div>
            <div className="profile-field">
              <span className="profile-field-label">Wake / Sleep</span>
              <span className="profile-field-value">
                {profileData.wake_time?.slice(0, 5)} / {profileData.sleep_time?.slice(0, 5)}
              </span>
            </div>
          </div>

          <div className="profile-section">
            <div className="profile-section-title">Preferences</div>
            <div className="profile-field" style={{ flexWrap: 'wrap' }}>
              <span className="profile-field-label">Diet</span>
              <div>
                {(profileData.dietary_restrictions || []).length > 0
                  ? profileData.dietary_restrictions.map((d) => (
                      <span className="profile-tag" key={d}>{d}</span>
                    ))
                  : <span className="profile-field-value">None</span>
                }
              </div>
            </div>
            <div className="profile-field" style={{ flexWrap: 'wrap' }}>
              <span className="profile-field-label">Cuisine</span>
              <div>
                {(profileData.cuisine_preferences || []).length > 0
                  ? profileData.cuisine_preferences.map((c) => (
                      <span className="profile-tag" key={c}>{c}</span>
                    ))
                  : <span className="profile-field-value">Any</span>
                }
              </div>
            </div>
          </div>

          {/* Planning Modules */}
          <div className="profile-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div className="profile-section-title" style={{ margin: 0 }}>Planning Modules</div>
              <button className="section-link" onClick={() => setEditingModules(!editingModules)}>
                {editingModules ? 'Done' : 'Edit'}
              </button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(profileData.planning_modules || []).map((m) => (
                <span key={m} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  background: '#FFF8F0', borderRadius: 10, padding: '5px 10px',
                  fontSize: 12, fontWeight: 600, color: '#C2855A',
                }}>
                  {m.replace(/_/g, ' ')}
                  {editingModules && (
                    <button onClick={() => handleRemoveModule(m)} style={{ border: 'none', background: 'none', color: '#C2855A', cursor: 'pointer', fontSize: 14, padding: 0 }}>×</button>
                  )}
                </span>
              ))}
            </div>
            {editingModules && (
              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <input
                  className="auth-input"
                  value={newModule}
                  onChange={(e) => setNewModule(e.target.value)}
                  placeholder="Add module (e.g. Pet care)"
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddModule(); } }}
                  style={{ flex: 1, marginBottom: 0 }}
                />
                <button onClick={handleAddModule} disabled={!newModule.trim()} style={{
                  padding: '0 16px', borderRadius: 12, border: 'none',
                  background: newModule.trim() ? '#C2855A' : '#EDE8E3',
                  color: 'white', fontWeight: 600, cursor: 'pointer', fontSize: 18,
                }}>+</button>
              </div>
            )}
          </div>

          <button onClick={() => navigate('/settings/dashboard')} style={{
            width: '100%', padding: '14px', borderRadius: 14, marginBottom: 10,
            border: '0.5px solid #EDE8E3', background: 'white', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            fontSize: 14, fontWeight: 600, color: '#1a1a1a',
          }}>
            <span style={{ fontSize: 18 }}>⚙️</span> Customise Dashboard
          </button>

          <button className="btn-brand" onClick={() => setEditing(true)} style={{ width: '100%', marginBottom: 16 }}>
            Edit Profile
          </button>
        </>
      ) : (
        <div className="profile-section">
          <input className="auth-input" value={form.display_name || ''} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="Display name" style={{ marginBottom: 8 }} />
          <select className="auth-input" value={form.user_type || 'parent'} onChange={(e) => setForm({ ...form, user_type: e.target.value })} style={{ marginBottom: 8 }}>
            <option value="homemaker">Homemaker</option>
            <option value="parent">Homemaker with Kids</option>
            <option value="new_mom">New Mom</option>
            <option value="working_mom">Working Mom</option>
          </select>
          <input className="auth-input" value={form.location_city || ''} onChange={(e) => setForm({ ...form, location_city: e.target.value })} placeholder="City" style={{ marginBottom: 8 }} />
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <input className="auth-input" type="time" value={form.wake_time?.slice(0, 5) || '06:00'} onChange={(e) => setForm({ ...form, wake_time: e.target.value })} />
            <input className="auth-input" type="time" value={form.sleep_time?.slice(0, 5) || '22:00'} onChange={(e) => setForm({ ...form, sleep_time: e.target.value })} />
          </div>
          <input className="auth-input" value={(form.dietary_restrictions || []).join(', ')} onChange={(e) => setForm({ ...form, dietary_restrictions: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} placeholder="Dietary restrictions (comma separated)" style={{ marginBottom: 8 }} />
          <input className="auth-input" value={(form.cuisine_preferences || []).join(', ')} onChange={(e) => setForm({ ...form, cuisine_preferences: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} placeholder="Cuisine preferences (comma separated)" style={{ marginBottom: 8 }} />
          <textarea className="auth-input" value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Notes for AI" rows={3} style={{ marginBottom: 8, resize: 'vertical' }} />
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="auth-btn" onClick={handleSave} style={{ flex: 1 }}>Save</button>
            <button className="auth-btn" onClick={() => { setEditing(false); setForm(profileData); }} style={{ flex: 1, background: '#888' }}>Cancel</button>
          </div>
        </div>
      )}

      {/* Children */}
      <div className="profile-section" style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div className="profile-section-title" style={{ margin: 0 }}>Children</div>
          <button className="section-link" onClick={() => setShowChildForm(!showChildForm)}>
            {showChildForm ? 'Cancel' : '+ Add'}
          </button>
        </div>

        {showChildForm && (
          <form onSubmit={handleAddChild} style={{ marginBottom: 12 }}>
            <input className="auth-input" placeholder="Child's name" value={childForm.name} onChange={(e) => setChildForm({ ...childForm, name: e.target.value })} required style={{ marginBottom: 8 }} />
            <input className="auth-input" type="date" value={childForm.date_of_birth} onChange={(e) => setChildForm({ ...childForm, date_of_birth: e.target.value })} required style={{ marginBottom: 8 }} />
            <input className="auth-input" placeholder="Interests (comma separated)" value={childForm.interests} onChange={(e) => setChildForm({ ...childForm, interests: e.target.value })} style={{ marginBottom: 8 }} />
            <input className="auth-input" placeholder="School name (optional)" value={childForm.school_name} onChange={(e) => setChildForm({ ...childForm, school_name: e.target.value })} style={{ marginBottom: 8 }} />
            <button type="submit" className="auth-btn">Add Child</button>
          </form>
        )}

        {childList.length === 0 && !showChildForm && (
          <div style={{ color: '#888', fontSize: 13, padding: '8px 0' }}>No children added</div>
        )}

        {childList.map((child) => (
          <div className="profile-field" key={child.id}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{child.name}</div>
              <div style={{ color: '#888', fontSize: 12 }}>
                Age {child.age}
                {child.interests?.length > 0 && ` · ${child.interests.join(', ')}`}
              </div>
            </div>
            <button
              onClick={() => handleDeleteChild(child.id)}
              style={{ border: 'none', background: 'none', color: '#DC3545', cursor: 'pointer', fontSize: 16 }}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <button className="profile-logout-btn" onClick={handleLogout}>
        Log Out
      </button>
    </div>
  );
}
