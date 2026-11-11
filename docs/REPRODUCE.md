# Which script produces what

Run order matters only where a script imports another (`e5_noquota.py` imports
`e5_regime.py` for the shared seed and parameters). Seeds are fixed in the scripts.

| Manuscript object | Script | Output |
|---|---|---|
| TABLE II, three regimes | `src/e5_noquota.py` | `data/e5_noquota.json` (`base`) |
| TABLE III, elasticity | `src/e5_regime.py` (`demand_block`) + `src/make_numbers.py` | `data/e5_regime.json` (`demand`) |
| TABLE IV, ratio-quota sweep | `src/e5_noquota.py` (`sweep.ratio`) | `data/e5_noquota.json` |
| TABLE I, positioning | no numbers | — |
| Fig. 1 mechanism | `src/make_figs.py` (`fig1_mechanism`) | `fig/fig1_mechanism.pdf` |
| Fig. 2 separation | `src/e1_unsw.py`, `src/e9_threshold.py`, `make_figs` (`fig2_separation`) | `data/e1_unsw.json`, `data/e9_threshold.json` |
| Fig. 3 dilution and disguise | `src/e2_window.py`, `make_figs` (`fig3_evasion`) | `data/e2_window.json` |
| Fig. 4 the two tests | `src/e10_temporal.py`, `src/e11_farm.py`, `make_figs` (`fig10_closures`) | `data/e10_temporal.json`, `data/e11_farm.json` |
| Fig. 5 the regimes | `src/e5_noquota.py`, `src/e5_regime.py`, `make_figs` (`fig7_regimes`) | `data/e5_noquota.json`, `data/e5_regime.json` |
| Fig. S1 sweeps | `src/e2_window.py`, `src/e5_regime.py`, `src/e9_threshold.py`, `make_figs` (`figA_sweeps`) | the three JSON files |
| Fig. S2 welfare against the externality price | `src/e14_policy.py`, `src/e15_sampling.py`, `make_figs` (`fig11_audit`) | `data/e14_policy.json`, `data/e15_sampling.json` |
| Fig. S3 window sweep | `src/e8_window_sweep.py`, `make_figs` (`fig6_window`) | `data/e8_window.json` |
| Fig. S4 PeeringDB cross-section | `src/e4_peeringdb.py`, `make_figs` (`fig5_peeringdb`) | `data/e4_peeringdb.json` |
| Fig. S5 robustness on a second corpus | `src/e3_cic.py`, `src/e3_external.py`, `make_figs` (`fig4_robustness`) | `data/e3_cic.json`, `data/e3_external.json` |
| Fig. S6 metering cost | `src/e7_meter.py`, `make_figs` (`fig8_meter`) | `data/e7_meter.json` |
| Fig. S7 dual use | `src/e16_dualuse.py`, `src/fig12_dualuse.py` | `data/e16_dualuse.json`, `data/e17_transfer.json` |
| Supplement, trigger without the direction | `src/e5_regime.py` (`volume_trigger_block`) | `data/e5_regime.json` (`volume_trigger`) |
| Supplement, floor sweep | `src/e12_floor.py` | `data/e12_floor.json` |
| Supplement, range and sampling | `src/e13_rigor.py`, `src/e15_sampling.py` | `data/e13_rigor.json`, `data/e15_sampling.json` |
| Supplement, fan-out | `src/e6_fanout.py` | `data/e6_fanout.json` |
| Supplement, adaptive evasion | `src/e18_adaptive.py` | `data/e18_adaptive.json` |

`src/verify_package.py` and `src/check_all.py` are the submission gates, not
analysis: they check page count, abstract length, macro coverage, anonymity and the
consistency of the upload files.

## Determinism

Every script takes its seed from a literal at the top of the file; `e2_window.py`
trains one model per grouped fold and the fold assignment comes from
`GroupKFold(shuffle=False)` over sorted address pairs. Rerunning on the same
numpy/scikit-learn versions reproduces the JSON byte for byte; `requirements.txt`
pins the ranges used.
