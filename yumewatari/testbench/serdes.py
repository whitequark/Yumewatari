from migen import *
from migen.build.generic_platform import *
from migen.build.platforms.versaecp55g import Platform
from migen.genlib.cdc import MultiReg
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.fsm import FSM

from ..gateware.serdes import *
from ..gateware.phy import K, PCIePHYTX
from ..gateware.align import *
from ..gateware.platform.lattice_ecp5 import *
from ..vendor.pads import *
from ..vendor.uart import *


class SERDESTestbench(Module):
    def __init__(self, capture_depth, **kwargs):
        self.platform = Platform(**kwargs)
        self.platform.add_extension([
             ("tp0", 0, Pins("X3:5"), IOStandard("LVCMOS33")),
        ])

        self.clock_domains.cd_ref = ClockDomain()
        self.clock_domains.cd_rx = ClockDomain()
        self.clock_domains.cd_tx = ClockDomain()

        self.submodules.serdes = serdes = \
            LatticeECP5PCIeSERDES(self.platform.request("pcie_x1"))
        self.submodules.aligner = aligner = \
            ClockDomainsRenamer("rx")(PCIeSERDESAligner(serdes.lane))
        self.comb += [
            self.cd_ref.clk.eq(serdes.ref_clk),
            serdes.rx_clk_i.eq(serdes.rx_clk_o),
            self.cd_rx.clk.eq(serdes.rx_clk_i),
            serdes.tx_clk_i.eq(serdes.tx_clk_o),
            self.cd_tx.clk.eq(serdes.tx_clk_i),
        ]

        self.submodules.tx_phy = ClockDomainsRenamer("tx")(PCIePHYTX(aligner))
        self.comb += [
            self.aligner.rx_align.eq(1),
            self.tx_phy.ts.n_fts.eq(0xff),
            self.tx_phy.ts.rate.gen1.eq(1),
        ]

        with open("top.sdc", "w") as f:
            f.write("define_clock -name {n:serdes_ref_clk} -freq 100.000\n")
            f.write("define_clock -name {n:serdes_tx_clk_o} -freq 150.000\n")
            f.write("define_clock -name {n:serdes_rx_clk_o} -freq 150.000\n")
        self.platform.add_source("top.sdc")
        self.platform.add_platform_command("""FREQUENCY NET "serdes_ref_clk" 100 MHz;""")
        self.platform.add_platform_command("""FREQUENCY NET "serdes_rx_clk_o" 125 MHz;""")
        self.platform.add_platform_command("""FREQUENCY NET "serdes_tx_clk_o" 125 MHz;""")

        refclkcounter = Signal(32)
        self.sync.ref += refclkcounter.eq(refclkcounter + 1)
        rxclkcounter = Signal(32)
        self.sync.rx += rxclkcounter.eq(rxclkcounter + 1)
        txclkcounter = Signal(32)
        self.sync.tx += txclkcounter.eq(txclkcounter + 1)

        led_att1 = self.platform.request("user_led")
        led_att2 = self.platform.request("user_led")
        led_sta1 = self.platform.request("user_led")
        led_sta2 = self.platform.request("user_led")
        led_err1 = self.platform.request("user_led")
        led_err2 = self.platform.request("user_led")
        led_err3 = self.platform.request("user_led")
        led_err4 = self.platform.request("user_led")
        self.comb += [
            led_att1.eq(~(refclkcounter[25])),
            led_att2.eq(~(0)),
            led_sta1.eq(~(rxclkcounter[25])),
            led_sta2.eq(~(txclkcounter[25])),
            led_err1.eq(~(~serdes.lane.rx_present)),
            led_err2.eq(~(~serdes.lane.rx_locked)),
            led_err3.eq(~(~serdes.lane.rx_aligned)),
            led_err4.eq(~(0)),
        ]

        trigger_rx  = Signal()
        trigger_ref = Signal()
        self.specials += MultiReg(trigger_ref, trigger_rx, odomain="rx")

        capture = Signal()
        self.submodules.symbols = symbols = ClockDomainsRenamer({
            "write": "rx", "read": "ref"
        })(
            AsyncFIFO(width=18, depth=capture_depth)
        )
        self.comb += [
            symbols.din.eq(Cat(aligner.rx_symbol)),
            symbols.we.eq(capture)
        ]
        self.sync.rx += [
            If(trigger_rx,
                capture.eq(1)
            ).Elif(~symbols.writable,
                capture.eq(0)
            )
        ]

        uart_pads = Pads(self.platform.request("serial"))
        self.submodules += uart_pads
        self.submodules.uart = uart = ClockDomainsRenamer("ref")(
            UART(uart_pads, bit_cyc=uart_bit_cyc(100e6, 115200)[0])
        )

        self.comb += [
            uart.rx_ack.eq(uart.rx_rdy),
            trigger_ref.eq(uart.rx_rdy)
        ]

        self.submodules.fsm = ClockDomainsRenamer("ref")(FSM(reset_state="WAIT"))
        self.fsm.act("WAIT",
            If(uart.rx_rdy,
                NextState("SYNC-1")
            )
        )
        self.fsm.act("SYNC-1",
            If(uart.tx_rdy,
                uart.tx_ack.eq(1),
                uart.tx_data.eq(0xff),
                NextState("SYNC-2")
            )
        )
        self.fsm.act("SYNC-2",
            If(uart.tx_rdy,
                uart.tx_ack.eq(1),
                uart.tx_data.eq(0xff),
                NextState("BYTE-0")
            )
        )
        self.fsm.act("BYTE-0",
            If(symbols.readable & uart.tx_rdy,
                uart.tx_ack.eq(1),
                uart.tx_data.eq(symbols.dout[16:]),
                NextState("BYTE-1")
            ).Elif(~symbols.readable,
                NextState("WAIT")
            )
        )
        self.fsm.act("BYTE-1",
            If(symbols.readable & uart.tx_rdy,
                uart.tx_ack.eq(1),
                uart.tx_data.eq(symbols.dout[8:]),
                NextState("BYTE-2")
            )
        )
        self.fsm.act("BYTE-2",
            If(symbols.readable & uart.tx_rdy,
                uart.tx_ack.eq(1),
                uart.tx_data.eq(symbols.dout[0:]),
                symbols.re.eq(1),
                NextState("BYTE-0")
            )
        )

        tp0 = self.platform.request("tp0")
        # self.comb += tp0.eq(serdes.rx_clk_o)

# -------------------------------------------------------------------------------------------------

import sys
import serial
import subprocess


CAPTURE_DEPTH = 1024


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        if arg == "build":
            toolchain = "diamond"
            if toolchain == "trellis":
                toolchain_path = "/usr/local/share/trellis"
            elif toolchain == "diamond":
                toolchain_path = "/usr/local/diamond/3.10_x64/bin/lin64"

            design = SERDESTestbench(CAPTURE_DEPTH, toolchain=toolchain)
            design.platform.build(design, toolchain_path=toolchain_path)

        if arg == "load":
            subprocess.call(["/home/whitequark/Projects/prjtrellis/tools/bit_to_svf.py",
                             "build/top.bit",
                             "build/top.svf"])
            subprocess.call(["openocd",
                             "-f", "/home/whitequark/Projects/"
                                   "prjtrellis/misc/openocd/ecp5-versa5g.cfg",
                             "-c", "init; svf -quiet build/top.svf; exit"])

        if arg == "sample":
            port = serial.Serial(port='/dev/ttyUSB1', baudrate=115200)
            port.write(b"\x00")

            while True:
                while True:
                    if port.read(1) == b"\xff": break
                if port.read(1) == b"\xff": break

            for x in range(CAPTURE_DEPTH):
                b2, b1, b0 = port.read(3)
                dword = (b2 << 16) | (b1 << 8) | b0
                for word in (((dword >> 0) & 0x1ff), ((dword >> 9) & 0x1ff)):
                    if word & 0x1ff == 0x1ee:
                        print("KEEEEEEEE", end=" ")
                    else:
                        print("{}{:08b}".format(
                            "K" if word & (1 << 8) else " ",
                            word & 0xff,
                        ), end=" ")
                if x % 4 == 3:
                    print()
