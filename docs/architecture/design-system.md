# Design system: "Clinical Calm"

**Since:** 22 Nov 2026 · **Replaces:** the October "Follow the line" signage design
([landing spec](../superpowers/specs/2026-10-05-landing-and-auth-pages-design.md),
[staff workspace spec](../superpowers/specs/2026-10-06-staff-workspace-design.md)) · **Chosen by:** the team, from three
directions rendered on the real app (Clinical Calm, Civic Signal, Night Shift)

A calm, light interface for people working under pressure: white and slate surfaces, one teal brand colour, soft cards,
and type chosen for legibility first. Status colours are kept for meaning (critical, warning, ok), never decoration.

## Tokens

Every colour, font, radius, shadow and duration is a token in
[`frontend/src/styles/tokens.css`](../../frontend/src/styles/tokens.css); components read only tokens. Dark mode
redefines the colour tokens under `prefers-color-scheme: dark` (navy surfaces, the same teal).

| Token | Light | Dark | Use |
|---|---|---|---|
| `--sign` | `#0B6E79` | same (set at runtime) | Brand: logo, primary buttons, active line. From `config/hospital.ts` (`brandColor`) |
| `--accent`, `--accent-soft` | `#0B6E79`, `#E3F2F3` | `#5EEAD4`, teal 12% | Active nav item, links that act, icons in pills |
| `--wall`, `--surface` | `#F4F6F9`, `#FFFFFF` | `#0B1220`, `#111A2B` | Page and cards |
| `--ink`, `--ink-muted` | `#0F172A`, `#4B5768` | `#E6EDF7`, `#9AA8BF` | Text |
| `--rule`, `--field-border` | `#E2E8F0`, `#7C889C` | `#22304A`, `#55698C` | Hairlines; borders of fields and buttons (3:1) |
| `--chrome-*` | white sidebar and header | `#0E1626` | Staff sidebar, top bar |
| `--footer*` | `#0F172A` | `#070C16` | Public footer |
| `--status-*`, `--line-*`, `--bed-*` | unchanged | unchanged | Meaning only; always with an icon and a word |
| `--radius-sm/--radius/--radius-lg` | 8 / 12 / 16 px | | Buttons / fields and small cards / panels and tiles |
| `--shadow-sm/md/lg` | soft, slate-tinted | deeper | Buttons / cards / raised surfaces |
| `--ease-out`, `--duration-fast/--duration` | 150 / 240 ms | | Motion |

Every text pairing meets WCAG AA (4.5:1) and every field border and focus ring 3:1, in both modes (checked with the
WCAG formula when the palette was chosen). White on the brand teal is 5.96:1.

## Type

**Atkinson Hyperlegible Next** for headings and text, and **Atkinson Hyperlegible Mono** for unit numbers, bed labels and
times (both SIL Open Font License, self-hosted through `@fontsource-variable`). The Braille Institute drew them so that
letters that are easily confused are not: I, l and 1; O and 0 (the zero has a slash); rn and m. In a hospital a
misread blood-unit number, bed label or dose is a clinical risk, so legibility comes first. Headings are weight 800 with
slightly tight tracking; nothing is set in capitals.

## Logo and imagery

- **Logo** ([`components/brand/Logo.tsx`](../../frontend/src/components/brand/Logo.tsx)): a plus whose centre is a
  node, for hospitals joined into one network, drawn in `--sign`, so a hospital's brand colour changes it too. Also the
  favicon (`frontend/public/favicon.svg`).
- **City network** ([`features/landing/CityNetwork.tsx`](../../frontend/src/features/landing/CityNetwork.tsx)): the home
  page illustration, hospitals on a street grid joined by routes, in theme colours. Decorative (`aria-hidden`), hidden
  on phones.
- **Icons:** [Lucide](https://lucide.dev) (ISC licence, `lucide-react`), one per staff module
  ([`features/staff/moduleIcons.tsx`](../../frontend/src/features/staff/moduleIcons.tsx)), always beside a word, never
  alone.

## Motion

Small and quick, and all of it is off when the device asks for reduced motion (`global.css`):

- each staff page fades up as it opens (240 ms); the sign-in card does the same;
- overview tiles lift under the pointer, and their numbers count up the first time they show
  ([`lib/useCountUp.ts`](../../frontend/src/lib/useCountUp.ts); tabular digits, so nothing jitters);
- on the home page the city-network routes draw themselves in and the receiving hospital pulses; the coloured lines
  from the sign to each section draw down, as before.

## What stayed

The page structure, every label, role and landmark (the tests and the end-to-end scenario find elements by them), the
coloured route lines on the home page, and the status colours. The redesign changed styles, not behaviour.
