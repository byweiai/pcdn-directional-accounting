# Third-party inputs and their licences

This release does not redistribute any of them. Each entry says where it comes from,
what it is used for, and what to fetch.

## UNSW-NB15

- Source: the NIDS dataset release archived at Zenodo, record 10140548
  (`https://zenodo.org/records/10140548`), together with its flow-feature CSV.
- Licence: the dataset's own terms (research use, attribution). Check the record
  before redistributing anything derived from it.
- Used by: `src/e1_unsw.py` (endpoint panel, flow-ratio percentiles),
  `src/e2_window.py` (out-of-sample detector, dilution, disguise),
  `src/e7_meter.py` (packet-size mix), `src/e12_floor.py`, `src/e13_rigor.py`.
- Local files: `data/eOneFlows` (flow CSV) and the endpoint panel it yields,
  `data/e1_panel.csv`, which *is* redistributed here because it is derived,
  aggregated and carries no payload or address beyond the benchmark's own scope.

## CIC-IDS2017, NetTiSA flow representation

- Source: Zenodo record 8301043 (`https://zenodo.org/records/8301043`).
- Licence: as stated on that record.
- Used by: `src/e3_cic.py` for the independent-corpus check behind Fig. S5.

## PeeringDB

- Source: the public registry API (`https://www.peeringdb.com/api/net`), snapshot
  taken at run time.
- Licence: PeeringDB's terms of use; the snapshot is factual registry data.
- Used by: `src/e4_peeringdb.py` for the cross-section behind Fig. S4. The snapshot
  is not shipped; the script refetches it and caches under `data/`.

## MAWI backbone capture

- Source: the WIDE MAWI working-group trace archive.
- Used by: `src/pcap_stats.py` as a sanity check on packet sizes only. The capture is
  not shipped and no result in the paper depends on it beyond that check.

## Values quoted from other papers

`23,631` subscriber lines and `84.99%` of traffic in `paper/main.tex` are values
reported in the two 2026 papers the manuscript responds to, not measurements made
here; they are cited at the point of use and are outside the scope of this release.
