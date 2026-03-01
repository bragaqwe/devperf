import { T, font, fontSans, scoreColor } from '../tokens'

export const Spinner = ({ size = 20 }) => (
  <div style={{
    width: size, height: size, border: `2px solid ${T.border}`,
    borderTopColor: T.accentLt, borderRadius: '50%',
    animation: 'spin 0.7s linear infinite', display: 'inline-block', flexShrink: 0,
  }} />
)

export const Card = ({ children, style = {}, onClick, fadeIn }) => (
  <div onClick={onClick} style={{
    background: T.card, border: `1px solid ${T.border}`, borderRadius: 12,
    padding: '20px 22px', cursor: onClick ? 'pointer' : 'default',
    transition: 'border-color 0.15s, background 0.15s',
    animation: fadeIn ? 'fadeIn 0.25s ease' : undefined, ...style,
  }}
    onMouseEnter={e => { if (onClick) { e.currentTarget.style.borderColor = T.borderLt; e.currentTarget.style.background = T.cardHov }}}
    onMouseLeave={e => { if (onClick) { e.currentTarget.style.borderColor = T.border;   e.currentTarget.style.background = T.card }}}
  >{children}</div>
)

export const Badge = ({ label, color = T.textSm, size = 'sm' }) => (
  <span style={{
    padding: size === 'xs' ? '1px 6px' : '2px 9px',
    borderRadius: 20, fontSize: size === 'xs' ? 9 : 10, fontWeight: 700,
    letterSpacing: '0.07em', textTransform: 'uppercase',
    background: color + '22', color, border: `1px solid ${color}33`,
    fontFamily: font, whiteSpace: 'nowrap', flexShrink: 0,
  }}>{label}</span>
)

export const Btn = ({ children, onClick, variant = 'default', disabled, small, loading, title, style: sx = {} }) => {
  const s = {
    default: { bg: T.card,       color: T.text,   border: T.border },
    primary: { bg: T.accent,     color: '#fff',   border: T.accent },
    danger:  { bg: '#1a0a0a',    color: T.red,    border: T.red + '55' },
    ghost:   { bg: 'transparent',color: T.textMd, border: 'transparent' },
    success: { bg: T.green+'18', color: T.green,  border: T.green+'44' },
  }[variant] || { bg: T.card, color: T.text, border: T.border }
  return (
    <button onClick={onClick} disabled={disabled || loading} title={title} style={{
      padding: small ? '4px 10px' : '8px 16px', borderRadius: 8,
      border: `1px solid ${s.border}`, background: s.bg, color: s.color,
      fontSize: small ? 11 : 13, fontWeight: 600,
      cursor: disabled || loading ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.45 : 1, display: 'inline-flex',
      alignItems: 'center', gap: 6, transition: 'all 0.15s',
      fontFamily: fontSans, whiteSpace: 'nowrap', flexShrink: 0, ...sx,
    }}>
      {loading && <Spinner size={13} />}{children}
    </button>
  )
}

export const Input = ({ label, value, onChange, placeholder, hint, type = 'text' }) => (
  <div style={{ marginBottom: 14 }}>
    {label && <label style={{ display: 'block', fontSize: 11, color: T.textSm, marginBottom: 5, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</label>}
    <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
      style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 13, fontFamily: font, outline: 'none', boxSizing: 'border-box' }}
      onFocus={e => e.target.style.borderColor = T.accentLt}
      onBlur={e  => e.target.style.borderColor = T.border}
    />
    {hint && <div style={{ fontSize: 10, color: T.textSm, marginTop: 4 }}>{hint}</div>}
  </div>
)

export const Select = ({ label, value, onChange, options, hint }) => (
  <div style={{ marginBottom: 14 }}>
    {label && <label style={{ display: 'block', fontSize: 11, color: T.textSm, marginBottom: 5, fontFamily: font, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</label>}
    <select value={value} onChange={e => onChange(e.target.value)}
      style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 13, fontFamily: font, outline: 'none' }}
      onFocus={e => e.target.style.borderColor = T.accentLt}
      onBlur={e  => e.target.style.borderColor = T.border}
    >
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
    {hint && <div style={{ fontSize: 10, color: T.textSm, marginTop: 4 }}>{hint}</div>}
  </div>
)

export const Modal = ({ title, onClose, children, wide }) => (
  <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.78)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)' }}
    onClick={e => e.target === e.currentTarget && onClose()}>
    <div style={{ background: T.card, border: `1px solid ${T.borderLt}`, borderRadius: 16, padding: '28px 28px 24px', width: wide ? 860 : 520, maxWidth: '96vw', maxHeight: '92vh', overflowY: 'auto', animation: 'fadeIn 0.2s ease' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
        <h3 style={{ margin: 0, color: T.text, fontSize: 16, fontWeight: 700, fontFamily: fontSans }}>{title}</h3>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: T.textSm, cursor: 'pointer', fontSize: 22, lineHeight: 1, padding: '0 4px' }}>×</button>
      </div>
      {children}
    </div>
  </div>
)

export const ScoreRing = ({ value, size = 52, stroke = 5 }) => {
  const r = (size - stroke * 2) / 2, circ = 2 * Math.PI * r
  const dash = (Math.min(value || 0, 100) / 100) * circ
  const color = scoreColor(value || 0)
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)', flexShrink: 0 }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={T.border} strokeWidth={stroke} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeDasharray={`${dash} ${circ-dash}`} strokeLinecap="round" />
      <text x={size/2} y={size/2+5} fill={color} fontSize={size > 44 ? 13 : 10} fontWeight={700} textAnchor="middle" fontFamily={font} style={{ transform: 'rotate(90deg)', transformOrigin: '50% 50%' }}>
        {Math.round(value || 0)}
      </text>
    </svg>
  )
}

export const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: '10px 14px', fontSize: 12, fontFamily: font }}>
      <div style={{ color: T.textSm, marginBottom: 4 }}>{label}</div>
      {payload.map(p => <div key={p.dataKey} style={{ color: p.color, marginBottom: 2 }}>{p.name}: <b>{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</b></div>)}
    </div>
  )
}

export const Avatar = ({ name, size = 36 }) => (
  <div style={{ width: size, height: size, borderRadius: '50%', flexShrink: 0, background: 'linear-gradient(135deg,#2563eb,#8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: size * 0.38, fontWeight: 700, color: '#fff' }}>
    {(name || '?').charAt(0).toUpperCase()}
  </div>
)

export const Section = ({ title, children, action }) => (
  <div style={{ marginBottom: 20 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: T.textSm, textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: font }}>{title}</div>
      {action}
    </div>
    {children}
  </div>
)

export const EmptyState = ({ icon, text, action }) => (
  <div style={{ textAlign: 'center', padding: '48px 24px', color: T.textMd }}>
    <div style={{ fontSize: 36, marginBottom: 12 }}>{icon}</div>
    <div style={{ fontSize: 14, marginBottom: 16 }}>{text}</div>
    {action}
  </div>
)

export const Tag = ({ children, color = T.textSm }) => (
  <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontFamily: font, background: color + '18', color, border: `1px solid ${color}28` }}>
    {children}
  </span>
)
