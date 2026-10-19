// Builds Orbit_Observers_Pitch.pptx (structured deck: theme, layouts, placeholders, sections). Run: node build_deck.js
const fs = require("fs"), path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/Users/siddharthpatni/.claude/skills/synced/48c620f4-3846-49cd-9f55-2b2587cf21b2_42dc88de-7dc0-4e87-a578-f458db598652/pptx/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "../..");
const THEME = { name: "Orbital Notation", headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: "05070C", lt1: "DFE8F5", dk2: "0B1220", lt2: "8FA6C8", accent1: "5AD1FF", accent2: "FFB454", accent3: "7DFFB2", accent4: "FF8F8F", accent5: "7AA2FF", accent6: "243651", hlink: "5AD1FF", folHlink: "8FA6C8" } };
const pres = new pptxgen(); pres.layout = "LAYOUT_WIDE"; pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Orbit Observers pitch"; pres.author = "Orbit Observers"; pres.company = "Orbit Observers";
const C = pres.SchemeColor, W = 13.33, H = 7.5, M = 0.6;

// ---- layouts (frame only) ----
pres.defineSlideMaster({ title: "TITLE_ONLY", background: { color: C.text1 }, slideNumber: { x: W - 1.1, y: H - 0.45, w: 0.6, h: 0.3, fontSize: 10, color: C.background2, align: "right" },
  objects: [
    { text: { text: "Orbit Observers  |  model-based study, assumed parameters, not flight-qualified", options: { x: M, y: H - 0.45, w: 9, h: 0.3, fontSize: 10, color: C.background2, margin: 0 } } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.4, w: W - 2 * M, h: 0.9, fontSize: 32, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } }] });
pres.defineSlideMaster({ title: "DIVIDER", background: { color: C.text1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: M, y: 2.6, w: W - 2 * M, h: 1.4, fontSize: 54, bold: true, color: C.background1, margin: 0, align: "left" }, text: "" } }] });

const T = (s, text) => s.addText(text, { placeholder: "title" });
const box = (s, x, y, w, h, name, fill = C.text2) => s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: C.accent6, width: 1 }, objectName: name });
const txt = (s, text, o) => s.addText(text, Object.assign({ isTextBox: true, margin: 0, color: C.background1, fontSize: 16, valign: "top" }, o));
const stat = (s, x, y, w, num, label, color) => { txt(s, num, { x, y, w, h: 0.9, fontSize: 48, bold: true, color }); txt(s, label, { x, y: y + 0.95, w, h: 0.7, fontSize: 14, color: C.background2 }); };

// ---- data for the chart (v4.1, 100 paired seeds per cell) ----
const rows = fs.readFileSync(path.join(ROOT, "results/v4_1_validation/summary_main.csv"), "utf8").trim().split("\n"); const hdr = rows[0].split(",");
const idx = k => hdr.indexOf(k), get = (tier, t) => { const r = rows.slice(1).map(l => l.split(",")).find(c => c[0] === tier && +c[1] === t); return r ? +r[idx("p_terminal_pass")] * 100 : null; };
const tumbles = [0, 0.25, 0.5, 1, 2, 3, 5];
const series = [["C0 unprepared", "C0_unprepared"], ["C1 markers", "C1_fiducials"], ["C2 marker + rate beacon", "C2_beacon"], ["C3 IOS mode", "C3_ios_mode"]].map(([name, k]) => ({ name, labels: tumbles.map(String), values: tumbles.map(t => get(k, t)) }));

let s;
// 1 title
pres.addSection({ title: "Open" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Open" });
T(s, "Orbit Observers");
txt(s, "Satellites that stay serviceable, even on their worst day", { x: M, y: 1.5, w: 5.6, h: 1.2, fontSize: 24, color: C.accent1 });
txt(s, "The minimum client-side preparation that keeps a satellite serviceable when it is healthy, degraded or tumbling. Not another docking port.", { x: M, y: 3.0, w: 5.4, h: 1.6, fontSize: 18 });
txt(s, "Business  /  Technical  /  Serviceability", { x: M, y: 5.2, w: 5.6, h: 0.4, fontSize: 16, color: C.accent2 });
s.addMedia({ type: "video", path: path.join(ROOT, "media/orbit_observers_intro.mp4"), x: 6.7, y: 1.5, w: 6.0, h: 3.375, objectName: "Intro video" });
s.addNotes("0:00. We are Orbit Observers. We make satellites serviceable on their worst day. (The 10 second video plays here.)");

// 2 problem
pres.addSection({ title: "Serviceability" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Serviceability" }); T(s, "Most satellites were never designed to be grabbed");
box(s, M, 1.6, 3.9, 3.9, "Card legacy"); txt(s, "Legacy clients", { x: M + 0.3, y: 1.85, w: 3.3, h: 0.4, fontSize: 24, bold: true, color: C.accent1 });
txt(s, "Often non-cooperative. No standard capture or service interface. Safe-mode behaviour can fight a servicer.", { x: M + 0.3, y: 2.45, w: 3.3, h: 2.9, fontSize: 19 });
box(s, M + 4.25, 1.6, 3.9, 3.9, "Card gap"); txt(s, "The last 12 metres", { x: M + 4.55, y: 1.85, w: 3.3, h: 0.4, fontSize: 22, bold: true, color: C.accent1 });
txt(s, "A tumbling client, a noisy camera and an unknown spin rate. The servicer carries all the risk and cost.", { x: M + 4.55, y: 2.45, w: 3.3, h: 2.9, fontSize: 19 });
box(s, M + 8.5, 1.6, 3.63, 3.9, "Card shift"); txt(s, "The GEO shift", { x: M + 8.8, y: 1.85, w: 3.1, h: 0.4, fontSize: 22, bold: true, color: C.accent1 });
txt(s, "Chemical to hybrid to all-electric removes the accidental nozzle and ring features servicers used. Future satellites need a deliberate interface.", { x: M + 8.8, y: 2.45, w: 3.1, h: 2.9, fontSize: 19 });
s.addNotes("0:15. Most GEO satellites were never designed to be grabbed. When one tumbles the servicer carries all the risk in the last twelve metres, and electric platforms remove the accidental features servicers used. We ask: what is the minimum a client must carry to stay serviceable?");

// 3 serviceability states
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Serviceability" }); T(s, "Three client states, five layers of preparation");
const states = [["Nominal", "Healthy, controlled, talking", "IOS mode: control handed to the servicer", "C3", C.accent3], ["Degraded", "Partial computer, power or comms", "Independent Service Beacon: rate, ID, health", "C2", C.accent2], ["Tumbling", "No control, no comms", "Markers and a known capture point", "C1", C.accent1]];
states.forEach(([n, d, e, c, col], i) => { const x = M + i * 4.1; box(s, x, 1.6, 3.9, 3.3, "State " + n);
  txt(s, c, { x: x + 0.3, y: 1.8, w: 1, h: 0.6, fontSize: 32, bold: true, color: col }); txt(s, n, { x: x + 1.3, y: 1.9, w: 2.4, h: 0.5, fontSize: 24, bold: true });
  txt(s, d, { x: x + 0.3, y: 2.6, w: 3.3, h: 0.7, fontSize: 16, color: C.background2 }); txt(s, e, { x: x + 0.3, y: 3.4, w: 3.3, h: 1.3, fontSize: 18 }); });
box(s, M, 5.2, W - 2 * M, 1.2, "OSAN strip");
txt(s, "OSAN service zone for high-value platforms: capture and load transfer, power and data, optional fluid transfer, POD attachment. Concept only; no loads or layout yet.", { x: M + 0.3, y: 5.4, w: W - 2 * M - 0.6, h: 0.8, fontSize: 16 });
s.addNotes("0:50. Three states: healthy, degraded, tumbling. Five layers: markers, a capture point, an independent beacon, an IOS handover mode, and a service zone. Each keeps the satellite serviceable one step further.");

// 4 envelope chart
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Serviceability" }); T(s, "Preparation matters where an unprepared client starts to fail");
s.addChart(pres.charts.LINE, series.map(x => ({ name: x.name, labels: x.labels, values: x.values })), { x: M, y: 1.45, w: 8.3, h: 5.0, chartColors: ["FF8F8F", "FFB454", "7DFFB2", "5AD1FF"], lineSize: 3, lineDataSymbolSize: 7,
  showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: "DFE8F5", legendFontFace: "+mn-lt", showTitle: true, title: "Terminal window met, % of 100 paired seeds, by tumble rate (deg/s)", titleFontSize: 14, titleColor: "DFE8F5", titleFontFace: "+mn-lt",
  catAxisLabelColor: "8FA6C8", valAxisLabelColor: "8FA6C8", catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 12, valAxisLabelFontSize: 12, valAxisMinVal: 0, valAxisMaxVal: 100, valGridLine: { color: "243651", size: 0.75 }, catGridLine: { style: "none" } });
stat(s, 9.3, 1.6, 3.4, "+51 pp", "at 3 deg/s: unprepared 41% to markers 92%", C.accent2);
stat(s, 9.3, 3.35, 3.4, "+8 pp", "rate data in the beacon: 92% to 100% (p = 0.008)", C.accent3);
stat(s, 9.3, 5.1, 3.4, "5 deg/s", "only a cooperating client passes (C3 assumes self-damping)", C.accent1);
s.addNotes("1:30. At three degrees per second an unprepared client reaches the terminal window 41 percent of the time, with markers 92, with a rate beacon 100. An identity-only radio adds nothing; rate information does. Above five degrees only a cooperating client works. v4.1, 100 seeds per cell; v4.0 gave 41.6, 91.8, 100 with 500 seeds.");

// 5 architecture
pres.addSection({ title: "Technical" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Technical" }); T(s, "One system from ground approval to client handover");
const cols = [["Ground", ["Dashboard and AI agents", "Policy and human approval", "Hash-chained audit", "Monte Carlo feasibility"], C.accent2], ["Servicer", ["Estimator on estimates only", "Hold point, braking approach", "Abort gates and retreat", "On-board log and downlink"], C.accent1], ["Client", ["Markers and capture point", "Independent beacon", "IOS state machine", "Fuel gauge: book-keeping + PVT"], C.accent3]];
cols.forEach(([n, items, col], i) => { const x = M + i * 4.3; box(s, x, 1.6, 3.5, 3.9, "Col " + n); txt(s, n, { x: x + 0.3, y: 1.8, w: 2.9, h: 0.5, fontSize: 26, bold: true, color: col });
  txt(s, items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1, paraSpaceAfter: 8 } })), { x: x + 0.3, y: 2.5, w: 2.9, h: 2.8, fontSize: 16 });
  if (i < 2) s.addShape(pres.ShapeType.rightArrow, { x: x + 3.55, y: 3.3, w: 0.7, h: 0.4, fill: { color: C.accent6 }, line: { color: C.accent6 }, objectName: "Arrow " + i }); });
box(s, M, 5.8, W - 2 * M, 0.9, "Rule strip"); txt(s, "Rules built in: flight logic never sees truth. Humans approve every high-risk step. IOS handover needs a human-approved gate and aborts from any state.", { x: M + 0.3, y: 5.97, w: W - 2 * M - 0.6, h: 0.6, fontSize: 16 });
s.addNotes("2:15. One system: a ground platform with human approval, a servicer and a prepared client. Flight logic never sees truth. The IOS handover is gated by human approval and aborts from any state.");

// 6 proof
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Technical" }); T(s, "Built, tested, and honest about its limits");
stat(s, M, 1.55, 2.8, "74", "automated tests pass", C.accent3); stat(s, M + 3.0, 1.55, 2.8, "41,240", "simulated approaches (35,100 + 6,140)", C.accent1); stat(s, M + 6.0, 1.55, 2.8, "0 / 6,140", "keep-out violations (a count, not a bound)", C.accent2); stat(s, M + 9.0, 1.55, 3.1, "1.2 kg", "fuel gauge error from 800 kg", C.accent3);
box(s, M, 3.6, 5.9, 3.0, "Verified"); txt(s, "Verified", { x: M + 0.3, y: 3.8, w: 5.3, h: 0.4, fontSize: 20, bold: true, color: C.accent3 });
txt(s, ["Paired seeds, intervals, exact tests, replayable runs", "IOS coupled to the approach: approval gate, rate envelope, abort", "Beacon bench plan B1 to B7 with model-derived limits", "Leak and sensor faults flagged in 100 of 100 runs"].map((t, k, a) => ({ text: t, options: { bullet: true, breakLine: k < a.length - 1, paraSpaceAfter: 6 } })), { x: M + 0.3, y: 4.3, w: 5.3, h: 2.2, fontSize: 15 });
box(s, M + 6.2, 3.6, 5.93, 3.0, "Limits"); txt(s, "Not yet", { x: M + 6.5, y: 3.8, w: 5.3, h: 0.4, fontSize: 20, bold: true, color: C.accent4 });
txt(s, ["No contact or capture model: 'window met' is not a grab", "Retreat passive safety not established", "No hardware data; costs and noise are assumptions", "Authentication is a simulation token"].map((t, k, a) => ({ text: t, options: { bullet: true, breakLine: k < a.length - 1, paraSpaceAfter: 6 } })), { x: M + 6.5, y: 4.3, w: 5.3, h: 2.2, fontSize: 15 });
s.addNotes("2:45. 74 tests, reproducible campaigns on HPC, zero keep-out violations in 6,140 runs. This is a model: no contact physics, no hardware yet, and we say so on every slide.");

// 7 business offer
pres.addSection({ title: "Business" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Business" }); T(s, "A tiered kit that makers add at build time");
const tiers = [["1", "EOL-ready", "Capture fixture + markers", "0.36", "Removal"], ["2", "Service-ready", "+ IOS mode + beacon", "1.46", "Attached propulsion"], ["3", "Life-extension-ready", "+ refuelling port", "2.18", "Refuel and release"], ["4", "Augmentation-ready", "+ power, data, POD (OSAN)", "6.68", "Upgrade POD"]];
tiers.forEach(([n, name, prov, cost, opt], i) => { const x = M + i * 3.07; box(s, x, 1.6, 2.9, 3.9, "Tier " + n); txt(s, "Tier " + n, { x: x + 0.25, y: 1.8, w: 2.4, h: 0.4, fontSize: 14, color: C.background2 }); txt(s, name, { x: x + 0.25, y: 2.2, w: 2.4, h: 0.8, fontSize: 20, bold: true, color: C.accent1 });
  txt(s, prov, { x: x + 0.25, y: 3.05, w: 2.4, h: 0.8, fontSize: 15 }); txt(s, "EUR " + cost + " M", { x: x + 0.25, y: 3.95, w: 2.4, h: 0.5, fontSize: 24, bold: true, color: C.accent2 }); txt(s, "enables: " + opt, { x: x + 0.25, y: 4.55, w: 2.4, h: 0.7, fontSize: 14, color: C.background2 }); });
txt(s, "Buyers (hypotheses): satellite makers and operators for the kit; servicers for more successful visits per vehicle; insurers and regulators for reproducible evidence. Costs per unit are assumptions: unit price, mass, launch and shared development.", { x: M, y: 5.75, w: W - 2 * M, h: 0.9, fontSize: 15, color: C.background2 });
s.addNotes("3:15. Buyers are satellite makers and operators who add a tier at build time, and servicers who get more successful visits per vehicle. All costs here are assumptions.");

// 8 economics
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Business" }); T(s, "Markers repay almost at once; the beacon and IOS need more");
const hd = t => ({ text: t, options: { bold: true, color: "5AD1FF", fill: { color: "0B1220" }, fontSize: 14 } });
const cell = (t, o = {}) => ({ text: t, options: Object.assign({ color: "DFE8F5", fill: { color: "05070C" }, fontSize: 14 }, o) });
s.addTable([[hd("At 3 deg/s"), hd("Success within 3 tries"), hd("Add-on cost per client"), hd("Break-even P(needs rescue)"), hd("Servicer break-even price per success")],
  [cell("C0 unprepared"), cell("64%"), cell("EUR 0"), cell("n/a"), cell("EUR 32.0 M")],
  [cell("C1 markers"), cell("98%"), cell("EUR 45 k"), cell("0.6% vs C0"), cell("EUR 20.0 M")],
  [cell("C2 + rate beacon"), cell("100%"), cell("EUR 0.40 M"), cell("75% vs C1"), cell("EUR 19.6 M")],
  [cell("C3 IOS mode"), cell("100%"), cell("EUR 1.15 M"), cell("14.5% vs C0"), cell("EUR 19.6 M")]],
  { x: M, y: 1.6, w: W - 2 * M, colW: [2.6, 2.3, 2.3, 2.5, 2.43], border: { type: "solid", color: "243651", pt: 1 }, rowH: 0.5 });
box(s, M, 4.5, 5.9, 2.1, "Assumed"); txt(s, "Assumed inputs", { x: M + 0.3, y: 4.65, w: 5.3, h: 0.4, fontSize: 18, bold: true, color: C.accent2 });
txt(s, "Rescue worth EUR 20.8 M net (EUR 40 M a year, 60% margin, 5 years, 8% discount, EUR 75 M price). Every price and probability is ours, not a customer's.", { x: M + 0.3, y: 5.15, w: 5.3, h: 1.4, fontSize: 15 });
box(s, M + 6.2, 4.5, 5.93, 2.1, "Reading"); txt(s, "What to test first", { x: M + 6.5, y: 4.65, w: 5.3, h: 0.4, fontSize: 18, bold: true, color: C.accent3 });
txt(s, "How often a client degrades enough to need rescue. It drives every break-even. The beacon is likely undervalued: identity, interface and health data carry no value in the simulator.", { x: M + 6.5, y: 5.15, w: 5.3, h: 1.4, fontSize: 15 });
s.addNotes("With our assumed inputs, markers repay their cost if even 0.6 percent of clients ever need rescue. The beacon and IOS mode pay off where tumble is high or where data beyond approach matters. Source: docs/ECONOMICS_MODEL.md.");

// 9 competitors and regulation
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Business" }); T(s, "Others fix the servicer; we specify the client");
box(s, M, 1.6, 5.9, 4.6, "Competition"); txt(s, "Existing offers [to verify]", { x: M + 0.3, y: 1.8, w: 5.3, h: 0.4, fontSize: 20, bold: true, color: C.accent1 });
txt(s, ["Northrop Grumman MEV and MRV: life extension of unprepared GEO clients", "Astroscale: removal, inspection, docking plate on client", "Starfish Space: autonomous docking and inspection", "ClearSpace: capture of defunct objects", "Orbit Fab, MDA, Airbus, Thales Alenia, OHB: refuel ports, arms, interfaces"].map((t, k, a) => ({ text: t, options: { bullet: true, breakLine: k < a.length - 1, paraSpaceAfter: 8 } })), { x: M + 0.3, y: 2.4, w: 5.3, h: 3.5, fontSize: 17 });
box(s, M + 6.2, 1.6, 5.93, 4.6, "Rules"); txt(s, "Rules that shape the design [to verify]", { x: M + 6.5, y: 1.8, w: 5.3, h: 0.4, fontSize: 20, bold: true, color: C.accent3 });
txt(s, ["ISO 24330 for rendezvous and servicing practice", "ISO 24113 and IADC for debris and end of life", "ECSS series for GNC, verification and interfaces", "NASA-STD-7009 for model credibility", "ITU and national licensing for the beacon", "Owner consent and national authorisation; EU Space Act evolving"].map((t, k, a) => ({ text: t, options: { bullet: true, breakLine: k < a.length - 1, paraSpaceAfter: 8 } })), { x: M + 6.5, y: 2.4, w: 5.3, h: 3.5, fontSize: 17 });
s.addNotes("Competitor and standards lists are from background knowledge and must be sourced before submission. A patent search is still open.");

// 10 plan and budget
pres.addSection({ title: "Implementation" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Implementation" }); T(s, "Next: a ground demonstration with agreed criteria");
const road = [["Study", "now", "Envelopes, beacon and IOS concept, tier trade"], ["Ground demo", "next", "Bench B1 to B7, contact model, HIL rig"], ["IOD", "later", "Prepared client and servicer in orbit"], ["Product family", "after", "Tiers 1 to 4 as catalogue items"]];
road.forEach(([n, when, d], i) => { const x = M + i * 3.07; box(s, x, 1.6, 2.9, 2.5, "Stage " + n, i === 1 ? C.accent6 : C.text2); txt(s, when, { x: x + 0.25, y: 1.8, w: 2.4, h: 0.3, fontSize: 14, color: C.background2 }); txt(s, n, { x: x + 0.25, y: 2.15, w: 2.4, h: 0.5, fontSize: 22, bold: true, color: C.accent1 }); txt(s, d, { x: x + 0.25, y: 2.8, w: 2.4, h: 1.2, fontSize: 15 }); });
stat(s, M, 4.45, 3.6, "EUR 770 k", "draft ground-demo budget (assumed)", C.accent2); stat(s, M + 3.9, 4.45, 3.0, "40", "person-months at EUR 8 k assumed", C.accent1);
txt(s, "Use of funds: about 42% people, 45% bench and rig hardware, 13% contingency. Six work packages: systems, RPO and GNC, HPC and analysis, beacon bench, IOS and OSAN, business and regulatory.", { x: M + 7.2, y: 4.5, w: 4.9, h: 1.8, fontSize: 15, color: C.background2 });
s.addNotes("3:50. Next is a ground demonstration: bench-test the beacon, validate a contact model, run the HIL rig. A draft budget is about 770 thousand euros, assumptions we want ClearSpace to challenge. Budget table: docs/PRESENTATION_PACK.md section 5.2.");

// 11 asks and risks
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Implementation" }); T(s, "Three asks and the risks we are watching");
box(s, M, 1.6, 5.9, 4.4, "Asks"); txt(s, "What we need", { x: M + 0.3, y: 1.8, w: 5.3, h: 0.4, fontSize: 22, bold: true, color: C.accent3 });
txt(s, ["Confirm the reference client and the degraded failure cases", "Point us to failure statistics so we can test how often rescue is needed", "Agree the success criteria for the ground demo"].map((t, k, a) => ({ text: t, options: { bullet: { type: "number" }, breakLine: k < a.length - 1, paraSpaceAfter: 12 } })), { x: M + 0.3, y: 2.5, w: 5.3, h: 3.8, fontSize: 20 });
box(s, M + 6.2, 1.6, 5.93, 4.4, "Risks"); txt(s, "Risks", { x: M + 6.5, y: 1.8, w: 5.3, h: 0.4, fontSize: 22, bold: true, color: C.accent4 });
txt(s, ["Value rests on an assumed failure rate and price", "Buyers may prefer servicer-side fixes", "Contact-model fidelity and hardware lead time", "Standards fragmentation and licensing timing", "Novelty not yet checked against patents"].map((t, k, a) => ({ text: t, options: { bullet: true, breakLine: k < a.length - 1, paraSpaceAfter: 10 } })), { x: M + 6.5, y: 2.5, w: 5.3, h: 3.4, fontSize: 19 });
s.addNotes("4:30. Three asks: confirm the reference client and failure cases, point us to failure statistics, agree the ground-demo success criteria.");

// 12 close
s = pres.addSlide({ masterName: "DIVIDER", sectionTitle: "Implementation" }); T(s, "Minimum preparation. Safe when degraded. A scalable roadmap.");
s.addNotes("4:50. Minimum preparation. Safe when degraded. A scalable roadmap.");

// appendix
pres.addSection({ title: "Appendix" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Appendix" }); T(s, "Appendix: what is evidence and what is assumed");
s.addTable([[hd("Item"), hd("Status"), hd("Source")],
  [cell("Pass rates, paired effects, aborts"), cell("Model result", { color: "7DFFB2" }), cell("results/v4_1_validation, results/v4_0")],
  [cell("Beacon power, mass, link margin"), cell("Engineering model, assumed derating", { color: "FFB454" }), cell("rpo_project/ios.py, docs/BEACON_BENCH_PLAN.md")],
  [cell("Prices, revenue, probabilities, budget"), cell("Assumed", { color: "FF8F8F" }), cell("docs/ECONOMICS_MODEL.md, docs/PRESENTATION_PACK.md")],
  [cell("Competitors and standards"), cell("From background knowledge, unsourced", { color: "FF8F8F" }), cell("docs/EXPERT_CHECKPOINT_SESSION1.md")],
  [cell("Fuel gauge, downlink, platform demo data"), cell("Simulated", { color: "FFB454" }), cell("tools/export_fuel_demo.py, export_downlink_demo.py")]],
  { x: M, y: 1.6, w: W - 2 * M, colW: [4.2, 3.9, 4.03], border: { type: "solid", color: "243651", pt: 1 }, rowH: 0.55 });
txt(s, "TRL statement: simulation and concept today (our judgement, about TRL 2 to 3); proposed target for the ground demo about TRL 4 to 5. Not an assessed rating.", { x: M, y: 5.2, w: W - 2 * M, h: 0.8, fontSize: 15, color: C.background2 });

(async () => { const out = path.join(__dirname, "Orbit_Observers_Pitch.pptx"); await pres.writeFile({ fileName: out }); await applyTheme(out, THEME); console.log("wrote", out); })();
