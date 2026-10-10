const DOTS = [
  { l: "6%", s: 6, d: 26, t: -4 }, { l: "17%", s: 9, d: 34, t: -18 }, { l: "29%", s: 5, d: 28, t: -9 }, { l: "42%", s: 8, d: 38, t: -26 },
  { l: "55%", s: 6, d: 30, t: -13 }, { l: "68%", s: 10, d: 36, t: -2 }, { l: "79%", s: 5, d: 27, t: -21 }, { l: "91%", s: 8, d: 33, t: -30 },
];

/* Decorative, non-interactive layer that sits behind the interface. Colours come from theme variables in index.css. */
export default function BackgroundAnimation() {
  return (
    <div className="bg-anim" aria-hidden="true">
      <span className="bg-orb bg-orb-1" />
      <span className="bg-orb bg-orb-2" />
      <span className="bg-orb bg-orb-3" />
      <span className="bg-radar" />
      {DOTS.map((p, i) => (
        <span key={i} className="bg-dot" style={{ left: p.l, width: p.s, height: p.s, animationDuration: `${p.d}s`, animationDelay: `${p.t}s` }} />
      ))}
    </div>
  );
}
