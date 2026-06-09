# MediAgent — Design System (MASTER)

Source of truth for the MediAgent frontend. Read this before building any page or
component. Page-specific deviations live in `design-system/pages/<page>.md` and
**override** this file for that page only; otherwise these rules apply everywhere.

Stack: Next.js 16 (App Router) · React 19 · Tailwind v4 (CSS-first, no `tailwind.config.js`)
· shadcn/ui (`radix-nova` preset, Radix primitives, Lucide icons) · tokens in `app/globals.css`.

---

## 1. Style direction — "Clinical Calm"

Minimal / flat, **light-first** (desktop MVP; mobile + dark mode are later passes).
Trustworthy and legible over decorative. Generous whitespace, clear hierarchy,
restraint. One primary CTA per screen; secondary actions visually subordinate.

Healthcare product = the UI must feel safe and precise. No playful/brutalist motifs,
no emoji as icons (use **Lucide** only), one icon family + stroke width throughout.

---

## 2. Typography

| Role | Font | Notes |
|------|------|-------|
| UI / body | **Plus Jakarta Sans** | Warm humanist sans (matches the Sign In design). Hierarchy via weight, not font-switching. Body ≥16px, line-height 1.5–1.75. |
| Numeric / data | **Geist Mono** | Lab values, reference ranges, queue position, times — tabular figures so columns align and don't shift. |

Weight hierarchy: headings 600–700, labels 500, body 400.

> **Wiring (done):** `layout.tsx` sets Plus Jakarta Sans `variable: "--font-sans"` and
> Geist Mono `--font-geist-mono`, so `globals.css`'s `--font-sans`/`--font-mono` resolve.
>
> **Design scales:** the Sign In mockup's `ink-*` and `teal-*` numbered scales (plus
> `okay/info/crit-*` and `shadow-card`/`shadow-lift`) are registered in `globals.css`
> `@theme` for pixel-faithful custom screens (login, chat). `teal-900=#0E2954`,
> `teal-700=#1F6E8C` (=primary), `teal-600=#2E8A99`, `teal-500=#84A7A1`.

---

## 3. Color system

### 3.1 Brand palette (cool: navy → slate-blue → teal → sage)

| Token (`--var`) | Hex | Role | Contrast note |
|------|------|------|---------------|
| `--primary` | `#1F6E8C` slate-blue | Primary actions: buttons, links, focus ring | White text **5.7:1 ✓ AA** |
| `--navy` | `#0E2954` | Hero/gradient anchor, dark surfaces, strong headings, primary hover | White text ~12:1 ✓ |
| `--teal` | `#2E8A99` | Accent + **patient chat bubble**, highlights | White text ~4.0:1 — **only at ≥16px** |
| `--sage` | `#84A7A1` | Muted FILLS, borders, dividers, disabled fills | **~2.6:1 — never text on light** |

Hero/gradient direction: `#0E2954 → #1F6E8C → #2E8A99` (navy → slate → teal).

### 3.2 Clinical state tokens (carry medical meaning — keep across all themes)

| Token | Hex | Meaning |
|------|------|---------|
| `--success` | `#16A34A` | Normal / in-range lab result |
| `--warning` | `#D97706` | Borderline / monitor |
| `--destructive` (danger) | `#DC2626` | Abnormal / critical / urgent triage |
| `--info` | `#0EA5E9` | Neutral system info |

**Rule (`color-not-decorative-only`):** clinical state must always be conveyed by
**color + icon + text** — never color alone (colorblind safety; it's medical data).
E.g. a low hemoglobin chip = red fill + down-arrow icon + "Low".

### 3.3 Neutrals

shadcn base = `neutral` (grayscale). Text uses `--foreground`; muted text uses
`--muted-foreground` (a dark gray) — **not** sage. May optionally cool the neutrals
(slight blue tint) in a later polish pass.

### 3.4 Usage cheatsheet (generated utilities)

`bg-primary text-primary-foreground` (CTAs) · `bg-teal text-teal-foreground` (patient
bubble, ≥16px) · `bg-success|warning|info|destructive` + matching `-foreground` (clinical
chips/badges) · `border-sage` / `bg-sage/…` (muted surfaces) · `ring-primary` (focus).

---

## 4. shadcn component inventory (Block 1B base set)

| Component | Used for |
|-----------|----------|
| `button`, `input`, `label`, `form` | login form, chat composer (Form = react-hook-form + zod) |
| `input-otp` | 6-digit code entry on the verify step |
| `card` | side panels, modal bodies |
| `dialog` | the 4 rich-content modals (Appointment / Lab / Queue / Triage) |
| `badge` | queue position, lab severity, triage urgency |
| `alert` | mandatory medical disclaimer + error banners |
| `sonner` | toasts: "code sent", request/verify errors |
| `skeleton` | panel/chat loading (skeleton over spinner for >1s) |
| `scroll-area` | chat history + scrollable panels |
| `avatar`, `dropdown-menu` | header patient menu + logout |
| `separator`, `tooltip` | layout + full text for truncated values |

---

## 5. Patterns

- **Rich content → modals, not chat bubbles.** A bubble shows a short summary + a
  trigger button ("View Report"); the structured data opens in a `Dialog`.
  (Appointment / Lab / Queue / Triage.)
- **`/chat` layout:** center chat panel + left rail of always-visible side panels
  (Appointments, Reports, Queue, History). No separate routes for these.
- **Medical disclaimer:** render as a persistent `Alert`, not faint gray text.
- **Login is one route, two states:** ① phone + email → ② 6-digit code (`input-otp`).
- **Modal motion:** animate from trigger (scale+fade), scrim 40–60% black.

---

## 6. Non-negotiable a11y / UX rules (skill priority 1–3)

- **Contrast:** body/normal text ≥ 4.5:1; large text & non-text UI ≥ 3:1. Verify both themes.
- **Focus:** visible focus ring on every interactive element — never strip it.
- **Color is never the only signal** — pair with icon/text (esp. clinical state).
- **Touch/click targets** ≥ 44px; `cursor-pointer` on clickables.
- **Loading:** skeletons for >1s; disable buttons + spinner during async (OTP send, login).
- **Forms:** visible labels (not placeholder-only); error below the field via
  `aria-live`/`role="alert"`; validate on blur; semantic input types (`email`, `tel`);
  auto-focus first invalid field; mark required fields.
- **Motion:** 150–300ms, `transform`/`opacity` only; respect `prefers-reduced-motion`.
- **Number formatting:** locale-aware; tabular figures (Geist Mono) for data columns.

---

## 7. Anti-patterns (do NOT)

- ❌ Sage `#84A7A1` as text on a light background (fails contrast).
- ❌ White/light text on teal at <16px (≈4.0:1).
- ❌ Mapping brand teal onto shadcn `--accent` (turns every hover loud); use `--teal`.
- ❌ Conveying lab/triage severity by color alone.
- ❌ Emoji as icons; mixing icon families/stroke widths.
- ❌ Raw hex in components — always use the semantic token utilities above.
- ❌ Rich data inline in chat bubbles — use modals.
