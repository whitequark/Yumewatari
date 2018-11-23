from migen import *
from migen.build.generic_platform import *
from migen.build.platforms.versaecp55g import Platform
from migen.genlib.io import CRG
from migen.genlib.cdc import MultiReg
from microscope import *

from ..gateware.platform.lattice_ecp5 import *
from ..gateware.serdes import *
from ..gateware.phy import *
from ..vendor.pads import *
from ..vendor.uart import *


class LTSSMTestbench(Module):
    def __init__(self, **kwargs):
        self.platform = Platform(**kwargs)
        self.platform.add_extension([
             ("tp0", 0, Pins("X3:5"), IOStandard("LVCMOS33")),
        ])

        self.clock_domains.cd_serdes = ClockDomain()
        self.submodules.serdes  = serdes  = \
            LatticeECP5PCIeSERDES(self.platform.request("pcie_x1"))
        self.comb += [
            self.cd_serdes.clk.eq(serdes.rx_clk_o),
            serdes.rx_clk_i.eq(self.cd_serdes.clk),
            serdes.tx_clk_i.eq(self.cd_serdes.clk),
        ]

        with open("top.sdc", "w") as f:
            f.write("define_clock -name {n:serdes_ref_clk} -freq 100.000\n")
            f.write("define_clock -name {n:serdes_rx_clk_o} -freq 150.000\n")
        self.platform.add_source("top.sdc")
        # self.platform.add_platform_command("""FREQUENCY NET "serdes_ref_clk" 100 MHz;""")
        # self.platform.add_platform_command("""FREQUENCY NET "serdes_rx_clk_o" 125 MHz;""")

        self.submodules.aligner = aligner = \
            ClockDomainsRenamer("rx")(PCIeSERDESAligner(serdes.lane))
        self.submodules.phy = phy = \
            ClockDomainsRenamer("rx")(PCIePHY(aligner, ms_cyc=125000))

        led_att1 = self.platform.request("user_led")
        led_att2 = self.platform.request("user_led")
        led_sta1 = self.platform.request("user_led")
        led_sta2 = self.platform.request("user_led")
        led_err1 = self.platform.request("user_led")
        led_err2 = self.platform.request("user_led")
        led_err3 = self.platform.request("user_led")
        led_err4 = self.platform.request("user_led")
        self.comb += [
            led_att1.eq(~(phy.rx.ts.link.valid)),
            led_att2.eq(~(phy.rx.ts.lane.valid)),
            led_sta1.eq(~(phy.rx.ts.valid)),
            led_sta2.eq(~(0)),
            led_err1.eq(~(~serdes.lane.rx_present)),
            led_err2.eq(~(~serdes.lane.rx_locked)),
            led_err3.eq(~(~serdes.lane.rx_aligned)),
            led_err4.eq(~(phy.rx.error)),
        ]

        tp0 = self.platform.request("tp0")
        self.comb += tp0.eq(phy.rx.ts.link.valid)

        uart_pads = Pads(self.platform.request("serial"))
        self.submodules += uart_pads
        self.submodules.uart = uart = ClockDomainsRenamer("rx")(
            UART(uart_pads, bit_cyc=uart_bit_cyc(125e6, 115200)[0])
        )

        self.comb += [
            uart.rx_ack.eq(uart.rx_rdy),
        ]

        index  = Signal(max=phy.ltssm_log.depth)
        offset = Signal(8)
        size   = Signal(16)
        entry  = Signal(phy.ltssm_log.width)
        self.comb += [
            size.eq(phy.ltssm_log.width * phy.ltssm_log.depth // 8),
            entry.eq(Cat(phy.ltssm_log.data_o, phy.ltssm_log.time_o)),
        ]

        self.submodules.uart_fsm = ClockDomainsRenamer("rx")(FSM())
        self.uart_fsm.act("WAIT",
            NextValue(uart.tx_ack, 0),
            If(uart.rx_rdy,
                NextValue(phy.ltssm_log.trigger, 1),
                NextValue(offset, 1),
                NextState("WIDTH")
            )
        )
        self.uart_fsm.act("WIDTH",
            NextValue(uart.tx_ack, 0),
            If(uart.tx_rdy & ~uart.tx_ack,
                NextValue(uart.tx_data, size.part(offset << 3, 8)),
                NextValue(uart.tx_ack, 1),
                If(offset == 0,
                    NextValue(offset, phy.ltssm_log.width // 8 - 1),
                    NextValue(index,  phy.ltssm_log.depth - 1),
                    NextState("DATA")
                ).Else(
                    NextValue(offset, offset - 1)
                )
            )
        )
        self.uart_fsm.act("DATA",
            NextValue(uart.tx_ack, 0),
            If(uart.tx_rdy & ~uart.tx_ack,
                NextValue(uart.tx_data, entry.part(offset << 3, 8)),
                NextValue(uart.tx_ack, 1),
                If(offset == 0,
                    phy.ltssm_log.next.eq(1),
                    NextValue(offset, phy.ltssm_log.width // 8 - 1),
                    If(index == 0,
                        NextValue(phy.ltssm_log.trigger, 0),
                        NextState("WAIT")
                    ).Else(
                        NextValue(index, index - 1)
                    )
                ).Else(
                    NextValue(offset, offset - 1)
                )
            )
        )

# -------------------------------------------------------------------------------------------------

import sys
import serial
import struct
import subprocess


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        if arg == "build":
            toolchain = "diamond"
            if toolchain == "trellis":
                toolchain_path = "/usr/local/share/trellis"
            elif toolchain == "diamond":
                toolchain_path = "/usr/local/diamond/3.10_x64/bin/lin64"

            design = LTSSMTestbench(toolchain=toolchain)
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
            design = LTSSMTestbench()
            design.finalize()

            port = serial.Serial(port='/dev/ttyUSB1', baudrate=115200)
            port.write(b"\x00")
            length, = struct.unpack(">H", port.read(2))
            data = port.read(length)

            offset = 0
            start  = None
            while offset < len(data):
                time, state = struct.unpack_from(">LB", data, offset)
                offset += struct.calcsize(">LB")

                if start is not None:
                    delta = time - start
                else:
                    delta = time

                print("%+10d cyc (%+10d us): %s" %
                      (delta, delta / 125, design.phy.ltssm.decoding[state]))

                start = time

