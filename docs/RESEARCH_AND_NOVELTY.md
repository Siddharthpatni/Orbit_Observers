# Research check: what is unique in our system

**How this was done.** Eleven web searches (19 Oct 2026) on the main parts of the system, reading search-result abstracts and snippets, **not full papers**. So the statements below are "not found in what I searched", not "does not exist". The novelty claims need a proper literature review and a patent search (Espacenet, IPIL) before they go in a proposal. Sources are listed at the end.

## 1. What the literature already does

| Area | What the papers do | Source |
|:--|:--|:--|
| GEO approach to a non-cooperative, possibly tumbling client | Passively safe co-elliptic approach and safety ellipse with covariance analysis; a guidance test from 50 m to 5 m near GEO; sequential convex programming guidance with H-infinity control, validated by a 1,000-run statistical analysis with a LIDAR navigation filter; Monte Carlo on a tumbling-target controller; reachability-based safe-start regions | Naasz et al. 2011; MIT thesis; Madonna et al. 2025; AAS 25-507; arXiv 2607.02128 |
| Client-side markers | Retroreflective and 2D/3D markers improve pose and spin-rate estimation; GEO monocular pose with retroreflective markers tested on synthetic images; markers on every face help when tumbling; marker claims that they make assets serviceable cheaply (company statement) | Opromolla et al. 2022; ESA navigation markers talks; Napolano group; IAF GLEX-2025; Orbit Fab |
| Cooperative vs non-cooperative clients | A cooperative client carries features and information links that aid acquisition, tracking and mating, and cooperability is a spectrum; almost no satellite carries fiducials or capture interfaces; a satellite in safe mode may tumble | CSPS report 2019; Frontiers in Robotics and AI editorial 2019 |
| Physical and data interfaces | Open capture interface MICE (ESA baseline for removal); MASI docking interface with data, power and fluid transfer; CONFERS practices; AIAA S-157 (fluid transfer) and S-159 (power and data, in public review) | GMV and ESA pages; Padova MASI record; CONFERS; AIAA |
| Why tumble rate matters | Tumble rate directly affects trajectory design and propellant use; estimators exist for when rates cannot be measured; beacon telemetry can be used to infer tumble rate | NRL paper; NASA paper; amateur beacon analysis |
| Economics of servicing | Expected-value method with a threshold on docking-success probability; GEO life extension viable near term, component exchange mid term; cost driven by servicer mass; value of serviceability hard to justify; a sceptical view (advocacy) that disposable satellites undercut the market | Sullivan 2005 (UMD); Verheyden et al. 2008 (JBIS); AAS 2009; MIT thesis; KTH report; New Space Economy 2025 |
| Propellant gauging | Book-keeping and PVT are most accurate early and degrade late; combining methods is recommended; reported errors at beginning vs end of life: book-keeping 0.1% to 4.6%, PVT 1.0% to 4.8% | Aerospace 2023; thesis and Turkish study |

## 2. What I could not find (candidates for uniqueness)

| # | Candidate | What I found instead | Strength of the claim |
|:--|:--|:--|:--|
| U1 | **A controlled, paired measurement of client preparation on closed-loop outcomes**, across tumble rates, with an identity-only control that isolates the value of rate data | Marker papers validate pose estimation; the closest "prepared vs unprepared" statement (IAF 2025) is qualitative. No paired comparison of unprepared, markers, beacon and handover found. Value of client telemetry is described qualitatively (NRL) | Moderate. Our result: +51 pp from markers and +8 pp from rate data at 3 deg/s, identity-only radio adds nothing |
| U2 | **The deliverable is a serviceability envelope and a minimum-preparation answer**, organised by client state (nominal, degraded, tumbling) | Literature separates servicer GNC from interface standardisation; "cooperability is a spectrum" is described but not quantified | Moderate. It is a framing plus evidence, not a new algorithm |
| U3 | **An information and handover layer for the degraded client**: an independently powered beacon with defined fields, and an IOS state machine with a single-authority invariant, tested coupled to the approach outcome | No source found for a dedicated servicing beacon with client control handover; FDIR is described as an on-board function; physical and power/data interface standards are covered, not this layer | Moderate but **unverified**. Absence in a web search is weak evidence; needs a patent search |
| U4 | **A money chain from simulated outcomes to euros per client per tier**, including break-even chance of needing rescue and servicer break-even price | Sullivan (2005) already gives an expected-value method with a docking-success threshold; AAS 2009 shows mass drives cost | Moderate-low as a method; the new part is tier-level linkage to simulated outcomes (retry only after a complete retreat) |
| U5 | **One demonstrated lifecycle**: ground approvals and audit, on-board hash-chained downlink, fuel gauging, all in one platform | Each part exists separately | Weak as science, useful as a differentiator and demo |

## 3. What is not unique (do not claim)

* Servicer guidance, navigation and control for tumbling targets (Naasz, Madonna, others).
* Fiducial or retroreflector pose estimation and the idea that markers are cheap (Opromolla, ESA, Orbit Fab).
* Interface standards: MICE, MASI, CONFERS practices, AIAA S-157 and S-159.
* Expected-value servicing economics as a method (Sullivan 2005, JBIS 2008).
* PVT and book-keeping propellant gauging, and combining them. Our 3-state filter is an integration. I found no paper on Kalman fusion of the two, but that is not evidence it is new in industry. Our simulated 1.2 kg RMS error uses assumed sensor accuracies and is **not comparable** to the published figures.

## 4. How to say it

"Existing work makes the servicer smarter and standardises the physical interfaces. We ask a different question: what is the minimum a client must carry to stay serviceable when it is degraded, and what is that worth? We measure it with paired simulations, add an information and handover layer for the degraded state, and turn the result into a price per client."

Risks to the claim: a reviewer will cite Sullivan (2005) for the economics and CONFERS and AIAA S-159 for interfaces; the beacon and IOS idea may exist in patents or internal industry documents; our evidence is simulation only.

## 5. Next steps

1. Read the full texts of Sullivan 2005, Madonna 2025, Opromolla 2022, the CSPS report, CONFERS practices and AIAA S-159.
2. Patent search on service beacon, client control handover, servicing-mode safe-mode behaviour.
3. Ask ClearSpace whether internal studies already quantify client preparation.
4. Add the verified rows to the Need and State of the Art section of the proposal.

## Sources

* Naasz et al., guidance and navigation for approach to a noncooperative spacecraft at GEO (J. Astronaut. Sci., 2011): [author page](https://independent.academia.edu/BNaasz)
* MIT thesis on guidance for an uncooperative tumbling satellite near GEO: [DSpace](https://dspace.mit.edu/handle/1721.1/122374)
* Madonna et al., Guidance and Control Architecture for Rendezvous and Approach to a Non-Cooperative Tumbling Target, Aerospace 12(8) 708, 2025: [MDPI](https://www.mdpi.com/2226-4310/12/8/708), [Naples record](https://iris.unina.it/handle/11588/1012249)
* Reachability-based safe-start regions, arXiv: [2607.02128](https://arxiv.org/pdf/2607.02128)
* Frontiers in Robotics and AI editorial on OOS and ADR: [PMC7806039](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7806039/)
* CSPS report on on-orbit servicing (Davis, Mayberry, Penn): [PDF](https://csps.aerospace.org/sites/default/files/2021-08/Davis-Mayberry-Penn_OOS_04242019.pdf)
* CONFERS: [practices and STSC briefing](https://swfound.org:443/media/206366/confers_stsc_final_13feb2019.pdf), [AIAA S-159 public review](https://satelliteconfers.org/news/726224/AIAA-Public-Review-for-On-Orbit-Servicing-Power-and-Data-Interfaces-Standard.htm), [AIAA S-157](https://satelliteconfers.org/news/695924/CONFERS-Announces-Publication-and-Availability-of-New-Standard-AIAA-S-157-2024.htm)
* MICE and MASI: [GMV MICE](https://www.gmv.com/en-es/docs/mice), [Padova MASI record](https://research.unipd.it/handle/11577/3588978), [ESA docking interoperability tests](https://www.esa.int/Enabling_Support/Space_Engineering_Technology/New_tests_for_rendezvous_and_docking_interoperability)
* Markers: [Opromolla et al. 2022](https://iris.unina.it/handle/11588/895682), [ESA navigation markers](https://indico.esa.int/event/644/contributions/12236/attachments/7562/14518/Navigation%20Markers%20Development.pdf), [Napolano group](https://iris.unina.it/handle/11588/976264), [IAF GLEX-2025](https://dl.iafastro.directory/event/GLEX-2025/paper/93741/), [arXiv 2606.27566](https://arxiv.org/pdf/2606.27566)
* Economics: [Sullivan 2005, UMD](https://drum.lib.umd.edu/handle/1903/2330), [Verheyden et al. 2008, JBIS](https://bis-space.com/shop/?p=8702), [KTH report](https://intra.kth.se/polopoly_fs/1.1022440.1603372885!/SD2905_BlueTeam_Services.pdf), [MIT thesis on value of serviceability](https://dspace.mit.edu/handle/1721.1/40857), [New Space Economy 2025 (opinion)](https://newspaceeconomy.ca/2025/11/12/why-is-in-orbit-satellite-servicing-a-solution-without-a-problem/)
* Propellant gauging: [Aerospace 2023 (DOAJ)](https://doaj.org/article/688d598258024d9fae95fd32a31a4f30), [IISc thesis](https://etd.iisc.ac.in/handle/2005/579)
* Tumble rate and telemetry: [NRL paper on retired GEO satellites](https://ntrs.nasa.gov/api/citations/20120000714/downloads/20120000714.pdf), [NASA estimator paper](https://ntrs.nasa.gov/api/citations/20050210231/downloads/20050210231.pdf)
