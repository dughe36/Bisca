import { memo } from "react";

const SUIT_COLORS = {
  denari: "#D4AF37",
  coppe: "#B32B2B",
  spade: "#26547C",
  bastoni: "#2A5C27",
};

const VALUE_LABELS = { 1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "F", 9: "C", 10: "R" };

function SuitGlyph({ suit, size = 28 }) {
  const c = SUIT_COLORS[suit];
  if (suit === "denari")
    return (
      <svg width={size} height={size} viewBox="0 0 40 40">
        <circle cx="20" cy="20" r="16" fill={c} stroke="#8a6d1e" strokeWidth="1.5" />
        <circle cx="20" cy="20" r="11" fill="none" stroke="#8a6d1e" strokeWidth="1" />
        <text x="20" y="25" textAnchor="middle" fontFamily="serif" fontSize="12" fill="#5b4715">✦</text>
      </svg>
    );
  if (suit === "coppe")
    return (
      <svg width={size} height={size} viewBox="0 0 40 40">
        <path d="M10 10 L30 10 L28 22 Q20 30 12 22 Z" fill={c} stroke="#5a1010" strokeWidth="1.5" />
        <rect x="18" y="28" width="4" height="6" fill={c} stroke="#5a1010" strokeWidth="1" />
        <ellipse cx="20" cy="34" rx="7" ry="2" fill={c} stroke="#5a1010" strokeWidth="1" />
      </svg>
    );
  if (suit === "spade")
    return (
      <svg width={size} height={size} viewBox="0 0 40 40">
        <path d="M20 4 Q26 18 30 26 Q26 34 20 32 Q14 34 10 26 Q14 18 20 4 Z" fill={c} stroke="#12314c" strokeWidth="1.5" />
        <rect x="19" y="30" width="2" height="6" fill="#12314c" />
      </svg>
    );
  // bastoni
  return (
    <svg width={size} height={size} viewBox="0 0 40 40">
      <rect x="18" y="6" width="4" height="28" rx="2" fill={c} stroke="#153a13" strokeWidth="1.5" />
      <circle cx="20" cy="8" r="4" fill={c} stroke="#153a13" strokeWidth="1.5" />
      <circle cx="20" cy="34" r="4" fill={c} stroke="#153a13" strokeWidth="1.5" />
    </svg>
  );
}

function BiscaCard({ card, hidden, small, faceDown, onClick, playable, "data-testid": tid }) {
  if (hidden || faceDown) {
    return (
      <div
        className={`card-back rounded-md ${small ? "w-10 h-16" : "w-16 h-24"} ${onClick ? "cursor-pointer" : ""}`}
        onClick={onClick}
        data-testid={tid}
      />
    );
  }
  const label = VALUE_LABELS[card.value];
  const color = SUIT_COLORS[card.suit];
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={`card-face rounded-md relative select-none ${small ? "w-10 h-16 text-xs" : "w-16 h-24 text-sm"} ${playable ? "hover:-translate-y-2 transition-transform duration-200" : ""} ${onClick ? "cursor-pointer" : "cursor-default"}`}
      style={{ borderTopColor: color, borderTopWidth: "3px" }}
      data-testid={tid}
    >
      <span className="absolute top-1 left-1.5 font-serif font-bold" style={{ color }}>{label}</span>
      <span className="absolute bottom-1 right-1.5 font-serif font-bold rotate-180" style={{ color }}>{label}</span>
      <div className="absolute inset-0 flex items-center justify-center">
        <SuitGlyph suit={card.suit} size={small ? 16 : 26} />
      </div>
    </button>
  );
}

export default memo(BiscaCard);
