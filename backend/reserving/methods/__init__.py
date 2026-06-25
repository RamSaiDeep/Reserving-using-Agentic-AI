from .cl import ChainLadder
from .bf import BornhuetterFerguson
from .mack import MackChainladder
from .cape_code import CapeCod
from .benktander import Benktander
from .case_outstanding import CaseOutstanding
from .clark import Clark
from .elr import ExpectedLossRatio
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
