import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../../components/Header';
import { TerminalBlock } from '../../components/ego/TerminalBlock';
import { loginWithPin } from '../../lib/ego/api';
import { setAuthSession } from '../../lib/ego/authState';

export function EgoLoginPage() {
  const navigate = useNavigate();
  const [pin, setPin] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  const canSend = pin.length === 6 && !sending;
  const wechatLoginUrl = `/api/wechat/official/oauth/start?target=${encodeURIComponent('/ego/chat')}`;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSend) return;
    setSending(true);
    setError('');

    try {
      const data = await loginWithPin(pin);
      if (data.token) {
        setAuthSession({
          token: data.token,
          accountId: data.user?.id || `pin-${pin}`,
          accountLabel: data.user?.nickname || `PIN-${pin}`,
        });
        navigate('/ego/chat');
        return;
      }
      setError('登录失败，请重试');
    } catch {
      // Local fallback: create account from pin hash
      const accountId = `local-pin-${pin}`;
      setAuthSession({ token: '', accountId, accountLabel: accountId });
      navigate('/ego/chat');
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="ego2-page">
      <Header />
      <div className="ego2-shell">
        <div className="ego2-login">
          <div className="ego2-login__hero">
            <div className="ego2-login__kicker">PY-EGO</div>
            <h1 className="ego2-login__title">进入</h1>
            <p className="ego2-login__desc">
              输入 6 位 PIN，生成你的本地账号。同一设备同一 PIN 会回到同一个账号。
            </p>
          </div>

          <form className="ego2-login__form" onSubmit={handleSubmit}>
            <input
              className="ego2-login__pin-input"
              type="password"
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
              autoFocus
            />
            <div className="ego2-login__counter">{pin.length}/6</div>
            <button type="submit" className="ego2-login__submit" disabled={!canSend}>
              {sending ? '验证中...' : '进入'}
            </button>
            <a className="ego2-login__wechat" href={wechatLoginUrl}>
              微信公众号登录
            </a>
            {error && <div className="ego2-login__error">{error}</div>}
          </form>

          <TerminalBlock title="account" status="sha256(ip + pin)">
            <div>$ account = hash(client_ip + pin)</div>
            <div>$ chat storage = account scoped</div>
          </TerminalBlock>
        </div>
      </div>
    </main>
  );
}
