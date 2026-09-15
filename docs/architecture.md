# Project Architecture

## Folder hierarchy

```text
adc_sim/
  item_base.py            Shared `Item` interface and generic item state
  core_items.py           Legendary/core item combat behaviors
  component_items.py      Basic and epic component combat behaviors
  utility_items.py        Starter, boots, and consumable combat behaviors
  data/
    items_data.py         Static item catalog: names, prices, tiers, recipes, stats, sources
    items_registry.py     Item-key-to-runtime-instance creation interface
  simulations/
    vayne.py              Vayne combat model, candidate pools, and default 1–5 core search
    azir.py               Azir combat setup (sand-soldier AA, mid-quest boots/AP), candidate pools,
                          default 1–5 core receding-horizon search, legacy 4-core ranking
    ranking_core.py       Preserved weighted exhaustive-ranking helper
```

## File roles and data flow

1. `items_data.py` is the source of truth for static item metadata and numeric stats.
2. `item_base.py` defines the common runtime interface and default no-op combat hooks.
3. Behavior modules contain only effects that need runtime state or combat hooks.
4. `items_registry.py` selects a behavior class and injects static data into its instance.
5. Simulations consume item instances produced by the registry. Tests or specialized simulation
   code may import a concrete behavior from its role-specific module.
6. Raw `namu_wiki/` text is provenance input, not a runtime dependency. Normalized records retain
   the source filename and page modification timestamp.
7. Champion simulation modules own their combat setup, candidate pools, and default search entry
   point. Vayne's default is the 1–5 core receding-horizon search that maximizes discounted
   marginal DPG; its former 1–4 core exhaustive ranking remains available as a compatibility mode.
8. New champion search migrations should adopt the receding-horizon method, while existing
   champion entry points remain unchanged until individually migrated and verified.

Unsupported passives are cataloged as `unsupported`; they must not silently affect simulation
results. This label records an implementation boundary, not a claim about the game mechanic.

## Change log

### 2026-07-14 — Split item behavior modules

- Reason: `adc_sim/items.py` mixed the base interface, components, utility items, and core-item
  behaviors in one 897-line module. Splitting by runtime role makes static catalog expansion and
  later behavior implementation independently testable.
- User approval justification: the user explicitly approved the proposed split and creation of
  this reserved architecture document on 2026-07-14.
- Migration safety: the legacy `items.py` implementation remains until the split modules and
  registry path are verified. Its removal requires a separate explicit approval.

### 2026-07-14 — Remove the legacy item module

- Reason: the split modules and registry path passed the full regression suite, so retaining a
  second implementation would create duplicate definitions and competing edit locations.
- User approval justification: after receiving the verification result, the user explicitly
  approved replacement and removal of `adc_sim/items.py` on 2026-07-14.
- Verification prerequisite: 123 tests passed before removal; the suite is run again after all
  direct imports are migrated.

### 2026-07-25 — Make receding-horizon search the Vayne default

- Reason: keep Vayne's DPS setup, candidate pools, and default 1–5 core build search in one
  champion module, using discounted marginal DPG (`gamma=0.8`, updated project default on
  2026-07-27) as the project migration target.
- Original roles: `vayne.py` owned DPS and 1–4 core exhaustive ranking;
  `vayne_sequential_greedy.py` separately owned the 1–5 core receding-horizon search.
- New roles: `vayne.py` owns both the preserved exhaustive APIs and the default receding-horizon
  entry point. The old module is temporarily a compatibility wrapper pending verification and
  separate deletion approval.
- User approval justification: the user approved the proposed Vayne-first migration scope and
  architecture update on 2026-07-25.

### 2026-07-25 — Remove the standalone Vayne sequential-search module

- Reason: the receding-horizon implementation and CLI were integrated into `vayne.py`, and the
  temporary compatibility wrapper had no remaining runtime responsibility.
- User approval justification: after the integrated implementation passed all 159 project tests,
  the user explicitly approved deleting `adc_sim/simulations/vayne_sequential_greedy.py`.
- Verification prerequisite: direct imports and CLI documentation were migrated to `vayne.py`
  before deletion; the focused and full suites are run again after removal.

### 2026-08-27 — Add Azir (mid AP) champion module and AP item catalog

- Reason: first mage-style champion. Sand-soldier attacks replace basic attacks (magic, 50% on-hit,
  ability effects), so the champion owns a full `get_one_hit_damage` override plus item hooks
  (`on_spell_effect`, `apply_dot`, `get_bonus_ap`, `get_bonus_as`, `try_stormraider`, `active_damage`)
  that only Azir consumes — existing champions and the engine are unchanged.
- New files: `adc_sim/simulations/azir.py`, `tests/test_azir.py`,
  `docs/superpowers/specs/2026-08-27-azir-design.md`. Extended: `items_data.py` (AP legendaries,
  tier-3 boots, `mana_regen` stat key, `cryptbloom` in `MAGIC_PEN_EXCLUSIVE`), `core_items.py`,
  `utility_items.py`, `champion.py` (`Azir` class appended), `power_compare.py` (Azir branch).
- Search: receding-horizon default per rule 8; `legacy-ranking` 4-core exhaustive kept as a mode.
- User approval justification: the user requested the addition and confirmed the modeling
  decisions (soldier event model, W+Q+E+R, item scope, PtA·LT + control build) on 2026-08-27.
