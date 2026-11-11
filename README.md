# Upload May Not Exceed Download: Directional Accounting for Peer-Assisted Delivery in Operator Networks

Code and derived data for the manuscript submitted to *IEEE Transactions on
Network Science and Engineering*. Everything here is what the paper's numbers are
computed from: the analysis scripts, the JSON they emit, and the figures built from
those JSON files.

Version 1.0.0 · DOI (Zenodo) minted from the GitHub release · Licence: code MIT,
derived data CC BY 4.0.

## Layout

| Path | Contents |
|---|---|
| `src/` | analysis scripts, one per experiment group (`e1`–`e18`) plus `make_numbers.py`, `make_figs.py`, `fig12_dualuse.py` |
| `data/` | the JSON each script writes; every number in the paper is read from here |
| `fig/` | the figure PDFs the manuscript embeds |
| `docs/` | reproduction map, provenance and licences of the third-party corpora |

## What is not here

The three input corpora are third party and are not redistributed. `docs/PROVENANCE.md`
names each one, its licence, its version and where to fetch it; `src/e4_peeringdb.py`
pulls the PeeringDB snapshot itself and caches it under `data/`.

## Reproduce

```
python -V            # 3.13
pip install -r requirements.txt
cd src
python e1_unsw.py        # endpoint panel and flow-ratio statistics   -> data/e1_unsw.json
python e2_window.py      # out-of-sample detector, dilution, disguise -> data/e2_window.json
python e5_noquota.py     # three regimes, balanced ledger, sweeps     -> data/e5_noquota.json
python e5_regime.py      # elastic demand, wash scan, volume trigger  -> data/e5_regime.json
python make_numbers.py   # every LaTeX macro the manuscript quotes    -> paper/numbers.tex
python make_figs.py      # Figures 1-5 and S1-S6
```

`docs/REPRODUCE.md` gives the full order and the exact script behind each table,
figure and claim that carries a number.

## Cite

```
Lv, Yue. (2026). Upload May Not Exceed Download: Directional Accounting for Peer-Assisted Delivery in Operator Networks (Version 1.0.0) [Computer software].
Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX
```
