import unittest
from migen import *

from ..gateware.align import *
from . import simulation_test


class SymbolSlipTestbench(Module):
    def __init__(self):
        self.submodules.dut = SymbolSlip(symbol_size=8, word_size=4, comma=0xaa)


class SymbolSlipTestCase(unittest.TestCase):
    def setUp(self):
        self.tb = SymbolSlipTestbench()

    @simulation_test
    def test_no_slip(self, tb):
        yield tb.dut.i.eq(0x04030201)
        yield
        self.assertEqual((yield tb.dut.o), 0)
        yield tb.dut.i.eq(0x08070605)
        yield
        self.assertEqual((yield tb.dut.o), 0)
        yield tb.dut.i.eq(0x0c0b0a09)
        yield
        self.assertEqual((yield tb.dut.o), 0x04030201)
        yield tb.dut.i.eq(0)
        yield
        self.assertEqual((yield tb.dut.o), 0x08070605)
        yield
        self.assertEqual((yield tb.dut.o), 0x0c0b0a09)

    @simulation_test
    def test_slip(self, tb):
        yield tb.dut.i.eq(0x0403aa01)
        yield
        yield tb.dut.i.eq(0x08070605)
        yield
        self.assertEqual((yield tb.dut.o), 0)
        yield tb.dut.i.eq(0x0c0b0a09)
        yield
        self.assertEqual((yield tb.dut.o), 0x050403aa)
        yield tb.dut.i.eq(0x000f0e0d)
        yield
        self.assertEqual((yield tb.dut.o), 0x09080706)

    @simulation_test
    def test_slip_2(self, tb):
        yield tb.dut.i.eq(0x0403aa01)
        yield
        yield tb.dut.i.eq(0x080706aa)
        yield
        self.assertEqual((yield tb.dut.o), 0)
        yield tb.dut.i.eq(0x0c0b0a09)
        yield
        self.assertEqual((yield tb.dut.o), 0xaa0403aa)
        yield tb.dut.i.eq(0x000f0e0d)
        yield
        self.assertEqual((yield tb.dut.o), 0x080706aa)
        yield tb.dut.i.eq(0x14131210)
        yield
        self.assertEqual((yield tb.dut.o), 0x0c0b0a09)

    @simulation_test
    def test_enable(self, tb):
        yield tb.dut.en.eq(0)
        yield tb.dut.i.eq(0x0403aa01)
        yield
        yield tb.dut.i.eq(0x08070605)
        yield
        self.assertEqual((yield tb.dut.o), 0)
        yield tb.dut.i.eq(0x0c0b0a09)
        yield
        self.assertEqual((yield tb.dut.o), 0x0403aa01)
        yield tb.dut.i.eq(0x000f0e0d)
        yield
        self.assertEqual((yield tb.dut.o), 0x08070605)
