"""The single source of truth for what the submission package asserts.

Both the quick-fill page generator and the gate import from here, so a change to
a declaration cannot reach one of them without reaching the other. The facts are
the author's own statements about the work plus the mapping between a figure
number in the manuscript and the vector file that produced it.
"""

TITLE = ('Upload May Not Exceed Download: Directional Accounting for '
         'Peer-Assisted Delivery in Operator Networks')

AUTHORS = [
    ('Yue Lv',
     'China Mobile Communications Group Yunnan Co., Ltd., Kunming 650000, China',
     'lvyue@yn.chinamobile.com', '0009-0006-7743-1644',
     'Corresponding and sole'),
]

DECLARATIONS = (
    'Original work; not published; not under consideration elsewhere; no '
    'preprint posted; no competing interests; data and analysis code '
    'available from the corresponding author.')

DATA_AVAILABILITY = (
    'Public corpora: UNSW-NB15 (Zenodo 10140548), NetTiSA flow representation '
    'of CIC-IDS2017 (Zenodo 8301043), PeeringDB registry.')

# Manuscript figure number -> the file that produced it. The order is the order
# the figures appear, which is the order the portal expects if it asks for them
# separately.
FIG_FILES = [
    (1, 'fig1_mechanism.pdf'),
    (2, 'fig3_evasion.pdf'),
    (3, 'fig2_separation.pdf'),
    (4, 'fig10_closures.pdf'),
    (5, 'fig7_regimes.pdf'),
]

# Identifiers that must not survive into either PDF.
IDENTITY = ('yue lv', 'lvyue', '0009-0006', 'yunnan', 'kunming',
            'china mobile', 'rui zhang')
