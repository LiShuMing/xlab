export function ChatBubble({ message, roleName = 'EGO' }) {
  const isUser = message.role === 'user';
  const speaker = isUser ? 'YOU' : (message.role_label || roleName);
  const timeLabel = message.created_at
    ? new Date(message.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={`ego2-chat-bubble${isUser ? ' ego2-chat-bubble--user' : ''}`}>
      <div className="ego2-chat-bubble__head">
        <span className="ego2-chat-bubble__speaker">{speaker}</span>
        {timeLabel && <span className="ego2-chat-bubble__time">{timeLabel}</span>}
      </div>
      <div className="ego2-chat-bubble__content">{message.content}</div>
    </div>
  );
}
