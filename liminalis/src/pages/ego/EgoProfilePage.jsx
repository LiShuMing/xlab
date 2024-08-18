import { useNavigate } from 'react-router-dom';
import { TerminalBlock } from '../../components/ego/TerminalBlock';
import { getCurrentRoleId, getRoleName } from '../../lib/ego/roles';
import { getAccountLabel } from '../../lib/ego/authState';

export function EgoProfilePage() {
  const navigate = useNavigate();
  const roleName = getRoleName(getCurrentRoleId());
  const accountLabel = getAccountLabel();

  return (
    <div className="ego2-page">
      <div className="ego2-section">
        <div className="ego2-section__head">
          <span className="ego2-kicker">PY-EGO</span>
          <h2 className="ego2-hero-title">我</h2>
          <p className="ego2-muted">你的记忆、档案和设置由本地存储和 AI 服务共同维护。</p>
        </div>
      </div>

      <div className="ego2-section">
        <TerminalBlock title="memory" status="online">
          <div>$ role: {roleName}</div>
          <div>$ account: {accountLabel}</div>
          <div>$ profile: 随着对话和记录自动更新</div>
        </TerminalBlock>
      </div>

      <div className="ego2-section">
        <div className="ego2-action-grid">
          <button className="ego2-btn" onClick={() => navigate('/ego/roles')}>
            角色设置
          </button>
          <button
            className="ego2-btn ego2-btn--ghost"
            onClick={() => {
              const toast = document.createElement('div');
              toast.className = 'ego2-toast';
              toast.textContent = '待接入 profile/export';
              document.body.appendChild(toast);
              setTimeout(() => toast.remove(), 2000);
            }}
          >
            导出数据
          </button>
        </div>
      </div>
    </div>
  );
}
