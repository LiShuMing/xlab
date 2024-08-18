export function RoleCard({ role, selected, onSelect }) {
  return (
    <button type="button" className={`ego2-role-card${selected ? ' ego2-role-card--selected' : ''}`} onClick={() => onSelect(role)}>
      <div className="ego2-role-card__info">
        <div className="ego2-role-card__name">{role.name}</div>
        <div className="ego2-role-card__id">{role.id}</div>
        <div className="ego2-role-card__desc">{role.description}</div>
      </div>
      <div className="ego2-role-card__action">
        <span className="ego2-role-card__marker">{selected ? '[x]' : '[ ]'}</span>
        <span className="ego2-role-card__btn">{selected ? '当前使用' : '使用此角色'}</span>
      </div>
    </button>
  );
}
