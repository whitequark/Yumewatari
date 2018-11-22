import unittest
from migen import *

from ..gateware.debug import *
from . import simulation_test


class RingLogTestbench(Module):
    def __init__(self):
        self.submodules.dut = RingLog(timestamp_width=8, data_width=8, depth=4)

    def read_out(self):
        yield self.dut.trigger.eq(1)
        yield
        result = []
        for _ in range(self.dut.depth):
            yield self.dut.next.eq(1)
            yield
            result.append(((yield self.dut.time_o), (yield self.dut.data_o)))
            yield self.dut.next.eq(0)
            yield
        yield self.dut.trigger.eq(0)
        yield
        return result


class RingLogTestCase(unittest.TestCase):
    def setUp(self):
        self.tb = RingLogTestbench()

    @simulation_test
    def test_basic(self, tb):
        yield
        yield
        yield
        yield tb.dut.data_i.eq(0x55)
        yield
        yield
        yield
        yield
        yield
        yield tb.dut.data_i.eq(0xaa)
        yield
        self.assertEqual((yield from tb.read_out()), [
            (0, 0),
            (0, 0),
            (4, 0x55),
            (9, 0xaa),
        ])
