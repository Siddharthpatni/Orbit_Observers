// Orbit Observers pitch deck: customer perspective, money first. Numbers come from numbers.json (tools/deck_numbers.py).
// Run: python ../../tools/deck_numbers.py && NODE_PATH=$PWD/node_modules node build_deck.js
const fs = require("fs"), path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/Users/siddharthpatni/.claude/skills/synced/48c620f4-3846-49cd-9f55-2b2587cf21b2_42dc88de-7dc0-4e87-a578-f458db598652/pptx/scripts/apply_theme.js");
const ROOT = path.resolve(__dirname, "../..");
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "numbers.json"), "utf8"));
const m1 = x => (Math.abs(x) >= 10 ? x.toFixed(0) : x.toFixed(1)), m2 = x => x.toFixed(2);

const THEME = { name: "Orbital Notation", headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: "05070C", lt1: "DFE8F5", dk2: "0B1220", lt2: "8FA6C8", accent1: "5AD1FF", accent2: "FFB454", accent3: "7DFFB2", accent4: "FF8F8F", accent5: "7AA2FF", accent6: "243651", hlink: "5AD1FF", folHlink: "8FA6C8" } };
const pres = new pptxgen(); pres.layout = "LAYOUT_WIDE"; pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Orbit Observers pitch"; pres.author = "Orbit Observers"; pres.company = "Orbit Observers";
const C = pres.SchemeColor, W = 13.33, H = 7.5, M = 0.6;

pres.defineSlideMaster({ title: "TITLE_ONLY", background: { color: C.text1 }, slideNumber: { x: W - 1.1, y: H - 0.45, w: 0.6, h: 0.3, fontSize: 10, color: C.background2, align: "right" },
  objects: [
    { text: { text: "Orbit Observers  |  model-based study. Money figures use assumed inputs, not customer data", options: { x: M, y: H - 0.45, w: 10, h: 0.3, fontSize: 10, color: C.background2, margin: 0 } } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.4, w: W - 2 * M, h: 0.9, fontSize: 32, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } }] });
pres.defineSlideMaster({ title: "DIVIDER", background: { color: C.text1 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: M, y: 2.6, w: W - 2 * M, h: 1.6, fontSize: 54, bold: true, color: C.background1, margin: 0, align: "left" }, text: "" } }] });

const T = (s, text) => s.addText(text, { placeholder: "title" });
const box = (s, x, y, w, h, name, fill = C.text2) => s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: C.accent6, width: 1 }, objectName: name });
const txt = (s, text, o) => s.addText(text, Object.assign({ isTextBox: true, margin: 0, color: C.background1, fontSize: 16, valign: "top" }, o));
const bullets = (arr, o = {}) => arr.map((t, k) => ({ text: t, options: Object.assign({ bullet: true, breakLine: k < arr.length - 1, paraSpaceAfter: 8 }, o) }));
const stat = (s, x, y, w, num, label, color, size = 44) => { txt(s, num, { x, y, w, h: 0.85, fontSize: size, bold: true, color }); txt(s, label, { x, y: y + 0.9, w, h: 0.8, fontSize: 14, color: C.background2 }); };
const chartBase = { catAxisLabelColor: "8FA6C8", valAxisLabelColor: "8FA6C8", catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 12, valAxisLabelFontSize: 12,
  valGridLine: { color: "243651", size: 0.75 }, catGridLine: { style: "none" }, titleColor: "DFE8F5", titleFontFace: "+mn-lt", titleFontSize: 14, showTitle: true,
  legendColor: "DFE8F5", legendFontFace: "+mn-lt", legendFontSize: 12, dataLabelColor: "DFE8F5", dataLabelFontFace: "+mn-lt", dataLabelFontSize: 12 };

// campaign data for the pass-rate chart
const rows = fs.readFileSync(path.join(ROOT, "results/v4_1_validation/summary_main.csv"), "utf8").trim().split("\n"); const hdr = rows[0].split(",");
const get = (tier, t) => { const r = rows.slice(1).map(l => l.split(",")).find(c => c[0] === tier && +c[1] === t); return +r[hdr.indexOf("p_terminal_pass")] * 100; };
const tumbles = [0, 0.25, 0.5, 1, 2, 3, 5];
const passSeries = [["C0 unprepared", "C0_unprepared"], ["C1 markers", "C1_fiducials"], ["C2 marker + rate beacon", "C2_beacon"], ["C3 IOS mode", "C3_ios_mode"]].map(([name, k]) => ({ name, labels: tumbles.map(String), values: tumbles.map(t => get(k, t)) }));

let s;
// ---------- 1 title ----------
pres.addSection({ title: "Open" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Open" }); T(s, "Orbit Observers");
txt(s, "Turn a stranded satellite into a recoverable asset", { x: M, y: 1.5, w: 5.6, h: 1.3, fontSize: 26, color: C.accent1 });
txt(s, "A small, priced preparation added at build time, so a future servicer can reach your satellite even after it fails.", { x: M, y: 3.1, w: 5.4, h: 1.5, fontSize: 18 });
txt(s, "For satellite operators, servicers, insurers and regulators", { x: M, y: 5.0, w: 5.6, h: 0.7, fontSize: 16, color: C.accent2 });
s.addMedia({ type: "video", path: path.join(ROOT, "media/orbit_observers_intro.mp4"), x: 6.7, y: 1.5, w: 6.0, h: 3.375, objectName: "Intro video" });
s.addNotes("0:00. We are Orbit Observers. We turn a stranded satellite into a recoverable asset. We are going to talk about money first: what a failure costs, what preparation costs, and when it pays. (The 10 second video plays here.)");

// ---------- 2 the money problem ----------
pres.addSection({ title: "The money" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "The money" }); T(s, `A stranded satellite is a EUR ${m1(N.rescue.gross_value_m)} M question`);
s.addChart(pres.charts.BAR, [{ name: "EUR M", labels: ["Value of 5 more years", "Servicing price", "Net to the owner"], values: [N.rescue.gross_value_m, N.rescue.price_m, N.rescue.net_m] }],
  Object.assign({}, chartBase, { x: M, y: 1.45, w: 7.0, h: 4.9, barDir: "col", chartColors: ["7DFFB2", "FF8F8F", "5AD1FF"], showLegend: false, title: "A rescued GEO satellite, EUR M (undiscounted, assumed inputs)", showValue: true, dataLabelPosition: "outEnd", valAxisMaxVal: 140, valAxisMinVal: 0, barGapWidthPct: 60 }));
txt(s, "Why satellites get stranded", { x: 8.0, y: 1.5, w: 4.7, h: 0.4, fontSize: 20, bold: true, color: C.accent1 });
txt(s, bullets(["Most legacy satellites were never designed to be grabbed", "A tumbling client makes the last 12 metres risky for the servicer", "All-electric platforms remove the accidental features servicers used"]), { x: 8.0, y: 2.05, w: 4.7, h: 2.3, fontSize: 17 });
box(s, 8.0, 4.5, 4.73, 1.85, "Assumption box"); txt(s, "Assumed: EUR 40 M a year revenue, 60% margin, 5 extra years, EUR 75 M servicing price. A rescue only pays if the servicer can reach the satellite.", { x: 8.25, y: 4.7, w: 4.25, h: 1.5, fontSize: 15, color: C.background2 });
s.addNotes("0:15. A GEO satellite that fails in year ten strands about five years of profit: 120 million euros on our assumptions. A rescue costs 75 million, so the owner keeps 45 million, but only if the servicer can actually reach the satellite. Every money figure in this deck is an assumed input; the outcomes come from our simulator.");

// ---------- 3 three customers ----------
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "The money" }); T(s, "Three customers, three money questions");
const cust = [["Satellite operator or maker", "Will the kit pay for itself?", `${N.incremental_vs_c0_at3.C1_fiducials.roi_x.toFixed(1)}x`, `return on markers: EUR 45 k per satellite buys EUR ${m2(N.incremental_vs_c0_at3.C1_fiducials.extra_benefit_m)} M expected benefit`, C.accent2],
  ["Servicer provider", "Can I serve more clients per vehicle?", "-37%", `break-even price per successful visit, EUR ${m1(N.at3.C0_unprepared.breakeven_price_m)} M to EUR ${m1(N.at3.C1_fiducials.breakeven_price_m)} M`, C.accent1],
  ["Insurer, regulator, agency", "Can I trust the risk number?", "0 / 6,140", "keep-out violations in the model; every run is replayable from a stored seed", C.accent3]];
cust.forEach(([who, q, num, ans, col], i) => { const x = M + i * 4.1; box(s, x, 1.55, 3.9, 4.95, "Customer " + who);
  txt(s, who, { x: x + 0.3, y: 1.8, w: 3.3, h: 0.6, fontSize: 21, bold: true, color: col }); txt(s, q, { x: x + 0.3, y: 2.55, w: 3.3, h: 0.8, fontSize: 17, color: C.background2 });
  txt(s, num, { x: x + 0.3, y: 3.5, w: 3.3, h: 0.9, fontSize: 44, bold: true, color: col }); txt(s, ans, { x: x + 0.3, y: 4.5, w: 3.3, h: 1.8, fontSize: 15 }); });
s.addNotes("0:40. Three customers. The operator or satellite maker asks whether the kit pays for itself. The servicer asks whether it can serve more clients per vehicle. Insurers and regulators ask whether they can trust the risk number. We answer each with a number, and we will show where each number comes from.");

// ---------- 4 the offer ----------
pres.addSection({ title: "The offer" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "The offer" }); T(s, "What the customer buys: four tiers, priced per satellite");
const tierInfo = [["1", "EOL-ready", "Capture fixture + markers", "Removal at end of life"], ["2", "Service-ready", "+ IOS mode + beacon", "Servicing of a degraded client"], ["3", "Life-extension-ready", "+ refuelling port", "Refuel and release"], ["4", "Augmentation-ready", "+ power, data and POD port", "Upgrade or propulsion POD"]];
tierInfo.forEach(([n, name, prov, opt], i) => { const x = M + i * 3.07, c = N.product_tiers[n]; box(s, x, 1.55, 2.9, 4.0, "Tier " + n);
  txt(s, "Tier " + n, { x: x + 0.25, y: 1.75, w: 2.4, h: 0.3, fontSize: 14, color: C.background2 }); txt(s, name, { x: x + 0.25, y: 2.1, w: 2.4, h: 0.8, fontSize: 20, bold: true, color: C.accent1 });
  txt(s, prov, { x: x + 0.25, y: 2.95, w: 2.4, h: 0.7, fontSize: 15 }); txt(s, `EUR ${m2(c.total_eur)} M`, { x: x + 0.25, y: 3.75, w: 2.4, h: 0.5, fontSize: 24, bold: true, color: C.accent2 });
  txt(s, `${c.mass_kg.toFixed(1)} kg  |  ${opt}`, { x: x + 0.25, y: 4.4, w: 2.4, h: 0.9, fontSize: 14, color: C.background2 }); });
txt(s, "Price per satellite includes unit cost, launch of the added mass and a share of development. All costs are assumptions. Most buyers start at Tier 1 or 2; Tiers 3 and 4 have a cost model but no benefit model yet.", { x: M, y: 5.8, w: W - 2 * M, h: 0.9, fontSize: 15, color: C.background2 });
s.addNotes("1:05. This is what the customer buys. Four tiers from end-of-life capture to an augmentation-ready service zone. Prices per satellite are assumed: 0.36 million for tier one up to 6.7 million for tier four. Most buyers would start at tier one or two.");

// ---------- 5 return on spend ----------
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "The offer" }); T(s, "Return on spend: markers first, the rest for the right risk");
const inc = N.incremental_vs_c0_at3;
s.addChart(pres.charts.BAR, [{ name: "Extra cost per satellite", labels: ["Markers (C1)", "+ rate beacon (C2)", "+ IOS mode (C3)"], values: [inc.C1_fiducials.extra_cost_m, inc.C2_beacon.extra_cost_m, inc.C3_ios_mode.extra_cost_m] },
  { name: "Extra expected benefit", labels: ["Markers (C1)", "+ rate beacon (C2)", "+ IOS mode (C3)"], values: [inc.C1_fiducials.extra_benefit_m, inc.C2_beacon.extra_benefit_m, inc.C3_ios_mode.extra_benefit_m] }],
  Object.assign({}, chartBase, { x: M, y: 1.45, w: 7.4, h: 5.0, barDir: "col", barGrouping: "clustered", chartColors: ["FF8F8F", "7DFFB2"], showLegend: true, legendPos: "b", title: "vs no preparation, at 3 deg/s tumble, EUR M (assumed inputs)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 1.5, barGapWidthPct: 50 }));
stat(s, 8.4, 1.55, 4.4, `${inc.C1_fiducials.roi_x.toFixed(1)}x`, "return on markers: EUR 0.045 M buys EUR 0.74 M expected benefit", C.accent3);
stat(s, 8.4, 3.35, 4.4, `EUR ${m1(N.fleet10.c1_extra_benefit_m)} M`, `expected benefit on a 10-satellite fleet for EUR ${m2(N.fleet10.c1_extra_cost_m)} M of markers`, C.accent2);
txt(s, "The beacon and IOS mode add little at 3 deg/s on approach alone. They pay where tumble can exceed the passive limit, or where identity, health and handover data matter.", { x: 8.4, y: 5.2, w: 4.4, h: 1.3, fontSize: 15, color: C.background2 });
s.addNotes("1:30. Return on spend. At three degrees per second, markers return about 16 times their cost in expected benefit on our assumptions. On a ten-satellite fleet that is about 7 million euros of expected benefit for under half a million of markers. The beacon and IOS mode add little on approach alone at this tumble rate; they pay where tumble can exceed the passive limit or where identity, health and handover data matter.");

// ---------- 6 when does it pay ----------
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "The offer" }); T(s, "When it pays depends on how often rescue is needed");
const sp = N.sens_p;
s.addChart(pres.charts.LINE, [{ name: "Markers vs none, 3 deg/s", labels: sp.p.map(p => (p * 100) + "%"), values: sp.c1_vs_c0_net_m }, { name: "IOS mode vs none, 5 deg/s", labels: sp.p.map(p => (p * 100) + "%"), values: sp.c3_vs_c0_at5_net_m }],
  Object.assign({}, chartBase, { x: M, y: 1.45, w: 7.4, h: 5.0, chartColors: ["FFB454", "5AD1FF"], lineSize: 3, lineDataSymbolSize: 8, showLegend: true, legendPos: "b", title: "Net value per satellite, EUR M, by chance a client ever needs rescue", showValue: false, valAxisMinVal: -1, valAxisMaxVal: 3.5 }));
stat(s, 8.4, 1.55, 4.4, "0.6%", "chance of ever needing rescue at which markers break even", C.accent2);
stat(s, 8.4, 3.35, 4.4, "5.3%", "chance at which IOS mode breaks even where tumble reaches 5 deg/s", C.accent1);
box(s, 8.4, 5.2, 4.33, 1.3, "Test first"); txt(s, "The number to test first with operators: how often a client degrades enough to need rescue.", { x: 8.6, y: 5.35, w: 3.95, h: 1.05, fontSize: 15 });
s.addNotes("2:00. Whether it pays depends on one number: how often a satellite fails badly enough to need rescue. Markers break even at 0.6 percent. IOS mode breaks even at 5.3 percent where tumble reaches five degrees per second. We do not know that failure rate, so it is the first thing we want to test with operators.");

// ---------- 7 why it works (serviceability) ----------
pres.addSection({ title: "Serviceability" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Serviceability" }); T(s, "Why it works: fewer failed rescues where it matters");
s.addChart(pres.charts.LINE, passSeries, Object.assign({}, chartBase, { x: M, y: 1.45, w: 7.4, h: 5.0, chartColors: ["FF8F8F", "FFB454", "7DFFB2", "5AD1FF"], lineSize: 3, lineDataSymbolSize: 7, showLegend: true, legendPos: "b", title: "Terminal window met, % of 100 paired seeds, by tumble rate (deg/s)", valAxisMinVal: 0, valAxisMaxVal: 100 }));
const a3 = N.at3;
stat(s, 8.4, 1.55, 4.4, `${(a3.C0_unprepared.p_success * 100).toFixed(0)}% to ${(a3.C1_fiducials.p_success * 100).toFixed(0)}%`, "rescue success within three attempts, unprepared to markers (3 deg/s)", C.accent3);
stat(s, 8.4, 3.35, 4.4, `${(a3.C0_unprepared.p_lost * 100).toFixed(0)}% to ${(a3.C1_fiducials.p_lost * 100).toFixed(0)}%`, "missions lost to an unsafe retreat or violation", C.accent4);
txt(s, "Three client states are covered: nominal (IOS mode), degraded (independent beacon), tumbling (markers and capture point). A radio that only sends identity changes nothing; rate data adds 8 points.", { x: 8.4, y: 5.2, w: 4.4, h: 1.3, fontSize: 15, color: C.background2 });
s.addNotes("2:25. Why the money works. At three degrees per second an unprepared client is reached within three attempts 64 percent of the time and the mission is lost 30 percent of the time. With markers those become 98 and 2 percent. Three client states are covered: nominal, degraded and tumbling. A radio that only sends identity changes nothing; rate data adds 8 points.");

// ---------- 8 servicers earn more ----------
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Serviceability" }); T(s, "Servicers need less per success, so everyone's price can fall");
const tn = ["C0_unprepared", "C1_fiducials", "C2_beacon", "C3_ios_mode"];
s.addChart(pres.charts.BAR, [{ name: "EUR M", labels: ["Unprepared", "Markers", "+ rate beacon", "+ IOS mode"], values: tn.map(t => N.at3[t].breakeven_price_m) }],
  Object.assign({}, chartBase, { x: M, y: 1.45, w: 7.4, h: 5.0, barDir: "col", chartColors: ["FF8F8F", "FFB454", "7DFFB2", "5AD1FF"], showLegend: false, title: "Servicer break-even price per successful visit, EUR M (3 deg/s)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 40, barGapWidthPct: 60 }));
stat(s, 8.4, 1.55, 4.4, `${a3.C0_unprepared.successes.toFixed(1)} to ${a3.C1_fiducials.successes.toFixed(1)}`, "expected successful rescues per servicer lifetime, unprepared to markers", C.accent3);
stat(s, 8.4, 3.35, 4.4, `${a3.C1_fiducials.visits} visits`, "per vehicle, limited by propellant. Fewer retries leave more fuel for more clients", C.accent1);
txt(s, `Assumes a EUR 250 M vehicle, EUR 15 M a year to run, 12 years, 60 m/s per transfer. Break-even price is cost divided by expected successes.`, { x: 8.4, y: 5.2, w: 4.4, h: 1.3, fontSize: 15, color: C.background2 });
s.addNotes("2:50. For the servicer, a prepared client means fewer retries, so the same vehicle completes about 21 rescues instead of 13. Its break-even price per success falls from 32 to 20 million euros. That lets the whole market price lower, which is what makes the owner's decision easier.");

// ---------- 8b what is new ----------
pres.addSection({ title: "Trust" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Trust" }); T(s, "What is new here, and what we build on");
box(s, M, 1.5, 6.4, 5.0, "New"); txt(s, "New (not found in our literature search)", { x: M + 0.3, y: 1.7, w: 5.8, h: 0.45, fontSize: 20, bold: true, color: C.accent3 });
txt(s, bullets(["A controlled, paired measurement of client preparation on closed-loop outcomes: markers +51 pp, rate data +8 pp, identity-only radio +0", "A degraded-state information and handover layer: independent beacon plus an IOS mode with one controlling authority", "A money chain from simulated outcomes to euros per client, per tier"], { paraSpaceAfter: 10 }), { x: M + 0.3, y: 2.3, w: 5.8, h: 3.4, fontSize: 16 });
txt(s, "Needs a full literature review and patent search to confirm", { x: M + 0.3, y: 5.8, w: 5.8, h: 0.5, fontSize: 14, color: C.accent2 });
box(s, M + 6.7, 1.5, 5.43, 5.0, "Builds on"); txt(s, "Builds on known work", { x: M + 7.0, y: 1.7, w: 4.9, h: 0.45, fontSize: 20, bold: true, color: C.accent1 });
txt(s, bullets(["Servicer guidance for tumbling targets (Naasz 2011, Madonna 2025)", "Marker-based pose estimation (Opromolla 2022, ESA)", "Interfaces and standards: MICE, MASI, CONFERS, AIAA S-157 and S-159", "Expected-value servicing economics (Sullivan 2005)", "PVT and book-keeping gauging"], { paraSpaceAfter: 8 }), { x: M + 7.0, y: 2.3, w: 4.9, h: 4.1, fontSize: 15 });
s.addNotes("Prior work makes the servicer smarter and standardises the physical interfaces. We ask what the client must carry to stay serviceable when degraded, and what that is worth. Our searches found no controlled paired measurement of client preparation, and no dedicated servicing beacon with control handover; but we only read abstracts, so this needs a full review and a patent search. Detail: docs/RESEARCH_AND_NOVELTY.md.");

// ---------- 9 trust (technical) ----------

s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Trust" }); T(s, "Can you rely on the numbers? Built, tested, and bounded");
stat(s, M, 1.55, 2.8, "74", "automated tests pass", C.accent3); stat(s, M + 3.0, 1.55, 2.8, "41,240", "simulated approaches (35,100 + 6,140)", C.accent1); stat(s, M + 6.0, 1.55, 2.8, "0 / 6,140", "keep-out violations (a count, not a bound)", C.accent2); stat(s, M + 9.0, 1.55, 3.1, "1.2 kg", "fuel gauge error from 800 kg", C.accent3);
box(s, M, 3.55, 5.9, 3.0, "Verified"); txt(s, "What you can rely on", { x: M + 0.3, y: 3.75, w: 5.3, h: 0.4, fontSize: 20, bold: true, color: C.accent3 });
txt(s, bullets(["Paired seeds, intervals, exact tests, every run replayable", "Human approval gates the close approach; abort from any state", "Beacon bench plan with pass limits; fuel and log gauges that flag faults", "Dashboard, downlink and audit trail already demonstrated"], { paraSpaceAfter: 6 }), { x: M + 0.3, y: 4.25, w: 5.3, h: 2.2, fontSize: 15 });
box(s, M + 6.2, 3.55, 5.93, 3.0, "Limits"); txt(s, "What we do not claim", { x: M + 6.5, y: 3.75, w: 5.3, h: 0.4, fontSize: 20, bold: true, color: C.accent4 });
txt(s, bullets(["No contact model: 'window met' is not a grab", "Retreat safety in orbit not established", "No hardware data; all costs and noise are assumptions", "Authentication is a simulation token today"], { paraSpaceAfter: 6 }), { x: M + 6.5, y: 4.25, w: 5.3, h: 2.2, fontSize: 15 });
s.addNotes("3:15. Can you rely on the numbers? 74 tests, 41 thousand simulated approaches, zero keep-out violations in the latest campaign, replayable from stored seeds. And what we do not claim: no contact model, no hardware data, and every cost is an assumption.");

// ---------- 10 business model and competition ----------
pres.addSection({ title: "Business" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Business" }); T(s, "How we earn, who else is here, and what rules apply");
const streams = [["Kit per satellite", "Operators and makers pay per unit at build time, or license the interface set", C.accent2], ["Servicer partnerships", "Share of savings from fewer retries; qualified-client lists", C.accent1], ["Evidence service", "Serviceability envelopes for insurers, regulators and agencies", C.accent3]];
streams.forEach(([h, d, col], i) => { const x = M + i * 4.1; box(s, x, 1.5, 3.9, 2.3, "Stream " + h); txt(s, h, { x: x + 0.25, y: 1.7, w: 3.4, h: 0.45, fontSize: 21, bold: true, color: col }); txt(s, d, { x: x + 0.25, y: 2.3, w: 3.4, h: 1.4, fontSize: 16 }); });
box(s, M, 4.0, 5.9, 2.55, "Competition"); txt(s, "Others fix the servicer [to verify]", { x: M + 0.3, y: 4.15, w: 5.3, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
txt(s, bullets(["Northrop Grumman MEV and MRV, Astroscale, Starfish Space, ClearSpace", "Orbit Fab, MDA, Airbus, Thales Alenia, OHB: ports, arms, interfaces", "Our difference: the client's minimum preparation for the degraded state"], { paraSpaceAfter: 5 }), { x: M + 0.3, y: 4.65, w: 5.3, h: 1.8, fontSize: 15 });
box(s, M + 6.2, 4.0, 5.93, 2.55, "Rules"); txt(s, "Rules that shape the design [to verify]", { x: M + 6.5, y: 4.15, w: 5.3, h: 0.4, fontSize: 18, bold: true, color: C.accent3 });
txt(s, bullets(["ISO 24330, ISO 24113, ECSS series, NASA-STD-7009", "Owner consent and national authorisation for proximity operations", "Authenticated commands; ITU and national licensing for the beacon"], { paraSpaceAfter: 5 }), { x: M + 6.5, y: 4.65, w: 5.3, h: 1.8, fontSize: 15 });
s.addNotes("3:40. How we earn: a per-satellite kit at build time, partnerships with servicers that share the savings from fewer retries, and an evidence service for insurers and regulators. Competitors mostly fix the servicer; we specify the client. Competitor and standards lists still need sourcing, and a patent search is open.");

// ---------- 11 plan, funds, asks ----------
pres.addSection({ title: "Plan" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Plan" }); T(s, "Each stage proves one money assumption; here is what we ask");
const road = [["Study", "now", "Success rates and costs per tier on a model"], ["Ground demo", "next", "Beacon bench, contact model, HIL rig: proves the technical numbers"], ["In-orbit demo", "later", "Prepared client and servicer: proves savings per visit"], ["Product family", "after", "Tiers sold: proves the price customers accept"]];
road.forEach(([n, when, d], i) => { const x = M + i * 3.07; box(s, x, 1.5, 2.9, 2.35, "Stage " + n, i === 1 ? C.accent6 : C.text2); txt(s, when, { x: x + 0.25, y: 1.65, w: 2.4, h: 0.3, fontSize: 14, color: C.background2 }); txt(s, n, { x: x + 0.25, y: 2.0, w: 2.4, h: 0.45, fontSize: 21, bold: true, color: C.accent1 }); txt(s, d, { x: x + 0.25, y: 2.55, w: 2.4, h: 1.2, fontSize: 14 }); });
stat(s, M, 4.15, 3.2, "EUR 770 k", "draft ground-demo budget (assumed): 42% people, 45% hardware, 13% contingency", C.accent2, 40);
box(s, M + 3.7, 4.15, 8.43, 2.4, "Asks"); txt(s, "What we need from you", { x: M + 4.0, y: 4.3, w: 7.8, h: 0.4, fontSize: 20, bold: true, color: C.accent3 });
txt(s, bullets(["Failure statistics, so we can replace our assumed rescue rate", "A reference client and failure cases to test against", "Agreed success criteria for the ground demo"], { bullet: { type: "number" }, paraSpaceAfter: 6 }), { x: M + 4.0, y: 4.85, w: 7.8, h: 1.6, fontSize: 17 });
s.addNotes("4:15. Each stage proves one money assumption. The ground demonstration proves the technical numbers with a beacon bench and a contact model; the in-orbit demonstration proves the savings per visit; selling tiers proves the price customers accept. A draft ground-demo budget is about 770 thousand euros, all assumed. We need three things: failure statistics, a reference client, and agreed success criteria.");

// ---------- 12 close ----------
s = pres.addSlide({ masterName: "DIVIDER", sectionTitle: "Plan" }); T(s, "A small preparation now. A recoverable asset later.");
s.addNotes("4:50. A small preparation now, a recoverable asset later.");

// ---------- backup ----------
pres.addSection({ title: "Backup" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Backup" }); T(s, "Backup: reference architecture and what we cover");
s.addImage({ path: path.join(ROOT, "docs/reference/Reference_System_Architecture.jpg"), x: M, y: 1.4, w: 7.7, h: 5.13, objectName: "Reference architecture", altText: "Reference system architecture: client satellite, OSAN service interface, servicing spacecraft, ground segment" });
box(s, 8.6, 1.4, 4.13, 1.62, "Covered"); txt(s, "Covered", { x: 8.8, y: 1.5, w: 3.7, h: 0.35, fontSize: 18, bold: true, color: C.accent3 });
txt(s, "Navigation aids, servicer GNC and abort logic, ground platform and approvals", { x: 8.8, y: 1.9, w: 3.75, h: 1.05, fontSize: 14 });
box(s, 8.6, 3.12, 4.13, 1.9, "Partial"); txt(s, "Partial", { x: 8.8, y: 3.22, w: 3.7, h: 0.35, fontSize: 18, bold: true, color: C.accent2 });
txt(s, "Service Beacon (no interface or health fields yet), IOS mode, health monitoring (fuel and logs only), capture geometry without loads", { x: 8.8, y: 3.62, w: 3.75, h: 1.35, fontSize: 14 });
box(s, 8.6, 5.12, 4.13, 1.44, "Next"); txt(s, "Not modelled", { x: 8.8, y: 5.22, w: 3.7, h: 0.35, fontSize: 18, bold: true, color: C.accent4 });
txt(s, "Utility and fluid transfer, upgrade port, robotic servicing, power and thermal lines", { x: 8.8, y: 5.62, w: 3.75, h: 0.9, fontSize: 14 });
s.addNotes("Reference diagram from the team. Covered: navigation aids, servicer GNC and abort logic, ground platform. Partial: beacon, IOS, health monitoring. Not modelled: utility and fluid transfer, upgrade port, robotic servicing. Full table: docs/PRESENTATION_PACK.md section 10.");

const hd = t => ({ text: t, options: { bold: true, color: "5AD1FF", fill: { color: "0B1220" }, fontSize: 14 } });
const cell = (t, o = {}) => ({ text: t, options: Object.assign({ color: "DFE8F5", fill: { color: "05070C" }, fontSize: 14 }, o) });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Backup" }); T(s, "Backup: every money input, and what drives the answer");
s.addTable([[hd("Input"), hd("Value used"), hd("Effect")],
  [cell("Client revenue and margin"), cell(`EUR ${N.assumptions.revenue_m} M a year, ${N.assumptions.margin * 100}%`), cell("Sets the value of a rescue")],
  [cell("Extension and timing"), cell(`${N.assumptions.years} years at year ${N.assumptions.service_year}, ${N.assumptions.discount * 100}% discount`), cell("Discounted rescue value EUR " + m1(N.rescue.net_discounted_m) + " M")],
  [cell("Servicing price"), cell(`EUR ${N.assumptions.price_m} M`), cell("Net to owner EUR " + m1(N.rescue.net_m) + " M undiscounted")],
  [cell("Chance a client needs rescue"), cell(`${N.assumptions.p_need * 100}%`), cell("Dominates every break-even; test first", { color: "FFB454" })],
  [cell("Attempts allowed"), cell(`${N.assumptions.attempts}`), cell("Retry only after a complete retreat")],
  [cell("Kit costs and servicer vehicle"), cell("see ECONOMICS_MODEL.md"), cell("Tier prices and break-even price")]],
  { x: M, y: 1.6, w: W - 2 * M, colW: [3.8, 4.3, 4.03], border: { type: "solid", color: "243651", pt: 1 }, rowH: 0.55 });
txt(s, "Outcomes (pass, abort, retry, fuel) come from the simulator; every euro figure comes from these inputs. Replace them with operator and ClearSpace data before any external claim.", { x: M, y: 5.8, w: W - 2 * M, h: 0.8, fontSize: 15, color: C.background2 });

s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Backup" }); T(s, "Backup: what is evidence and what is assumed");
s.addTable([[hd("Item"), hd("Status"), hd("Source")],
  [cell("Pass rates, paired effects, aborts"), cell("Model result", { color: "7DFFB2" }), cell("results/v4_1_validation, results/v4_0")],
  [cell("Beacon power, mass, link margin"), cell("Engineering model, assumed derating", { color: "FFB454" }), cell("docs/BEACON_BENCH_PLAN.md")],
  [cell("Prices, revenue, probabilities, budget"), cell("Assumed", { color: "FF8F8F" }), cell("docs/ECONOMICS_MODEL.md, PRESENTATION_PACK.md")],
  [cell("Competitors and standards"), cell("Background knowledge, unsourced", { color: "FF8F8F" }), cell("docs/EXPERT_CHECKPOINT_SESSION1.md")],
  [cell("Fuel gauge, downlink, dashboard data"), cell("Simulated", { color: "FFB454" }), cell("tools/export_fuel_demo.py, export_downlink_demo.py")]],
  { x: M, y: 1.6, w: W - 2 * M, colW: [4.2, 3.9, 4.03], border: { type: "solid", color: "243651", pt: 1 }, rowH: 0.55 });
txt(s, "Maturity: simulation and concept today (our judgement, about TRL 2 to 3); proposed target for the ground demo about TRL 4 to 5. Not an assessed rating.", { x: M, y: 5.2, w: W - 2 * M, h: 0.8, fontSize: 15, color: C.background2 });

(async () => { const out = path.join(__dirname, "Orbit_Observers_Pitch.pptx"); await pres.writeFile({ fileName: out }); await applyTheme(out, THEME); console.log("wrote", out); })();
