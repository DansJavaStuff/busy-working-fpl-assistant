# Early-season form sensitivity

This is a research comparison, not a new production model. Live projections still use `min(completed_gameweeks / 6, 1)` as the current-season PPG weight. No chip thresholds, captain weights or transfer gates change.

## Initial supplied GW6 evidence

Recomputing the supplied five player records with their other inputs held fixed gives:

| Player | Current 6-GW rule | 12-GW rule | 12-GW rule with minutes cap |
|---|---:|---:|---:|
| Groß | 8.668 | 7.519 | 7.519 |
| Bogle | 8.059 | 6.911 | 6.694 |
| Haaland | 6.999 | 6.791 | 6.791 |
| Tarkowski | 7.594 | 6.719 | 6.719 |
| Mukiele | 2.265 | 2.580 | 2.643 |

The current-season weight goes from 5/6 to 5/12 in the second column of alternatives. Captain weighting still favours Groß under these alternatives. Haaland overtakes Bogle on captain score, changing the vice ranking among these three players. These are projections, not observed outcomes; the initial calculation is limited to the supplied players. It cannot establish the full optimiser's transfer choices or their accuracy.

## Full-pool command on the Pi

```bash
time python3 -m tools.compare_form_sensitivity
```

The command fetches fresh official bootstrap/fixtures, loads one projection pool and live squad, then saves a private, uniquely named input bundle under ignored `data/runtime/form_sensitivity/`. Capture uses existing third-party depth-chart and historical-prior mechanisms; the responses are sequential, not an atomic API snapshot. Same-GW KEEP/INCLUDE constraints are copied from the saved weekly report if present. It never calls transfer/team submission endpoints or writes the weekly recommendation/approval/report.

Three variants run on that same input bundle, each solving 0–3 transfers:

- `control_6gw`: unchanged six-completed-GW weighting.
- `form_12gw`: `min(completed_gameweeks / 12, 1)`.
- `form_12gw_minutes_cap`: cap the 12-GW weight further at `minutes / 1080`, equivalent to twelve full matches of minutes. This is an exposure proxy, not a count of actual appearances.

The projection function accepts an explicit research override; default callers retain the original rule. Players now preserve their original projection inputs and availability factor for replay. The control must reproduce all five captured weekly projections to within 1e-9 before any solver comparisons proceed. Bundles must match the projection/context/transfer/research code signature; a model-code change requires a new capture.

The output reports recommended transfers/hits/gains, captain/vice, owned captain rankings and stability across variants. It reproduces HQ's existing free/paid transfer gates, including the 3-point additional net-gain gate for paid plans. Gains are compared with HOLD *within each variant*; do not interpret a lower absolute score under stronger shrinkage as worse performance.

The captured bundle path is printed before solving. To replay later without API calls or changes to that bundle:

```bash
python3 -m tools.compare_form_sensitivity --input data/runtime/form_sensitivity/PASTE_CAPTURE_FILENAME.json
```

To capture now and defer solving, use `--capture-only`. A failed solve leaves its saved input bundle available for replay. On the Pi, CBC remains `/usr/bin/cbc`. This is 12 solves over one pool; no reliable Pi duration is established yet.

## Interpretation and limits

- FPL `ep_next`, fixtures, priors, availability, captain multipliers and transfer gates remain fixed. `ep_next` may itself contain form information, so these variants do not remove all early-season form influence.
- Availability and team news can change after capture, especially during international duty. These are provisional research rankings, not an instruction to apply today's plan. Refresh live advice closer to the deadline.
- Three fixed alternatives are a sensitivity check, not tuning against a preferred player. Stability does not prove accuracy; instability identifies a decision to scrutinise.
- The tool compares transfer/captain advice, not chip values or future news. It is not an evaluation of realised points.
- An infeasible HOLD baseline, including an incoming INCLUDE constraint, prevents a meaningful comparison and stops the run. A larger transfer-count search is out of scope.
- Next evidence: full-pool Pi output, then chronological live snapshots and realised outcomes. Do not promote an alternative solely because it makes a familiar player captain or changes this week's transfer.
