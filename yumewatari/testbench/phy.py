from migen import *
from migen.build.generic_platform import *
from migen.build.platforms.versaecp55g import Platform
from migen.genlib.cdc import MultiReg

from ..gateware.serdes import *
from ..gateware.phy import *
from ..gateware.platform.lattice_ecp5 import *


class PHYTestbench(Module):
    def __init__(self, **kwargs):
        self.platform = Platform(**kwargs)
        self.platform.add_extension([
             ("tp0", 0, Pins("X3:5"), IOStandard("LVCMOS33")),
        ])

        self.submodules.serdes = serdes = LatticeECP5PCIeSERDES(self.platform.request("pcie_x1"))
        self.comb += [
            serdes.lane.tx_symbol.eq(0x17C),
            serdes.lane.rx_align.eq(1),
        ]

        self.clock_domains.cd_ref = ClockDomain()
        self.clock_domains.cd_rx = ClockDomain()
        self.clock_domains.cd_tx = ClockDomain()
        self.comb += [
            self.cd_ref.clk.eq(serdes.ref_clk),
            serdes.rx_clk_i.eq(serdes.rx_clk_o),
            self.cd_rx.clk.eq(serdes.rx_clk_i),
            serdes.tx_clk_i.eq(serdes.tx_clk_o),
            self.cd_tx.clk.eq(serdes.tx_clk_i),
        ]

        self.platform.add_platform_command("""FREQUENCY NET "ref_clk" 100 MHz;""")
        self.platform.add_platform_command("""FREQUENCY NET "rx_clk_i" 250 MHz;""")
        self.platform.add_platform_command("""FREQUENCY NET "tx_clk_i" 250 MHz;""")

        self.submodules.phy = phy = ClockDomainsRenamer("rx")(PCIeRXPHY(serdes.lane))

        led_att1 = self.platform.request("user_led")
        led_att2 = self.platform.request("user_led")
        led_sta1 = self.platform.request("user_led")
        led_sta2 = self.platform.request("user_led")
        led_err1 = self.platform.request("user_led")
        led_err2 = self.platform.request("user_led")
        led_err3 = self.platform.request("user_led")
        led_err4 = self.platform.request("user_led")
        self.comb += [
            led_att1.eq(~(0)),
            led_att2.eq(~(0)),
            led_sta1.eq(~(phy.ts.valid)),
            led_sta2.eq(~(0)),
            led_err1.eq(~(~serdes.lane.rx_present)),
            led_err2.eq(~(~serdes.lane.rx_locked)),
            led_err3.eq(~(~serdes.lane.rx_aligned)),
            led_err4.eq(~(phy.ts_error)),
        ]

        tp0 = self.platform.request("tp0")
        self.comb += tp0.eq(phy.fsm.ongoing("TSn-LINK"))

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
