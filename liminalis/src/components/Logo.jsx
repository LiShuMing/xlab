export function Logo({ small = false }) {
  return (
    <a href="/" className={small ? 'logo logo-small' : 'logo'}>
      <span className="logo-mark">L</span>
      <span>Liminalis</span>
    </a>
  );
}
