import unittest
from migen import *

from ..gateware.serdes import *
from ..gateware.serdes import K, D
from ..gateware.phy_tx import *
from . import simulation_test


class PCIePHYTXTestbench(Module):
    def __init__(self, ratio=1):
        self.submodules.lane = PCIeSERDESInterface(ratio)
        self.submodules.phy  = PCIePHYTX(self.lane)

    def do_finalize(self):
        self.states = {v: k for k, v in self.phy.emitter.fsm.encoding.items()}

    def phy_state(self):
        return self.states[(yield self.phy.emitter.fsm.state)]

    def receive(self, count):
        symbols = []
        for _ in range(count):
            word = yield self.lane.tx_symbol
            if self.lane.ratio == 1:
                symbols.append(word)
            else:
                symbols.append(tuple((word >> (9 * n)) & 0x1ff
                                     for n in range(self.lane.ratio)))
            yield
        return symbols


class _PCIePHYTXTestCase(unittest.TestCase):
    def assertReceive(self, tb, symbols):
        self.assertEqual((yield from tb.receive(len(symbols))), symbols)


class PCIePHYTXGear1xTestCase(_PCIePHYTXTestCase):
    def setUp(self):
        self.tb = PCIePHYTXTestbench()

    def assertReceive(self, tb, symbols):
        self.assertEqual((yield from tb.receive(len(symbols))), symbols)

    @simulation_test
    def test_tx_ts1_pad(self, tb):
        yield tb.phy.ts.valid.eq(1)
        yield tb.phy.ts.n_fts.eq(0xff)
        yield tb.phy.ts.rate.gen1.eq(1)
        yield
        yield from self.assertReceive(tb, [
            K(28,5), K(23,7), K(23,7), 0xff, 0b0010, 0b0000, *[D(10,2) for _ in range(10)],
            K(28,5)
        ])

    @simulation_test
    def test_tx_ts1_link(self, tb):
        yield tb.phy.ts.valid.eq(1)
        yield tb.phy.ts.link.valid.eq(1)
        yield tb.phy.ts.link.number.eq(0xaa)
        yield tb.phy.ts.n_fts.eq(0xff)
        yield tb.phy.ts.rate.gen1.eq(1)
        yield
        yield from self.assertReceive(tb, [
            K(28,5), 0xaa, K(23,7), 0xff, 0b0010, 0b0000, *[D(10,2) for _ in range(10)],
            K(28,5)
        ])

    @simulation_test
    def test_tx_ts1_link_lane(self, tb):
        yield tb.phy.ts.valid.eq(1)
        yield tb.phy.ts.link.valid.eq(1)
        yield tb.phy.ts.link.number.eq(0xaa)
        yield tb.phy.ts.lane.valid.eq(1)
        yield tb.phy.ts.lane.number.eq(0x01)
        yield tb.phy.ts.n_fts.eq(0xff)
        yield tb.phy.ts.rate.gen1.eq(1)
        yield
        yield from self.assertReceive(tb, [
            K(28,5), 0xaa, 0x01, 0xff, 0b0010, 0b0000, *[D(10,2) for _ in range(10)],
            K(28,5)
        ])

    @simulation_test
    def test_tx_ts1_reset(self, tb):
        yield tb.phy.ts.valid.eq(1)
        yield tb.phy.ts.n_fts.eq(0xff)
        yield tb.phy.ts.rate.gen1.eq(1)
        yield tb.phy.ts.ctrl.hot_reset.eq(1)
        yield
        yield from self.assertReceive(tb, [
            K(28,5), K(23,7), K(23,7), 0xff, 0b0010, 0b0001, *[D(10,2) for _ in range(10)],
            K(28,5)
        ])

    @simulation_test
    def test_tx_ts2(self, tb):
        yield tb.phy.ts.valid.eq(1)
        yield tb.phy.ts.n_fts.eq(0xff)
        yield tb.phy.ts.rate.gen1.eq(1)
        yield tb.phy.ts.ts_id.eq(1)
        yield
        yield from self.assertReceive(tb, [
            K(28,5), K(23,7), K(23,7), 0xff, 0b0010, 0b0000, *[D(5,2) for _ in range(10)],
            K(28,5)
        ])


class PCIePHYTXGear2xTestCase(_PCIePHYTXTestCase):
    def setUp(self):
        self.tb = PCIePHYTXTestbench(ratio=2)

    @simulation_test
    def test_tx_ts1_link_lane(self, tb):
        yield tb.phy.ts.valid.eq(1)
        yield tb.phy.ts.link.valid.eq(1)
        yield tb.phy.ts.link.number.eq(0xaa)
        yield tb.phy.ts.lane.valid.eq(1)
        yield tb.phy.ts.lane.number.eq(0x01)
        yield tb.phy.ts.n_fts.eq(0xff)
        yield tb.phy.ts.rate.gen1.eq(1)
        yield
        yield from self.assertReceive(tb, [
            (K(28,5), 0xaa), (0x01, 0xff), (0b0010, 0b0000),
                *[(D(10,2), D(10,2)) for _ in range(5)],
        ])
