/* EduRadar mark: a radar scanner (rings + rotating sweep) with a graduation cap at its centre. */
export default function LogoMark({ className = "" }) {
  return (
    <svg className={`logo-mark ${className}`} viewBox="0 0 48 48" fill="none" aria-hidden="true" focusable="false">
      <circle cx="24" cy="24" r="20" stroke="currentColor" strokeOpacity=".55" strokeWidth="1.6" />
      <circle cx="24" cy="24" r="12.5" stroke="currentColor" strokeOpacity=".4" strokeWidth="1.4" strokeDasharray="2.5 3" />
      <g className="logo-sweep">
        <path d="M24 24 L24 4 A20 20 0 0 1 41.32 14 Z" fill="currentColor" fillOpacity=".28" />
        <line x1="24" y1="24" x2="24" y2="4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </g>
      <path d="M24 14 L36 20 L24 26 L12 20 Z" fill="currentColor" />
      <path d="M17.5 23.4 V28 C17.5 29.8 20.4 31.2 24 31.2 C27.6 31.2 30.5 29.8 30.5 28 V23.4 L24 26.7 Z" fill="currentColor" fillOpacity=".9" />
      <path d="M36 20 V28.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="36" cy="29.8" r="1.6" fill="currentColor" />
    </svg>
  );
}
