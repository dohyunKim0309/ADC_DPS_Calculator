# ADC DPS Calculator

*[한국어 README](README.ko.md)*

An event-driven League of Legends combat simulator that exhaustively searches and ranks ADC (Attack Damage Carry) item build orders by DPS and gold efficiency — re-run every patch.

Stats sites (op.gg, u.gg, lolalytics) aggregate what players *actually* build and win with. This project answers a different question: **what does the math say should be strong** — computed from an explicit, auditable damage model before the meta settles. Every modeled mechanic is implemented from multi-source cross-validated patch data, and every untested assumption is tagged as a hypothesis in the code.

## Sample output (patch 26.13, DDragon data 16.13)

Cross-champion comparison of each champion's best-found 4-item build (single target, sustained-kill measurement). Builds are compared at all four item spikes; the excerpt below is the **3-item spike** — DPS/Gold measured with the first three items completed, each build's 4th item in parentheses:

```text
=== Cross-Champion Top1 Compare (1~4 Core) ===
[3 Core] Winner: Vayne (159.40 DPG)
  - Vayne  DPG 159.40 | DPS 1801.2 | Gold 11300 | Yun Tal → IE → LDR (4th: PD)
  - CogMaw DPG 130.71 | DPS 1359.4 | Gold 10400 | Guinsoo → Nashor → Dusk&Dawn (4th: Rabadon)
  - KaiSa  DPG 108.97 | DPS 1133.3 | Gold 10400 | Guinsoo → Yun Tal → Nashor (4th: Terminus)
  - Corki  DPG 104.14 | DPS 1187.2 | Gold 11400 | Yun Tal → IE → LDR (4th: Essence)
  - Ashe   DPG  92.63 | DPS  981.9 | Gold 10600 | Yun Tal → C44 → LDR (4th: IE)
  - Yunara DPG  91.61 | DPS  989.4 | Gold 10800 | Guinsoo → Yun Tal → LDR (4th: IE)
  - Jinx   DPG  86.05 | DPS  912.2 | Gold 10600 | Yun Tal → C44 → LDR (4th: IE)
```

`DPG` = DPS per 1000 gold spent. (Ezreal has a dedicated sim but isn't wired into the cross-champion compare yet.) Things the model surfaced on 26.13: Vayne's *theoretical* best build is full crit, which outscores the standard on-hit build (BotRK → Guinsoo → Terminus) on a single target in this model; Kog'Maw's is hybrid AP on-hit; Ashe and Jinx converge on the same crit core. All of this inherits the model's limitations — see [Model limitations](#model-limitations-read-this-first).

## How it works

**Event loop** (`adc_sim/engine.py`) — time advances by the minimum of (next auto attack, next skill ready, next state change); simultaneous events resolve skills before attacks; an epsilon nudge prevents same-timestamp stalls. A kill refills the dummy to full (overkill damage carries over) and the standard measurement kills **2 full health bars**, so burst openers are amortized and current-HP effects (e.g. BotRK) aren't overvalued.

**Damage pipeline** (`adc_sim/champion.py`) — expected-value crit on autos → on-hit stacking with per-item proc counts (Guinsoo's doubles on-hit procs; "extra on-hit application" effects like Dusk & Dawn stack additively on top) → damage amplifiers (some multiplicative, some conditional, e.g. Shadowflame only below 40% HP) → armor/MR mitigation with multiplicative %-pen and flat pen, true damage bypassing it. Champion kits are modeled as engine events: Vayne's Silver Bolts 3-hit true damage, Kog'Maw's W max-HP% magic on-hit, Jinx minigun stacks, Yunara's transcendence rotation, etc.

**Mana as a hard resource** — casts are gated by current mana with regen per tick; a skill off cooldown but unaffordable waits for regen. No infinite-mana hand-waving.

**Ranking methodology** — for each champion, all 4-item purchase orders from a champion-specific pool are enumerated (with constraints like "at most one %-armor-pen item per build"). Each build is scored at 4 power spikes (1/2/3/4 items, each with fixed champion level and target stats), as **gold efficiency relative to a fixed control build** — each champion's standard meta build (e.g. Kraken → PD → IE → LDR for Ashe, BotRK → Guinsoo → Terminus → PD for Vayne) — weighted 5:4:3:3 toward early cores, so a score reads as "% of the meta build's gold efficiency". Identical 4-item *sets* dedup to their best order. Simulation results are memoized by item set, which is what makes exhaustive search tractable.

**Case-based ranking** (`case_ranking.py`) — beyond single rankings, a 28-case grid (defensive-item timing × which defensive item × anti-heal requirement × zeal-item requirement) re-ranks the full non-defensive item pool per scenario, with configurable weight profiles.

## Scope

| | |
|---|---|
| Champions | Ashe, Vayne, Jinx, Kai'Sa, Corki, Ezreal, Kog'Maw, Yunara |
| Keystones | Lethal Tempo, Press the Attack, Conqueror (+ Coup de Grace / Cut Down) |
| Items | Current ADC pool incl. Yun Tal, Terminus, Dusk & Dawn, Navori Flickerblade, Hextech Scope C44 … (`adc_sim/data/items_data.py` is the single source of stats/prices) |
| Data sources | Community Dragon connector + manual cross-validation against DDragon / LoL Wiki / Meraki |

## Quick start

Requires Python 3.10. The only dependency is matplotlib.

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# per-champion build rankings (opens a matplotlib window at the end)
.venv/bin/python -m adc_sim.simulations.vayne
.venv/bin/python -m adc_sim.simulations.ashe

# cross-champion comparison
.venv/bin/python -m adc_sim.simulations.power_compare

# case-based ranking, table-only (headless-safe), optional case filter
.venv/bin/python -m adc_sim.simulations.case_ranking "def@4/nohc"
```

Full ranking runs take a few minutes. Case-filter tokens map to the case axes: `def@4` = defensive item bought 4th, `nohc` = no anti-heal required, `zealfree` = no zeal-item constraint, and so on. Headless / CI: prefix with `MPLBACKEND=Agg` to suppress the blocking plot window. CSV/JSON report export is off by default — enable `result_export_enabled` in `adc_sim/settings.py`.

## Project layout

```text
adc_sim/
  engine.py        # event loop + mitigation
  champion.py      # damage model, champion kits (event-driven skills, mana)
  items.py         # item behavior classes (on-hit, spellblade, amp hooks)
  runes.py         # keystones + secondaries (adaptive on-hit split)
  data/
    items_data.py      # item stats/prices — single source of truth
    items_registry.py  # key → configured item instance
    cdragon.py         # Community Dragon connector (patch diffing aid)
  simulations/     # per-champion build search + ranking + reports
tests/             # 70+ unit & regression tests
```

## Per-patch workflow

1. Diff patch notes; pull raw data via the CDragon connector, cross-check against DDragon/Wiki (no source is fully accurate — champion spell data in particular).
2. Update `items_data.py` / champion subclasses. New mechanics get a behavior class and an explicit hypothesis tag (`[Hypothesis]`, `H-VAYNE-W`, …) when the interaction isn't verifiable.
3. Re-run rankings; the DPS regression snapshot (`tests/_baseline_dps.json` + `test_regression_diff`) fails loudly if any champion's numbers move unintentionally.

## Model limitations (read this first)

This is a **theory model, not measured game data**. Rankings are best-case estimates under explicit assumptions:

- Single-target training dummy: no movement, range differences, positioning risk, CC, shields, or team context.
- 100% attack uptime is assumed regardless of range — no kiting or windup downtime, which flatters short-range champions (Vayne, Kog'Maw). Target armor/MR per item spike is fixed and defined per simulation module (`CORE_TARGET_STATS`).
- Sustained-DPS measurement; utility and burst-window value are out of scope.
- Some champion strengths are deliberately unmodeled and those champions read low — e.g. Jinx's Get Excited! resets/AoE rockets, Vayne's Condemn. The tool tells you *auto-attack DPS math*, not "who wins games".
- Item/rune interactions that can't be verified from data are shipped as tagged hypotheses — corrections welcome, they're one-line data edits in most cases.

## Tests

```bash
.venv/bin/python -m pip install pytest   # test-only dependency
.venv/bin/python -m pytest tests/ -q
```

Per-mechanic unit tests (Silver Bolts placement, Guinsoo proc math, mana gating, adaptive rune split …) plus a cross-champion DPS regression snapshot to catch unintended model drift.

## License

**TBD** — a license is being decided (permissive vs. noncommercial) and will be added shortly; until then the code is source-available for reading and review, and reuse requires permission. Questions, corrections, and assumption-challenges are welcome as issues regardless.
