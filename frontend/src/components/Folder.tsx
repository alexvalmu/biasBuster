import type { CSSProperties, ReactNode } from "react";

// Pastel folder covers: [face, tab]
export const FOLDER_COLORS = {
  mint: ["#A9CBC6", "#99C1BB"],
  blue: ["#B3C2D6", "#A5B6CD"],
  violet: ["#C9BCD6", "#BDAECD"],
  sage: ["#B4C9B5", "#A6BEA8"],
  sand: ["#DCC9A0", "#D1BC8E"],
  rose: ["#D9B3A9", "#CFA498"],
} as const;

export type FolderColor = keyof typeof FOLDER_COLORS;

export const INK = "#1D1C1A";
export const INK_2 = "#5E5B55";
export const PAPER = "#FCFBF8";
export const ORANGE = "#FF5A1F";

type Props = {
  color: FolderColor;
  title: string;
  subtitle: string;
  children: ReactNode;
  className?: string;
  tilt?: number;
};

/** A dotted pastel folder with a tab, holding a line drawing in a 240×300 viewBox. */
export function Folder({ color, title, subtitle, children, className = "", tilt }: Props) {
  const [fold, fold2] = FOLDER_COLORS[color];
  const style = {
    "--fold": fold,
    "--fold-2": fold2,
    ...(tilt !== undefined ? { "--tilt": `${tilt}deg` } : {}),
  } as CSSProperties;

  return (
    <span className={`folder ${className}`} style={style} aria-hidden>
      <span className="folder-tab" />
      <span className="folder-face">
        <svg viewBox="0 0 240 300">
          <text x="22" y="36" fontFamily="Doto, monospace" fontWeight="800" fontSize="15" fill={INK}>
            {title}
          </text>
          <text x="22" y="52" fontFamily="Satoshi, sans-serif" fontSize="7.5" fill={INK_2}>
            {subtitle}
          </text>
          {children}
        </svg>
      </span>
    </span>
  );
}
