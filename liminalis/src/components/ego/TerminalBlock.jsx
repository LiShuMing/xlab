export function TerminalBlock({ title, status, children }) {
  return (
    <div className="ego2-terminal">
      {(title || status) && (
        <div className="ego2-terminal__head">
          {title && <span className="ego2-terminal__title">{title}</span>}
          {status && <span className="ego2-terminal__status">{status}</span>}
        </div>
      )}
      <div className="ego2-terminal__body">{children}</div>
    </div>
  );
}
