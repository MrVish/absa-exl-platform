/**
 * Client walkthrough deck for the ABSA x EXL Model Hosting onboarding program.
 *
 * Run: node scripts/build_client_deck.js
 * Output: docs/absa-exl-program-walkthrough.pptx
 *
 * Palette: Midnight Executive
 *   Primary  navy   #1E2761  (60-70% weight)
 *   Mid     deep blue #2E4172
 *   Light   ice blue #CADCFC
 *   Bg      off-white #F1F4F9
 *   Accent  coral   #F96167  (risk / critical)
 *   Done    green   #4CAF50
 *   Muted   slate   #64748B
 */

const pptxgen = require("pptxgenjs");
const path = require("path");

const C = {
  NAVY: "1E2761",
  DEEP: "2E4172",
  ICE: "CADCFC",
  BG: "F1F4F9",
  WHITE: "FFFFFF",
  CORAL: "F96167",
  GREEN: "4CAF50",
  AMBER: "F59E0B",
  SLATE: "64748B",
  CHARCOAL: "1E293B",
  BAND: "EEF2F7",
};

const FONT_HEAD = "Georgia";
const FONT_BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "ABSA × EXL Program Office";
pres.title = "ABSA × EXL Model Hosting — Program Walkthrough";

// --- helpers -------------------------------------------------------------

function darkSlide() {
  const s = pres.addSlide();
  s.background = { color: C.NAVY };
  return s;
}

function lightSlide() {
  const s = pres.addSlide();
  s.background = { color: C.WHITE };
  return s;
}

function addTitleStrip(slide, title, subtitle) {
  // Slim navy header strip with the title — replaces a heavy "accent line"
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.3, h: 0.65,
    fill: { color: C.NAVY }, line: { color: C.NAVY },
  });
  slide.addText(title, {
    x: 0.5, y: 0, w: 8.5, h: 0.65,
    fontFace: FONT_HEAD, fontSize: 22, bold: true, color: C.WHITE,
    valign: "middle", margin: 0,
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: 9, y: 0, w: 4, h: 0.65,
      fontFace: FONT_BODY, fontSize: 11, color: C.ICE,
      valign: "middle", align: "right", margin: 0,
    });
  }
}

function addFooter(slide, pageNum, total) {
  slide.addText(`ABSA × EXL  •  Onboarding Program Walkthrough`, {
    x: 0.5, y: 7.05, w: 9, h: 0.3,
    fontFace: FONT_BODY, fontSize: 9, color: C.SLATE, margin: 0,
  });
  slide.addText(`${pageNum} / ${total}`, {
    x: 12.3, y: 7.05, w: 0.6, h: 0.3,
    fontFace: FONT_BODY, fontSize: 9, color: C.SLATE, align: "right", margin: 0,
  });
}

function statCard(slide, x, y, w, h, value, label, color = C.NAVY) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: C.WHITE }, line: { color: C.ICE, width: 0.75 },
    shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
  });
  slide.addText(value, {
    x: x + 0.15, y: y + 0.18, w: w - 0.3, h: h * 0.55,
    fontFace: FONT_HEAD, fontSize: 38, bold: true, color, align: "center", valign: "middle",
  });
  slide.addText(label, {
    x: x + 0.1, y: y + h * 0.6, w: w - 0.2, h: h * 0.4,
    fontFace: FONT_BODY, fontSize: 10.5, color: C.SLATE, align: "center", valign: "top",
  });
}

// Generic small "pill" used for phase chips
function pill(slide, x, y, w, h, text, fillColor, textColor) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, fill: { color: fillColor }, line: { color: fillColor }, rectRadius: h / 2,
  });
  slide.addText(text, {
    x, y, w, h, fontFace: FONT_BODY, fontSize: 10, bold: true,
    color: textColor, align: "center", valign: "middle", margin: 0,
  });
}

// ---- SLIDE 1: TITLE -----------------------------------------------------
{
  const s = darkSlide();

  // Big eyebrow
  s.addText("ONBOARDING PROGRAM WALKTHROUGH", {
    x: 0.7, y: 1.8, w: 12, h: 0.5,
    fontFace: FONT_BODY, fontSize: 14, bold: true, color: C.ICE,
    charSpacing: 6, margin: 0,
  });

  // Main title
  s.addText("ABSA × EXL", {
    x: 0.7, y: 2.4, w: 12, h: 1.1,
    fontFace: FONT_HEAD, fontSize: 64, bold: true, color: C.WHITE, margin: 0,
  });
  s.addText("Model Hosting Platform", {
    x: 0.7, y: 3.5, w: 12, h: 0.9,
    fontFace: FONT_HEAD, fontSize: 44, color: C.ICE, italic: true, margin: 0,
  });

  // Tagline
  s.addText("A 6-month program to onboard 10 production models with end-to-end\ngovernance, security and chain-of-custody from intake to scoring delivery.", {
    x: 0.7, y: 5.0, w: 12, h: 1.2,
    fontFace: FONT_BODY, fontSize: 16, color: C.ICE, lineSpacingMultiple: 1.25, margin: 0,
  });

  // Vertical accent rectangle (not a horizontal "accent line")
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.4, y: 1.8, w: 0.12, h: 4.5,
    fill: { color: C.CORAL }, line: { color: C.CORAL },
  });
}

// ---- SLIDE 2: WHY WE ARE HERE -------------------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "Why we're here", "01 / Context");

  // Two-column layout: narrative left, three pillars right
  s.addText("The opportunity", {
    x: 0.6, y: 1.05, w: 6.2, h: 0.5,
    fontFace: FONT_HEAD, fontSize: 22, bold: true, color: C.NAVY, margin: 0,
  });
  s.addText(
    "ABSA has 10 production-grade risk and decision models running today across multiple\n" +
    "environments. EXL will host the scoring runtime end-to-end — taking signed code\n" +
    "and data from ABSA, scoring it on a controlled platform, and returning auditable\n" +
    "outputs on the agreed cadence.\n\n" +
    "The platform we deliver must satisfy banking-grade audit, security and change-\n" +
    "management requirements while being repeatable enough to onboard new models\n" +
    "without re-architecting.",
    {
      x: 0.6, y: 1.6, w: 6.2, h: 4.5,
      fontFace: FONT_BODY, fontSize: 13, color: C.CHARCOAL, lineSpacingMultiple: 1.35, margin: 0,
    }
  );

  // Right: 3 pillars
  const pillars = [
    { t: "Auditable",    d: "Every artefact signed; every action logged; full chain-of-custody from intake to delivery." },
    { t: "Repeatable",   d: "Pipeline templates and a model registry turn new-model onboarding from weeks into days." },
    { t: "Cross-account", d: "ABSA and EXL operate in separate AWS accounts with cryptographically verifiable hand-offs." },
  ];
  pillars.forEach((p, i) => {
    const y = 1.1 + i * 1.8;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 7.4, y, w: 5.3, h: 1.55,
      fill: { color: C.WHITE }, line: { color: C.ICE, width: 0.75 },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 7.4, y, w: 0.1, h: 1.55,
      fill: { color: C.NAVY }, line: { color: C.NAVY },
    });
    s.addText(p.t, {
      x: 7.7, y: y + 0.1, w: 5.0, h: 0.5,
      fontFace: FONT_HEAD, fontSize: 18, bold: true, color: C.NAVY, margin: 0,
    });
    s.addText(p.d, {
      x: 7.7, y: y + 0.6, w: 4.95, h: 0.9,
      fontFace: FONT_BODY, fontSize: 11.5, color: C.CHARCOAL, lineSpacingMultiple: 1.3, margin: 0,
    });
  });

  addFooter(s, 2, 13);
}

// ---- SLIDE 3: AT A GLANCE -----------------------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "Delivery at a glance", "02 / What we're committing to");

  // Five stat cards
  statCard(s, 0.6, 1.2, 2.4, 1.6, "10", "models in scope", C.NAVY);
  statCard(s, 3.15, 1.2, 2.4, 1.6, "6", "months to go-live", C.NAVY);
  statCard(s, 5.7, 1.2, 2.4, 1.6, "9", "delivery phases", C.NAVY);
  statCard(s, 8.25, 1.2, 2.4, 1.6, "85+", "tracked tasks", C.NAVY);
  statCard(s, 10.8, 1.2, 2.1, 1.6, "11", "milestone gates", C.CORAL);

  // Story strip below
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 3.2, w: 12.3, h: 1.5,
    fill: { color: C.BG }, line: { color: C.ICE, width: 0.5 },
  });
  s.addText("How the 10 models split", {
    x: 0.85, y: 3.3, w: 6, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 14, bold: true, color: C.NAVY, margin: 0,
  });
  s.addText([
    { text: "Group 1 ", options: { bold: true, color: C.CORAL } },
    { text: "(2 models, Month 4):", options: { color: C.CHARCOAL } },
    { text: " proof of the chain end-to-end. ABSA sign-off here is the biggest single milestone.", options: { color: C.CHARCOAL, breakLine: true } },
    { text: "Group 2 ", options: { bold: true, color: C.NAVY } },
    { text: "(8 models, Months 5-6):", options: { color: C.CHARCOAL } },
    { text: " parallel ramp; reuses Group 1 templates so per-model cost falls sharply.", options: { color: C.CHARCOAL } },
  ], {
    x: 0.85, y: 3.75, w: 12, h: 0.95,
    fontFace: FONT_BODY, fontSize: 12.5, lineSpacingMultiple: 1.35, margin: 0,
  });

  // What success looks like
  s.addText("What success looks like at Month 6", {
    x: 0.6, y: 5.0, w: 12, h: 0.45,
    fontFace: FONT_HEAD, fontSize: 16, bold: true, color: C.NAVY, margin: 0,
  });
  const wins = [
    ["10/10", "models in scheduled production scoring on EXL-hosted infrastructure"],
    ["100%", "of scoring runs cryptographically signed + verifiable end-to-end by ABSA"],
    ["Self-service", "template-driven onboarding for any new model in the same family"],
  ];
  wins.forEach((w, i) => {
    const x = 0.6 + i * 4.15;
    s.addText(w[0], {
      x, y: 5.5, w: 1.8, h: 0.5,
      fontFace: FONT_HEAD, fontSize: 22, bold: true, color: C.CORAL, margin: 0,
    });
    s.addText(w[1], {
      x: x + 1.8, y: 5.55, w: 2.4, h: 1.0,
      fontFace: FONT_BODY, fontSize: 11.5, color: C.CHARCOAL, lineSpacingMultiple: 1.3, margin: 0,
    });
  });

  addFooter(s, 3, 13);
}

// ---- SLIDE 4: PROGRAM TIMELINE -----------------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "Program timeline", "03 / Six months at a glance");

  // Month axis - shifted right so phase labels fit in the left gutter
  const months = ["M1", "M2", "M3", "M4", "M5", "M6", "M7+"];
  const axisY = 1.5;
  const axisX = 4.8;
  const axisW = 8.2;
  const monthW = axisW / 7;
  months.forEach((m, i) => {
    s.addText(m, {
      x: axisX + i * monthW, y: axisY, w: monthW, h: 0.35,
      fontFace: FONT_HEAD, fontSize: 13, bold: true, color: C.NAVY,
      align: "center", margin: 0,
    });
  });
  // axis line
  s.addShape(pres.shapes.LINE, {
    x: axisX, y: axisY + 0.4, w: axisW, h: 0,
    line: { color: C.SLATE, width: 0.75 },
  });

  // Phase bars: [name, startM (1..7), spanM, color, optional milestone idx (0..6)]
  const bars = [
    ["Governance & Scope",                1, 1, C.NAVY,  null],
    ["Architecture, Access & Connectivity", 1, 2, C.DEEP,  null],
    ["Data & Code Readiness",             1, 2, C.DEEP,  null],
    ["Platform Foundation Build",         2, 2, C.NAVY,  null],
    ["Controls & Change Mgmt",            2, 5, C.SLATE, null],
    ["Code Optimization & Pipelines",     3, 2, C.DEEP,  null],
    ["Group 1 — First 2 models",          4, 1, C.CORAL, 3],
    ["Group 2 — Remaining 8 models",      5, 2, C.NAVY,  null],
    ["Dashboards & Delivery",             5, 2, C.DEEP,  null],
    ["Steady State Support",              7, 1, C.GREEN, null],
    ["New Model Onboarding (template)",   7, 1, C.GREEN, null],
  ];

  let y = axisY + 0.55;
  const barH = 0.30;
  const rowGap = 0.05;
  bars.forEach((b) => {
    const [name, startM, span, color, milestoneM] = b;
    const bx = axisX + (startM - 1) * monthW;
    const bw = monthW * span;

    // Phase label on left, sits in the 4.7" gutter to the left of the axis
    s.addText(name, {
      x: 0.3, y, w: 4.35, h: barH,
      fontFace: FONT_BODY, fontSize: 10.5, color: C.CHARCOAL,
      align: "right", valign: "middle", margin: 0,
    });
    // Bar
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: bx, y, w: bw, h: barH,
      fill: { color, transparency: 0 }, line: { color, width: 0 }, rectRadius: barH / 4,
    });
    // Milestone diamond if Group 1
    if (milestoneM !== null) {
      const mx = axisX + (milestoneM + 1) * monthW - 0.16;
      s.addShape(pres.shapes.DIAMOND, {
        x: mx, y: y - 0.04, w: 0.22, h: 0.38,
        fill: { color: C.WHITE }, line: { color: C.CORAL, width: 2 },
      });
    }
    y += barH + rowGap;
  });

  // Critical milestone callout — y after 11 bars ≈ 1.5 + 0.55 + 11*0.35 = 5.9, so safely below
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.5, y: 6.15, w: 12.3, h: 0.65,
    fill: { color: C.CORAL, transparency: 88 }, line: { color: C.CORAL, width: 1.25 }, rectRadius: 0.08,
  });
  s.addShape(pres.shapes.DIAMOND, {
    x: 0.7, y: 6.31, w: 0.28, h: 0.33,
    fill: { color: C.WHITE }, line: { color: C.CORAL, width: 2 },
  });
  s.addText("Critical milestone: Group 1 sign-off (end of Month 4) gates Group 2 and steady state. Schedule slippage here cascades.", {
    x: 1.15, y: 6.2, w: 11.5, h: 0.55,
    fontFace: FONT_BODY, fontSize: 12, bold: true, color: C.CORAL, valign: "middle", margin: 0,
  });

  addFooter(s, 4, 13);
}

// ---- SLIDE 5: PHASES 1-3 (Months 1-2) -----------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "Months 1-2: Set the foundation", "04 / Phases 1-3");

  // Three columns
  const cols = [
    {
      n: "1", title: "Governance & Scope", months: "Month 1",
      bullets: [
        "Confirm SPOCs on both sides",
        "Agree 10-model delivery sequence",
        "Lock run cadence per model",
        "Agree PIR + sign-off checkpoints",
        "ABSA shares approved model docs + code + benchmarks",
      ],
      gate: "SPOCs identified, scope sign-off",
    },
    {
      n: "2", title: "Architecture & Connectivity", months: "Months 1-2",
      bullets: [
        "ABSA architecture sign-off",
        "EXL provisions AWS landing zones",
        "Cross-account IAM trust established",
        "Encrypted S3 replication path validated",
        "SSO federation tested + signed off",
      ],
      gate: "Real account IDs + IAM principals exchanged",
    },
    {
      n: "3", title: "Data & Code Readiness", months: "Months 1-2",
      bullets: [
        "ABSA freezes input variables",
        "ABSA prepares signed code package",
        "First code+data+benchmark transferred to EXL",
        "EXL validates receipt via code-intake",
        "EXL runs schema + drift quality checks",
      ],
      gate: "First model accepted by code-intake",
    },
  ];

  cols.forEach((c, i) => {
    const x = 0.6 + i * 4.25;
    // Card
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.2, w: 3.95, h: 5.6,
      fill: { color: C.WHITE }, line: { color: C.ICE, width: 0.75 },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
    });
    // Numbered circle
    s.addShape(pres.shapes.OVAL, {
      x: x + 0.25, y: 1.4, w: 0.55, h: 0.55,
      fill: { color: C.NAVY }, line: { color: C.NAVY },
    });
    s.addText(c.n, {
      x: x + 0.25, y: 1.4, w: 0.55, h: 0.55,
      fontFace: FONT_HEAD, fontSize: 18, bold: true, color: C.WHITE,
      align: "center", valign: "middle", margin: 0,
    });
    s.addText(c.title, {
      x: x + 0.95, y: 1.4, w: 2.9, h: 0.55,
      fontFace: FONT_HEAD, fontSize: 16, bold: true, color: C.NAVY, valign: "middle", margin: 0,
    });
    s.addText(c.months, {
      x: x + 0.25, y: 2.05, w: 3.5, h: 0.3,
      fontFace: FONT_BODY, fontSize: 11, italic: true, color: C.SLATE, margin: 0,
    });
    // Bullets
    const bullets = c.bullets.map((b, idx) => ({
      text: b,
      options: { bullet: true, color: C.CHARCOAL, breakLine: idx < c.bullets.length - 1 },
    }));
    s.addText(bullets, {
      x: x + 0.25, y: 2.5, w: 3.5, h: 3.0,
      fontFace: FONT_BODY, fontSize: 11.5, paraSpaceAfter: 4, margin: 0,
    });
    // Gate strip
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 6.0, w: 3.95, h: 0.8,
      fill: { color: C.BG }, line: { color: C.BG },
    });
    s.addText("GATE TO NEXT PHASE", {
      x: x + 0.25, y: 6.05, w: 3.5, h: 0.25,
      fontFace: FONT_BODY, fontSize: 8.5, bold: true, color: C.SLATE, charSpacing: 4, margin: 0,
    });
    s.addText(c.gate, {
      x: x + 0.25, y: 6.32, w: 3.5, h: 0.4,
      fontFace: FONT_BODY, fontSize: 11, bold: true, color: C.NAVY, margin: 0,
    });
  });

  addFooter(s, 5, 13);
}

// ---- SLIDE 6: PHASE 4 & 5 (Platform + Controls) ------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "Months 2-6: Platform & Controls", "05 / Phases 4 & 5");

  // Phase 4 left
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 1.15, w: 7.5, h: 5.65,
    fill: { color: C.WHITE }, line: { color: C.ICE, width: 0.75 },
    shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 1.15, w: 0.12, h: 5.65, fill: { color: C.NAVY }, line: { color: C.NAVY },
  });
  s.addText("Phase 4: Platform Foundation Build", {
    x: 0.85, y: 1.3, w: 7.2, h: 0.45,
    fontFace: FONT_HEAD, fontSize: 18, bold: true, color: C.NAVY, margin: 0,
  });
  s.addText("Months 2-3  •  EXL leads, ABSA consulted on key choices", {
    x: 0.85, y: 1.75, w: 7.2, h: 0.3,
    fontFace: FONT_BODY, fontSize: 11, italic: true, color: C.SLATE, margin: 0,
  });

  const p4 = [
    ["Landing zone + networking", "Multi-account topology per ADR-0004; baseline IAM/KMS"],
    ["Model registry + version control", "FastAPI registry + DynamoDB; approval state machine"],
    ["Pipeline templates", "Standard-batch / Scalable-batch / Realtime placeholder ready"],
    ["CI/CD + drift gates", "GitHub Actions workflows publishing signed manifests"],
    ["Audit + observability", "Append-only event log + LocalStack-based regression demo"],
    ["Infrastructure-as-Code", "Terraform modules for every component, per-env stacks"],
  ];
  p4.forEach((row, i) => {
    const y = 2.2 + i * 0.7;
    s.addShape(pres.shapes.OVAL, {
      x: 0.95, y: y + 0.05, w: 0.2, h: 0.2,
      fill: { color: C.CORAL }, line: { color: C.CORAL },
    });
    s.addText(row[0], {
      x: 1.25, y, w: 2.6, h: 0.35,
      fontFace: FONT_BODY, fontSize: 12, bold: true, color: C.NAVY, margin: 0,
    });
    s.addText(row[1], {
      x: 3.85, y, w: 4.2, h: 0.6,
      fontFace: FONT_BODY, fontSize: 10.5, color: C.CHARCOAL, lineSpacingMultiple: 1.25, margin: 0,
    });
  });

  // Phase 5 right
  s.addShape(pres.shapes.RECTANGLE, {
    x: 8.35, y: 1.15, w: 4.55, h: 5.65,
    fill: { color: C.BG }, line: { color: C.ICE, width: 0.75 },
    shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 8.35, y: 1.15, w: 0.12, h: 5.65, fill: { color: C.CORAL }, line: { color: C.CORAL },
  });
  s.addText("Phase 5: Controls & Change Management", {
    x: 8.6, y: 1.3, w: 4.2, h: 0.7,
    fontFace: FONT_HEAD, fontSize: 16, bold: true, color: C.NAVY, margin: 0,
  });
  s.addText("Months 2-6  •  Cross-cutting", {
    x: 8.6, y: 2.0, w: 4.2, h: 0.3,
    fontFace: FONT_BODY, fontSize: 11, italic: true, color: C.SLATE, margin: 0,
  });
  s.addText([
    { text: "Change-request workflow + approval matrix", options: { bullet: true, breakLine: true, color: C.CHARCOAL } },
    { text: "Peer review + promotion gates for production", options: { bullet: true, breakLine: true, color: C.CHARCOAL } },
    { text: "Rollback requirements per change", options: { bullet: true, breakLine: true, color: C.CHARCOAL } },
    { text: "Data retention + archival rules", options: { bullet: true, breakLine: true, color: C.CHARCOAL } },
    { text: "Secure access controls for delivery endpoints", options: { bullet: true, breakLine: true, color: C.CHARCOAL } },
    { text: "Release logging in agreed tracking tool", options: { bullet: true, color: C.CHARCOAL } },
  ], {
    x: 8.6, y: 2.4, w: 4.2, h: 4.3,
    fontFace: FONT_BODY, fontSize: 11, paraSpaceAfter: 5, margin: 0,
  });

  addFooter(s, 6, 13);
}

// ---- SLIDE 7: PHASES 6 + 7 (CRITICAL) -----------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "Months 3-4: Optimize, then prove it", "06 / Phases 6 & 7");

  // Phase 6
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 1.2, w: 6.0, h: 5.6,
    fill: { color: C.WHITE }, line: { color: C.ICE, width: 0.75 },
    shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 1.2, w: 0.12, h: 5.6, fill: { color: C.NAVY }, line: { color: C.NAVY },
  });
  s.addText("Phase 6: Code Optimization & Pipeline Setup", {
    x: 0.85, y: 1.35, w: 5.6, h: 0.5,
    fontFace: FONT_HEAD, fontSize: 16, bold: true, color: C.NAVY, margin: 0,
  });
  s.addText("Months 3-4  •  EXL leads", {
    x: 0.85, y: 1.85, w: 5.6, h: 0.3,
    fontFace: FONT_BODY, fontSize: 11, italic: true, color: C.SLATE, margin: 0,
  });
  s.addText([
    { text: "Review developer code for production readiness", options: { bullet: true, breakLine: true } },
    { text: "Standardize + optimize model scoring code", options: { bullet: true, breakLine: true } },
    { text: "Validate scoring logic vs dev benchmarks", options: { bullet: true, breakLine: true } },
    { text: "Package scoring code for controlled deployment", options: { bullet: true, breakLine: true } },
    { text: "Create reusable scoring pipeline templates", options: { bullet: true, breakLine: true } },
    { text: "Register models + pipeline versions in registry", options: { bullet: true, breakLine: true } },
    { text: "Set up model run schedules", options: { bullet: true } },
  ], {
    x: 0.95, y: 2.3, w: 5.5, h: 4.3,
    fontFace: FONT_BODY, fontSize: 11.5, color: C.CHARCOAL, paraSpaceAfter: 5, margin: 0,
  });

  // Phase 7 - critical
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.8, y: 1.2, w: 6.1, h: 5.6,
    fill: { color: C.NAVY }, line: { color: C.NAVY },
    shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.18 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.8, y: 1.2, w: 0.12, h: 5.6, fill: { color: C.CORAL }, line: { color: C.CORAL },
  });
  s.addText("CRITICAL MILESTONE", {
    x: 7.05, y: 1.35, w: 5.6, h: 0.35,
    fontFace: FONT_BODY, fontSize: 10, bold: true, color: C.CORAL,
    charSpacing: 4, margin: 0,
  });
  s.addText("Phase 7: Group 1 — First 2 models", {
    x: 7.05, y: 1.75, w: 5.6, h: 0.5,
    fontFace: FONT_HEAD, fontSize: 18, bold: true, color: C.WHITE, margin: 0,
  });
  s.addText("Month 4  •  Joint EXL + ABSA  •  Gates Group 2 + steady state", {
    x: 7.05, y: 2.25, w: 5.6, h: 0.3,
    fontFace: FONT_BODY, fontSize: 11, italic: true, color: C.ICE, margin: 0,
  });

  s.addText("Why this is critical", {
    x: 7.05, y: 2.7, w: 5.6, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 13, bold: true, color: C.ICE, margin: 0,
  });
  s.addText(
    "Group 1 is the proof point. We prove the chain end-to-end on two real models — intake, sign, score, reconcile, PIR — before scaling to the remaining 8. ABSA sign-off here unlocks every downstream phase.",
    {
      x: 7.05, y: 3.1, w: 5.6, h: 1.6,
      fontFace: FONT_BODY, fontSize: 11.5, color: C.WHITE, lineSpacingMultiple: 1.35, margin: 0,
    }
  );

  s.addText("Exit criteria", {
    x: 7.05, y: 4.85, w: 5.6, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 13, bold: true, color: C.ICE, margin: 0,
  });
  s.addText([
    { text: "Outputs reconcile to ABSA benchmarks", options: { bullet: true, breakLine: true, color: C.WHITE } },
    { text: "Defects resolved, PIR complete", options: { bullet: true, breakLine: true, color: C.WHITE } },
    { text: "ABSA Risk Owner sign-off in writing", options: { bullet: true, color: C.WHITE } },
  ], {
    x: 7.25, y: 5.25, w: 5.4, h: 1.4,
    fontFace: FONT_BODY, fontSize: 11.5, paraSpaceAfter: 4, margin: 0,
  });

  addFooter(s, 7, 13);
}

// ---- SLIDE 8: PHASES 8 + 9 (Group 2, Dashboards, Steady State) ----------
{
  const s = lightSlide();
  addTitleStrip(s, "Months 5-7+: Scale + steady state", "07 / Phases 8 & 9");

  const sections = [
    {
      title: "Group 2: Remaining 8 models", months: "Months 5-6", color: C.NAVY,
      points: [
        "Group 1 templates reused",
        "Parallel onboarding stream",
        "Per-model PIR + reconciliation",
        "ABSA sign-off closes initial scope",
      ],
    },
    {
      title: "Dashboards & Delivery", months: "Months 5-6", color: C.DEEP,
      points: [
        "Monitoring dashboard for runs + exceptions",
        "Alert routing for failures",
        "Secure output delivery to ABSA",
        "Operational runbooks + handover material",
      ],
    },
    {
      title: "Steady State Support", months: "Month 7+", color: C.GREEN,
      points: [
        "Scheduled daily/weekly/monthly scoring",
        "Audit trail per run + delivery",
        "Drift + anomaly review cadence",
        "Quarterly service review with ABSA",
      ],
    },
    {
      title: "New Model Onboarding", months: "Month 7+", color: C.GREEN,
      points: [
        "Template-driven for same model family",
        "Type-specific controls for new categories",
        "Validation + scoring + PIR per model",
        "Register + schedule new approved models",
      ],
    },
  ];

  sections.forEach((sec, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.6 + col * 6.35;
    const y = 1.2 + row * 2.95;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 6.1, h: 2.7,
      fill: { color: C.WHITE }, line: { color: C.ICE, width: 0.75 },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.12, h: 2.7,
      fill: { color: sec.color }, line: { color: sec.color },
    });

    s.addText(sec.title, {
      x: x + 0.3, y: y + 0.15, w: 5.7, h: 0.4,
      fontFace: FONT_HEAD, fontSize: 16, bold: true, color: C.NAVY, margin: 0,
    });
    s.addText(sec.months, {
      x: x + 0.3, y: y + 0.55, w: 5.7, h: 0.25,
      fontFace: FONT_BODY, fontSize: 10.5, italic: true, color: C.SLATE, margin: 0,
    });
    const bullets = sec.points.map((p, idx) => ({
      text: p, options: { bullet: true, color: C.CHARCOAL, breakLine: idx < sec.points.length - 1 },
    }));
    s.addText(bullets, {
      x: x + 0.35, y: y + 0.9, w: 5.6, h: 1.75,
      fontFace: FONT_BODY, fontSize: 11.5, paraSpaceAfter: 4, margin: 0,
    });
  });

  addFooter(s, 8, 13);
}

// ---- SLIDE 9: OWNERSHIP ------------------------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "Who owns what", "08 / Ownership across the program");

  const lanes = [
    { who: "ABSA owns", color: C.CORAL, items: [
      "Architecture sign-off + internal cloud approvals",
      "Source datasets, input variables, signed code packages",
      "Benchmark outputs for reconciliation",
      "IP whitelisting + connectivity details",
      "Group 1 & Group 2 sign-off (PIR closure)",
      "Approving new model onboarding requests",
    ]},
    { who: "EXL delivers", color: C.NAVY, items: [
      "AWS landing zone, IAM, KMS, secrets",
      "Model registry + pipeline templates",
      "Code intake validation + manifest signing",
      "Scoring runtime + audit trail",
      "Monitoring dashboards + alerting",
      "Operational runbooks + handover material",
    ]},
    { who: "Both run jointly", color: C.SLATE, items: [
      "Governance, scope, RACI, cadence",
      "Cross-account IAM trust + SSO",
      "Encrypted transfer validation",
      "Change management + approval matrix",
      "PIR + benchmark reconciliation",
      "Quarterly service review",
    ]},
  ];

  lanes.forEach((lane, i) => {
    const x = 0.6 + i * 4.25;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.2, w: 3.95, h: 5.6,
      fill: { color: C.WHITE }, line: { color: C.ICE, width: 0.75 },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.2, w: 3.95, h: 0.7, fill: { color: lane.color }, line: { color: lane.color },
    });
    s.addText(lane.who, {
      x, y: 1.2, w: 3.95, h: 0.7,
      fontFace: FONT_HEAD, fontSize: 18, bold: true, color: C.WHITE,
      align: "center", valign: "middle", margin: 0,
    });

    const bullets = lane.items.map((p, idx) => ({
      text: p, options: { bullet: true, color: C.CHARCOAL, breakLine: idx < lane.items.length - 1 },
    }));
    s.addText(bullets, {
      x: x + 0.3, y: 2.15, w: 3.55, h: 4.5,
      fontFace: FONT_BODY, fontSize: 11.5, paraSpaceAfter: 6, margin: 0,
    });
  });

  addFooter(s, 9, 13);
}

// ---- SLIDE 10: KEY RISKS -----------------------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "Key risks & mitigations", "09 / Top 5 we're actively managing");

  const risks = [
    { sev: "HIGH",   desc: "ABSA account onboarding (real account IDs + IAM principal ARNs) delayed",
      mit: "Pre-stage Terraform; LocalStack-based regression demo keeps CI green; escalate by end Month 1" },
    { sev: "HIGH",   desc: "Group 1 sign-off slips, cascading into Group 2 + steady state",
      mit: "Use Group 1 as dress rehearsal; pre-stage Group 2 templates so the ramp doesn't wait" },
    { sev: "HIGH",   desc: "ML compute platform choice (SFN+Lambda vs SageMaker) blocks Phase 4",
      mit: "Decision required end of Month 2; surface to architecture review board this week" },
    { sev: "MEDIUM", desc: "Benchmark reconciliation discrepancies force scoring-code rewrite",
      mit: "Validate scoring logic incrementally during code optimization; record per-feature deltas" },
    { sev: "MEDIUM", desc: "Data quality issues (drift, schema mismatch) in initial intake",
      mit: "Run code-intake validate on first arrival; reject + return to ABSA the same day" },
  ];

  const headerY = 1.15;
  const headers = ["Severity", "Risk description", "Mitigation"];
  const xs = [0.6, 2.0, 7.6];
  const widths = [1.4, 5.6, 5.3];

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: headerY, w: 12.3, h: 0.5,
    fill: { color: C.NAVY }, line: { color: C.NAVY },
  });
  headers.forEach((h, i) => {
    s.addText(h, {
      x: xs[i] + 0.1, y: headerY, w: widths[i] - 0.2, h: 0.5,
      fontFace: FONT_BODY, fontSize: 11, bold: true, color: C.WHITE,
      valign: "middle", margin: 0,
    });
  });

  risks.forEach((r, i) => {
    const y = headerY + 0.5 + i * 1.05;
    if (i % 2 === 0) {
      s.addShape(pres.shapes.RECTANGLE, {
        x: 0.6, y, w: 12.3, h: 1.05,
        fill: { color: C.BAND }, line: { color: C.BAND },
      });
    }
    // sev pill
    const sevColor = r.sev === "HIGH" ? C.CORAL : C.AMBER;
    pill(s, xs[0] + 0.15, y + 0.2, 1.1, 0.4, r.sev, sevColor, C.WHITE);
    // description
    s.addText(r.desc, {
      x: xs[1] + 0.1, y: y + 0.12, w: widths[1] - 0.2, h: 0.85,
      fontFace: FONT_BODY, fontSize: 11.5, color: C.CHARCOAL, valign: "middle", lineSpacingMultiple: 1.25, margin: 0,
    });
    // mitigation
    s.addText(r.mit, {
      x: xs[2] + 0.1, y: y + 0.12, w: widths[2] - 0.2, h: 0.85,
      fontFace: FONT_BODY, fontSize: 11, color: C.SLATE, valign: "middle", italic: true, lineSpacingMultiple: 1.25, margin: 0,
    });
  });

  addFooter(s, 10, 13);
}

// ---- SLIDE 11: WHAT WE HAVE ALREADY BUILT -------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "What we've already built", "10 / Platform ready today");

  s.addText(
    "We aren't starting from zero. The hosting platform is built end-to-end and runs the\nfull chain locally every PR — code intake to verifier — so day 1 of real onboarding\nis configuration, not construction.",
    {
      x: 0.6, y: 1.15, w: 12.3, h: 1.0,
      fontFace: FONT_BODY, fontSize: 13, color: C.CHARCOAL, lineSpacingMultiple: 1.3, margin: 0,
    }
  );

  const items = [
    { t: "Code Intake validator",      d: "5 checkers (Python static, SAS structural, schema, tests, PIR) with per-package venv isolation" },
    { t: "Pipeline Factory",           d: "Deterministic ASL renderer with 3 templates (standard-batch, scalable-batch, realtime placeholder)" },
    { t: "Manifest Signer",            d: "KMS asymmetric signing + verify-online / verify-offline / verify-from-bucket CLIs" },
    { t: "Registry API",               d: "FastAPI + DynamoDB with approval state machine and append-only audit log" },
    { t: "LocalStack End-to-End Demo", d: "Full producer + verifier chain runs in CI on every PR; sample transcript committed" },
    { t: "Ops Runbooks",               d: "KMS key rotation, LocalStack demo, day-2 operating procedures" },
  ];

  items.forEach((it, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.6 + col * 6.35;
    const y = 2.4 + row * 1.45;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 6.1, h: 1.25,
      fill: { color: C.WHITE }, line: { color: C.ICE, width: 0.75 },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.06 },
    });
    s.addShape(pres.shapes.OVAL, {
      x: x + 0.25, y: y + 0.32, w: 0.6, h: 0.6,
      fill: { color: C.GREEN }, line: { color: C.GREEN },
    });
    s.addText("✓", {
      x: x + 0.25, y: y + 0.32, w: 0.6, h: 0.6,
      fontFace: FONT_HEAD, fontSize: 24, bold: true, color: C.WHITE,
      align: "center", valign: "middle", margin: 0,
    });
    s.addText(it.t, {
      x: x + 1.0, y: y + 0.2, w: 5.0, h: 0.4,
      fontFace: FONT_HEAD, fontSize: 14, bold: true, color: C.NAVY, margin: 0,
    });
    s.addText(it.d, {
      x: x + 1.0, y: y + 0.6, w: 5.0, h: 0.65,
      fontFace: FONT_BODY, fontSize: 10.5, color: C.CHARCOAL, lineSpacingMultiple: 1.3, margin: 0,
    });
  });

  addFooter(s, 11, 13);
}

// ---- SLIDE 12: WHAT ABSA NEEDS TO PROVIDE -------------------------------
{
  const s = lightSlide();
  addTitleStrip(s, "What we need from ABSA", "11 / Unblocks real Phase 2-7");

  s.addText(
    "These seven items unblock the real Phase 2-7 work. Until they arrive, the LocalStack\ndemo keeps the platform regression-tested but we cannot move scoring to real AWS.",
    {
      x: 0.6, y: 1.15, w: 12.3, h: 0.85,
      fontFace: FONT_BODY, fontSize: 12.5, color: C.CHARCOAL, lineSpacingMultiple: 1.35, margin: 0,
    }
  );

  const asks = [
    "AWS Account IDs (ABSA receiving accounts + any additional EXL accounts)",
    "IAM Principal ARNs requiring kms:Verify, kms:GetPublicKey, s3:GetObject access",
    "SAS runtime (Docker image + license terms) for full SAS validation",
    "PIR system contract (API spec or feed format for the mapping authority)",
    "Data movement choice (S3 cross-account replication vs SFTP)",
    "CAB / IVU API contract for governance integration",
    "Network connectivity decision (VPC peering / Transit Gateway / PrivateLink)",
  ];

  // Numbered list with strong visual treatment
  asks.forEach((a, i) => {
    const y = 2.25 + i * 0.62;
    // Number circle
    s.addShape(pres.shapes.OVAL, {
      x: 0.7, y: y - 0.02, w: 0.5, h: 0.5,
      fill: { color: C.NAVY }, line: { color: C.NAVY },
    });
    s.addText(`${i + 1}`, {
      x: 0.7, y: y - 0.02, w: 0.5, h: 0.5,
      fontFace: FONT_HEAD, fontSize: 16, bold: true, color: C.WHITE,
      align: "center", valign: "middle", margin: 0,
    });
    s.addText(a, {
      x: 1.4, y, w: 11.4, h: 0.5,
      fontFace: FONT_BODY, fontSize: 13, color: C.CHARCOAL, valign: "middle", margin: 0,
    });
  });

  addFooter(s, 12, 13);
}

// ---- SLIDE 13: NEXT STEPS -----------------------------------------------
{
  const s = darkSlide();

  // Big eyebrow
  s.addText("NEXT STEPS", {
    x: 0.7, y: 0.9, w: 12, h: 0.5,
    fontFace: FONT_BODY, fontSize: 14, bold: true, color: C.ICE,
    charSpacing: 6, margin: 0,
  });
  s.addText("Where we go from here", {
    x: 0.7, y: 1.4, w: 12, h: 0.9,
    fontFace: FONT_HEAD, fontSize: 36, bold: true, color: C.WHITE, margin: 0,
  });

  const steps = [
    { n: "01", t: "This week", d: "Confirm SPOCs and circulate the master task tracker. Schedule the kickoff with steering committee." },
    { n: "02", t: "Next 2 weeks", d: "Lock open decisions: ML compute platform, data-movement path, real-time tier SLA. Architecture sign-off." },
    { n: "03", t: "Next 30 days", d: "ABSA shares Group 1 model code + benchmarks. EXL stands up landing zones. First package validated via code-intake." },
    { n: "04", t: "Next 90 days", d: "Platform built. Code optimized. Group 1 onboarded and reconciled. ABSA sign-off targeted end of Month 4." },
  ];

  steps.forEach((step, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.7 + col * 6.2;
    const y = 2.6 + row * 1.95;

    // Step number in big italic
    s.addText(step.n, {
      x, y, w: 1.2, h: 0.7,
      fontFace: FONT_HEAD, fontSize: 36, bold: true, italic: true, color: C.CORAL, margin: 0,
    });
    s.addText(step.t, {
      x: x + 1.3, y: y + 0.05, w: 4.5, h: 0.45,
      fontFace: FONT_HEAD, fontSize: 18, bold: true, color: C.WHITE, margin: 0,
    });
    s.addText(step.d, {
      x: x + 1.3, y: y + 0.55, w: 4.6, h: 1.4,
      fontFace: FONT_BODY, fontSize: 12, color: C.ICE, lineSpacingMultiple: 1.35, margin: 0,
    });
  });

  // Bottom Q&A strip
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.7, y: 6.7, w: 11.9, h: 0.6,
    fill: { color: C.CORAL }, line: { color: C.CORAL },
  });
  s.addText("Questions? Reach the Program Office or your assigned SPOC.", {
    x: 0.7, y: 6.7, w: 11.9, h: 0.6,
    fontFace: FONT_HEAD, fontSize: 14, bold: true, color: C.WHITE,
    align: "center", valign: "middle", margin: 0,
  });
}

// ---- save --------------------------------------------------------------
const outPath = path.join(__dirname, "..", "docs", "absa-exl-program-walkthrough.pptx");
pres.writeFile({ fileName: outPath }).then((file) => {
  console.log("Wrote", file);
});
