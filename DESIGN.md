# TimeDesk design direction

Source: the user's approved light, orderly workplace direction, applied to attendance work. ENERGY 1 / RHYTHM 2 / MOTION 1.

The first decision is whether to start or finish the employee's own work session. That control has the largest weight. The next task is checking dated records. Correction review uses before/after intervals and a written reason, so reviewers can decide from the record instead of a decorative chart.

- Slate blue `#153d63` identifies clock controls and current navigation. Pale blue separates the clock area from the white history table. Green only marks an active or approved state, always with text.
- Arial is a local system font. Tabular digits keep elapsed time and durations easy to compare. No font service or generated image assets are required.
- The desktop composition combines a horizontal clock strip, date filters and a dense history table. On phones the clock becomes a vertical section and each table row becomes a labelled record. Main navigation stays visible.
- Motion is limited to normal control feedback. The live elapsed text updates once per second without animated decoration. Reduced motion is respected.
- Focus rings, a skip link, explicit labels, 44px controls and high contrast serve keyboard and touch use. Server timestamps and Training labels explain what the numbers mean.
- Form boundaries use `#6f8394` on white (3.93:1). Values use `#203244` (13.12:1), placeholders explicitly use `#516577` at full opacity (6.04:1), and focus uses `#1672b5` (5.11:1 on white; 4.68:1 on the page background). These source color calculations are checked again against rendered controls before publication.

No logo asset is fabricated: TimeDesk is plain text. There are no invented trends, testimonials, biometric claims or attendance-compliance claims.
