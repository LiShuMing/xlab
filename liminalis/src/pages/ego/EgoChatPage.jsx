import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ChatBubble } from '../../components/ego/ChatBubble';
import { createSession, sendMessage, listMessages } from '../../lib/ego/api';
import { generateChatReply } from '../../lib/ego/aiFeedback';
import { getCurrentRoleId, getRoleName, setCurrentRoleId } from '../../lib/ego/roles';
import {
  loadLocalChatMessages as loadLocal,
  saveLocalChatMessages as saveLocal,
  getWelcomeMessage,
} from '../../lib/ego/localChat';

export function EgoChatPage() {
  const navigate = useNavigate();
  const { roleId: paramRoleId } = useParams();
  const [roleId, setRoleId] = useState(getCurrentRoleId());
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  const roleName = getRoleName(roleId);

  // Apply role from route param
  useEffect(() => {
    if (paramRoleId && paramRoleId !== roleId) {
      setRoleId(paramRoleId);
      setCurrentRoleId(paramRoleId);
    }
  }, [paramRoleId]);

  // Load messages
  const loadMessages = useCallback(async (sid) => {
    if (!sid) {
      setMessages([getWelcomeMessage(roleId)]);
      return;
    }
    try {
      const data = await listMessages(sid);
      if (Array.isArray(data) && data.length > 0) {
        setMessages(data);
      } else {
        setMessages([getWelcomeMessage(roleId)]);
      }
    } catch {
      setMessages(loadLocal(roleId));
    }
  }, [roleId]);

  // Ensure session on mount
  useEffect(() => {
    async function init() {
      try {
        const sess = await createSession(roleId);
        setSessionId(sess.id);
        await loadMessages(sess.id);
      } catch {
        setSessionId(null);
        setMessages(loadLocal(roleId));
      }
    }
    init();
  }, [roleId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Persist messages to local
  useEffect(() => {
    if (messages.length > 0) {
      saveLocal(messages, roleId);
    }
  }, [messages, roleId]);

  async function handleSend() {
    const content = draft.trim();
    if (!content || sending) return;

    const userMsg = {
      id: `u-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setDraft('');
    setSending(true);

    try {
      let sid = sessionId;
      if (!sid) {
        const sess = await createSession(roleId);
        sid = sess.id;
        setSessionId(sid);
      }
      const result = await sendMessage(sid, content);
      const reply = result.reply || result;
      setMessages((prev) => [...prev, reply]);
    } catch {
      const replyText = generateChatReply(content, roleId);
      const localReply = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        role_id: roleId,
        role_label: roleName,
        content: replyText,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, localReply]);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleSend();
    }
  }

  return (
    <div className="ego2-page ego2-page--chat">
      <div className="ego2-section">
        <div className="ego2-section__head">
          <span className="ego2-kicker">SESSION</span>
          <h2 className="ego2-hero-title">对话</h2>
          <button className="ego2-link-btn" onClick={() => navigate('/ego/roles')}>
            {roleName}
          </button>
        </div>
      </div>

      <div className="ego2-chat-messages">
        {messages.map((msg) => (
          <ChatBubble key={msg.id} message={msg} roleName={roleName} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="ego2-chat-composer">
        <textarea
          className="ego2-composer-input"
          placeholder="写一段话..."
          value={draft}
          onChange={(e) => setDraft(e.target.value.slice(0, 800))}
          onKeyDown={handleKeyDown}
          maxLength={800}
        />
        <button
          className="ego2-btn"
          onClick={handleSend}
          disabled={!draft.trim() || sending}
        >
          {sending ? '...' : '发送'}
        </button>
      </div>
    </div>
  );
}
