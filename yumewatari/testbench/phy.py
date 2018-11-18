from migen import *
from migen.build.generic_platform import *
from migen.build.platforms.versaecp55g import Platform
from migen.genlib.io import CRG
from migen.genlib.cdc import MultiReg
from microscope import *

from ..gateware.platform.lattice_ecp5 import *
from ..gateware.serdes import *
from ..gateware.phy import *


class PHYTestbench(Module):
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
        self.platform.add_platform_command("""FREQUENCY NET "serdes_ref_clk" 100 MHz;""")
        self.platform.add_platform_command("""FREQUENCY NET "serdes_rx_clk_o" 125 MHz;""")

        self.submodules.aligner = aligner = \
            ClockDomainsRenamer("rx")(PCIeSERDESAligner(serdes.lane))
        self.submodules.phy = \
            ClockDomainsRenamer("rx")(PCIePHY(aligner))

        led_att1 = self.platform.request("user_led")
        led_att2 = self.platform.request("user_led")
        led_sta1 = self.platform.request("user_led")
        led_sta2 = self.platform.request("user_led")
        led_err1 = self.platform.request("user_led")
        led_err2 = self.platform.request("user_led")
        led_err3 = self.platform.request("user_led")
        led_err4 = self.platform.request("user_led")
        self.comb += [
            led_att1.eq(~(self.phy.rx.ts.link.valid)),
            led_att2.eq(~(self.phy.rx.ts.lane.valid)),
            led_sta1.eq(~(self.phy.rx.ts.valid)),
            led_sta2.eq(~(0)),
            led_err1.eq(~(~serdes.lane.rx_present)),
            led_err2.eq(~(~serdes.lane.rx_locked)),
            led_err3.eq(~(~serdes.lane.rx_aligned)),
            led_err4.eq(~(self.phy.rx.error)),
        ]

        tp0 = self.platform.request("tp0")
        self.comb += tp0.eq(self.phy.rx.ts.link.valid)

        self.phy.finalize()

        self.submodules += CRG(serdes.ref_clk)
        self.submodules += add_probe_single("lane0.rx", "ts",
                                            self.phy.rx.ts.raw_bits(), clock_domain="rx")
        self.submodules += add_probe_single("lane0.rx", "ts.link",
                                            self.phy.rx.ts.link.raw_bits(), clock_domain="rx")
        self.submodules += add_probe_single("lane0.rx", "ts.lane",
                                            self.phy.rx.ts.lane.raw_bits(), clock_domain="rx")
        self.submodules += add_probe_single("lane0.tx", "ts",
                                            self.phy.tx.ts.raw_bits(), clock_domain="rx")
        self.submodules += add_probe_single("lane0", "state",
                                            self.phy.ltssm.state, clock_domain="rx")
        self.submodules += Microscope(self.platform.request("serial"), 99.8e6)

# -------------------------------------------------------------------------------------------------

import subprocess


if __name__ == "__main__":
    toolchain = "diamond"
    if toolchain == "trellis":
        toolchain_path = "/usr/local/share/trellis"
    elif toolchain == "diamond":
        toolchain_path = "/usr/local/diamond/3.10_x64/bin/lin64"

    design = PHYTestbench(toolchain=toolchain)
    design.platform.build(design, toolchain_path=toolchain_path)
    subprocess.call(["/home/whitequark/Projects/prjtrellis/tools/bit_to_svf.py",
                     "build/top.bit",
                     "build/top.svf"])
    subprocess.call(["openocd",
                     "-f", "/home/whitequark/Projects/"
                           "prjtrellis/misc/openocd/ecp5-versa5g.cfg",
                     "-c", "init; svf -quiet build/top.svf; exit"])
