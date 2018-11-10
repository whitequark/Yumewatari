import unittest

from ..gateware.serdes import *
from ..gateware.phy import *
from . import simulation_test


class PCIePHYTestbench(Module):
    def __init__(self):
        self.submodules.lane = PCIeSERDESInterface()
        self.submodules.phy  = PCIePHY(self.lane)

    def do_finalize(self):
        self.states = {v: k for k, v in self.phy.fsm.encoding.items()}

    def phy_state(self):
        return self.states[(yield self.phy.fsm.state)]


class PCIePHYTestCase(unittest.TestCase):
    def setUp(self):
        self.tb = PCIePHYTestbench()

    def assertState(self, tb, state):
        self.assertEqual((yield from tb.phy_state()), state)

    @simulation_test
    def test_recv_ts1(self, tb):
        pass
