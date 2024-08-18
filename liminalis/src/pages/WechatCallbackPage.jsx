import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/Header';
import { setAuthSession } from '../lib/ego/authState';

export function WechatCallbackPage() {
  const navigate = useNavigate();
  const [message, setMessage] = useState('正在完成微信登录...');

  useEffect(() => {
    const params = readCallbackParams();
    const token = params.get('token');
    const accountId = params.get('account_id');
    const accountLabel = params.get('account_label') || accountId;
    const target = sanitizeTarget(params.get('target'));

    if (!token || !accountId) {
      setMessage('微信登录失败，请返回后重试。');
      return;
    }

    setAuthSession({ token, accountId, accountLabel });
    navigate(target, { replace: true });
  }, [navigate]);

  return (
    <main className="ego2-page">
      <Header />
      <div className="ego2-shell">
        <div className="ego2-status">{message}</div>
      </div>
    </main>
  );
}

function readCallbackParams() {
  const hash = window.location.hash.replace(/^#\??/, '');
  if (hash) return new URLSearchParams(hash);
  return new URLSearchParams(window.location.search);
}

function sanitizeTarget(target) {
  if (!target || !target.startsWith('/') || target.startsWith('//')) return '/ego/chat';
  if (target.startsWith('/api/') || target.startsWith('/wechat/callback')) return '/ego/chat';
  return target;
}
