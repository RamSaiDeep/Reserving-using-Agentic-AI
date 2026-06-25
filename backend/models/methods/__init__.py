import warnings

warnings.warn(
    "The backend/models/methods package is deprecated and will be removed in a future release. "
    "Use backend/reserving/methods instead.",
    DeprecationWarning,
    stacklevel=2
)

from .chain_ladder import ChainLadder
from .mack_chain_ladder import MackChainladder
from .bornhuetter_ferguson import BornhuetterFerguson
from .benktander import Benktander
from .cape_cod import CapeCod
from .case_outstanding import CaseOutstanding
from .clark import Clark
from .expected_loss_ratio import ExpectedLossRatio
from .frequency_severity import FrequencySeverity

METHODS = {
    'CL': ChainLadder,
    'MCL': MackChainladder,
    'BF': BornhuetterFerguson,
    'BK': Benktander,
    'CC': CapeCod,
    'CO': CaseOutstanding,
    'CLK': Clark,
    'ELR': ExpectedLossRatio,
    'FS': FrequencySeverity
}
