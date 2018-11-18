from migen import *
from migen.genlib.fsm import *

from .protocol import *
from .phy_rx import *
from .phy_tx import *


__all__ = ["PCIePHY"]


class PCIePHY(Module):
    def __init__(self, lane):
        self.submodules.rx = PCIePHYRX(lane)
        self.submodules.tx = PCIePHYTX(lane)

        ###

        self.comb += [
            self.tx.ts.n_fts.eq(0xff),
            self.tx.ts.rate.gen1.eq(1),
        ]
