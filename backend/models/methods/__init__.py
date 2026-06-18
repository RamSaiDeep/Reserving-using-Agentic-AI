from .chain_ladder import ChainLadder
from .mack_chain_ladder import MackChainladder
from .bornhuetter_ferguson import BornhuetterFerguson
from .benktander import Benktander
from .cape_cod import CapeCod
from .case_outstanding import CaseOutstanding
from .clark import Clark

METHODS = {
    'CL': ChainLadder,
    'MCL': MackChainladder,
    'BF': BornhuetterFerguson,
    'BK': Benktander,
    'CC': CapeCod,
    'CO': CaseOutstanding,
    'CLK': Clark
}
