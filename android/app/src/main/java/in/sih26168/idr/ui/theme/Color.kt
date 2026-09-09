package `in`.sih26168.idr.ui.theme

import androidx.compose.ui.graphics.Color

/** App background — Uber-black surface. */
val Bg = Color(0xFF0B0E11)
/** Sheets, cards, elevated panels. */
val Bg2 = Color(0xFF161A1F)
val Panel = Color(0xC7161A1F)
val Line = Color(0x17E8EDF2)
val Text = Color(0xFFFFFFFF)
/** Secondary labels on dark surfaces — kept ≥ ~4.5:1 vs Bg/Bg2. */
val Mute = Color(0xFFA3ABB4)
/** Our track, active states, CTA — teal. */
val Accent = Color(0xFF00E0A4)
/** Alias for telem/success readouts (same teal family). */
val Telem = Color(0xFF00E0A4)
/** GNSS-fix track segment — calm blue only. */
val Gnss = Color(0xFF4FC3F7)
/** Legacy name kept for call sites; maps to GNSS blue. */
val Ours = Gnss
val Danger = Color(0xFFFF4D6A)
/** IDR-mode HUD pill / warnings. */
val Amber = Color(0xFFFFB300)
/** Naive/ghost puck (file 05). */
val Ghost = Color(0xFFFF5252)
