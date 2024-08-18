import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { RoleCard } from '../../components/ego/RoleCard';
import { listRoles, getCurrentRole, updateCurrentRole } from '../../lib/ego/api';
import { BUILTIN_ROLES, getCurrentRoleId, setCurrentRoleId, getRoleName } from '../../lib/ego/roles';

export function EgoRolePage() {
  const navigate = useNavigate();
  const [roles, setRoles] = useState(BUILTIN_ROLES);
  const [currentId, setCurrentId] = useState(getCurrentRoleId());
  const currentName = getRoleName(currentId);

  useEffect(() => {
    async function load() {
      try {
        const data = await listRoles();
        if (Array.isArray(data)) {
          setRoles(data);
        }
        const cur = await getCurrentRole();
        if (cur?.id) {
          setCurrentId(cur.id);
          setCurrentRoleId(cur.id);
        }
      } catch {
        // Use built-in roles
      }
    }
    load();
  }, []);

  async function handleSelect(role) {
    setCurrentId(role.id);
    setCurrentRoleId(role.id);
    try {
      await updateCurrentRole(role.id);
    } catch {
      // Already set locally
    }
    // Toast
    const toast = document.createElement('div');
    toast.className = 'ego2-toast';
    toast.textContent = `已切换到「${role.name}」`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
  }

  return (
    <div className="ego2-page">
      <div className="ego2-section">
        <div className="ego2-section__head">
          <span className="ego2-kicker">ROLES</span>
          <h2 className="ego2-hero-title">角色</h2>
          <p className="ego2-muted">选择一个角色开始对话</p>
        </div>
      </div>

      <div className="ego2-section">
        {roles.map((role) => (
          <RoleCard
            key={role.id}
            role={role}
            selected={currentId === role.id}
            onSelect={handleSelect}
          />
        ))}
      </div>

      <div className="ego2-section ego2-section--current">
        <div className="ego2-kicker">CURRENT</div>
        <div className="ego2-current-role">
          <span>{currentName}</span>
          <button className="ego2-btn" onClick={() => navigate('/ego/chat')}>
            去对话
          </button>
        </div>
      </div>
    </div>
  );
}
