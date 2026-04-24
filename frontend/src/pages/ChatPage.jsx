import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { chat, profile as profileApi, children as childrenApi } from '../services/api';

function getDefaultChips(profileData, childList) {
  const userType = profileData?.user_type;
  const hasOlderKids = childList?.some(c => c.age >= 1);
  const hasInfant = childList?.some(c => c.age < 1);

  const babyName = profileData?.baby_name || 'baby';

  if (userType === 'new_mom' && !hasOlderKids) {
    // Infant only — baby-focused chips
    return [
      "Quick meal I can eat one-handed",
      `When should ${babyName} nap next?`,
      "I'm exhausted, simplify my day",
      "Healthy snack for breastfeeding",
    ];
  }

  if (userType === 'new_mom' && hasOlderKids) {
    // Infant + older kids
    return [
      `When should ${babyName} nap next?`,
      "Activity ideas for kids",
      "Quick meal I can eat one-handed",
      "I'm exhausted, simplify my day",
    ];
  }

  // Default — parent, homemaker, working_mom
  return [
    "What should I cook tonight?",
    "Activity ideas for kids",
    "Reschedule my afternoon",
    "Healthy snack options",
  ];
}

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [activeConvo, setActiveConvo] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [childList, setChildList] = useState([]);
  const messagesEnd = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const prefillHandled = useRef(false);

  const defaultChips = getDefaultChips(profileData, childList);

  useEffect(() => {
    loadConversations();
    profileApi.get().then(res => { if (!res.error) setProfileData(res); });
    childrenApi.list().then(res => { if (!res.error && Array.isArray(res)) setChildList(res); });
  }, []);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (location.state?.prefill && !prefillHandled.current) {
      prefillHandled.current = true;
      const prefill = location.state.prefill;
      navigate(location.pathname, { replace: true, state: {} });
      (async () => {
        const result = await chat.create();
        if (!result.error) {
          setActiveConvo(result);
          setMessages([]);
          await doSendMessage(result, prefill);
        }
      })();
    }
  }, [location.state]);

  async function loadConversations() {
    setLoading(true);
    const result = await chat.list();
    if (!result.error) setConversations(Array.isArray(result) ? result : []);
    setLoading(false);
  }

  async function startNewChat() {
    const result = await chat.create();
    if (!result.error) { setActiveConvo(result); setMessages([]); }
  }

  async function openConversation(convo) {
    const result = await chat.get(convo.id);
    if (!result.error) { setActiveConvo(result); setMessages(result.messages || []); }
  }

  async function deleteConversation(e, convoId) {
    e.stopPropagation();
    await chat.delete(convoId);
    setConversations((prev) => prev.filter((c) => c.id !== convoId));
  }

  async function doSendMessage(convo, text) {
    if (!text.trim() || !convo) return;
    const userMsg = { id: Date.now(), role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setSending(true);
    const result = await chat.send(convo.id, text);
    if (!result.error) {
      setMessages((prev) => [...prev, result]);
      if (convo.title === 'New Chat') setActiveConvo({ ...convo, title: text.slice(0, 50) });
    } else {
      setMessages((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }]);
    }
    setSending(false);
  }

  async function sendMessage(text) { await doSendMessage(activeConvo, text); }

  async function confirmAction(messageId) {
    setConfirming(messageId);
    const result = await chat.confirm(messageId);
    if (!result.error) {
      setMessages((prev) => prev.map((m) => m.id === messageId ? { ...m, action_status: 'confirmed' } : m));
      if (result.message) setMessages((prev) => [...prev, result.message]);
      if (result.follow_up) setMessages((prev) => [...prev, result.follow_up]);
    }
    setConfirming(null);
  }

  async function cancelAction(messageId) {
    setConfirming(messageId);
    const result = await chat.cancel(messageId);
    if (!result.error) {
      setMessages((prev) => prev.map((m) => m.id === messageId ? { ...m, action_status: 'cancelled' } : m));
      if (result.message) setMessages((prev) => [...prev, result.message]);
    }
    setConfirming(null);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input); }
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  // ── Chat conversation view ──
  if (activeConvo) {
    return (
      <div className="chat-screen">
        {/* Header */}
        <div className="chat-header">
          <button className="chat-back-btn" onClick={() => { setActiveConvo(null); loadConversations(); }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
          </button>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="chat-header-title">{activeConvo.title || 'New Chat'}</div>
            <div className="chat-header-subtitle">Dayo is here to help</div>
          </div>
          <div className="chat-header-status">
            <span className="chat-status-dot" />
            Online
          </div>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {/* Empty state */}
          {messages.length === 0 && (
            <div className="chat-empty-state">
              <div className="chat-empty-avatar">D</div>
              <div className="chat-empty-title">Hey! How can I help today?</div>
              <div className="chat-empty-subtitle">
                I can manage your meals, groceries, schedule, housework — just ask.
              </div>
              <div className="chat-chips-grid">
                {defaultChips.map((chip) => (
                  <button key={chip} className="chat-chip" onClick={() => sendMessage(chip)}>
                    {chip}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message list */}
          {messages.map((msg) =>
            msg.role === 'user' ? (
              <div className="chat-row user" key={msg.id}>
                <div className="chat-bubble user">{msg.content}</div>
              </div>
            ) : (
              <div className="chat-row assistant" key={msg.id}>
                <div className="chat-avatar">D</div>
                <div className="chat-content">
                  <div className="chat-bubble assistant">{msg.content}</div>

                  {/* Pending action */}
                  {msg.action_status === 'pending' && (
                    <div className="chat-action-buttons">
                      <button className="chat-action-btn confirm"
                        onClick={() => confirmAction(msg.id)}
                        disabled={confirming === msg.id}>
                        {confirming === msg.id ? (
                          <><span className="chat-btn-spinner" /> Working...</>
                        ) : 'Yes, do it'}
                      </button>
                      <button className="chat-action-btn cancel"
                        onClick={() => cancelAction(msg.id)}
                        disabled={confirming === msg.id}>
                        Cancel
                      </button>
                    </div>
                  )}

                  {msg.action_status === 'confirmed' && (
                    <div className="chat-action-badge confirmed">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
                      Done
                    </div>
                  )}

                  {msg.action_status === 'cancelled' && (
                    <div className="chat-action-badge cancelled">Cancelled</div>
                  )}
                </div>
              </div>
            )
          )}

          {/* Typing indicator */}
          {sending && (
            <div className="chat-row assistant">
              <div className="chat-avatar">D</div>
              <div className="chat-content">
                <div className="chat-bubble assistant chat-typing">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEnd} />
        </div>

        {/* Input */}
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <input
              className="chat-input-field"
              placeholder="Message Dayo..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending}
            />
            <button className="chat-send"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || sending}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Conversation list view ──
  return (
    <div style={{ paddingBottom: 100 }}>
      {/* Header */}
      <div style={{ padding: '20px 16px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'Georgia, serif', color: '#1a1a1a' }}>Chats</div>
          <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>Your conversations with Dayo</div>
        </div>
        <button onClick={startNewChat} style={{
          background: '#C2855A', color: '#fff', border: 'none', borderRadius: 12,
          padding: '10px 18px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Chat
        </button>
      </div>

      {loading && (
        <div className="loading"><div className="spinner" />Loading...</div>
      )}

      {!loading && conversations.length === 0 && (
        <div style={{ textAlign: 'center', padding: '60px 24px' }}>
          <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#C2855A" strokeWidth="1.5" strokeLinecap="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
          </div>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', marginBottom: 6 }}>No conversations yet</div>
          <div style={{ fontSize: 13, color: '#999' }}>Start chatting with Dayo about your day</div>
        </div>
      )}

      <div style={{ padding: '16px 16px 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {conversations.slice(0, 3).map((convo) => (
          <div key={convo.id} onClick={() => openConversation(convo)} style={{
            background: '#fff', borderRadius: 14, border: '1px solid #EDE8E3',
            padding: '14px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: 12, background: '#FDF2EB',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              fontSize: 16,
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#C2855A" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {convo.title}
              </div>
              <div style={{ fontSize: 12, color: '#aaa', marginTop: 3 }}>
                {convo.message_count} messages · {timeAgo(convo.updated_at)}
              </div>
            </div>
            <button onClick={(e) => deleteConversation(e, convo.id)} style={{
              border: 'none', background: 'none', color: '#ccc', cursor: 'pointer',
              fontSize: 18, padding: '4px', flexShrink: 0,
            }}>×</button>
          </div>
        ))}
      </div>
    </div>
  );
}
