type CoastMarkProps = {
  size?: number;
  className?: string;
};

/** C-ring + saffron puck — the COAST launcher mark. */
export function CoastMark({ size = 28, className }: CoastMarkProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
    >
      <rect width="32" height="32" fill="#07090D" />
      <path
        d="M22.4 8.2a10.4 10.4 0 1 0 0 15.6"
        fill="none"
        stroke="#00D4AA"
        strokeWidth="2.7"
        strokeLinecap="round"
      />
      <path d="M13.2 10 L23.6 16 L13.2 22 Z" fill="#FF6B2D" />
    </svg>
  );
}

export function CoastWordmark({ size = 22 }: { size?: number }) {
  return (
    <span className="brand-lockup">
      <CoastMark size={size} />
      COAST<span className="dot">.</span>
    </span>
  );
}
