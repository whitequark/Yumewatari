from migen import *
from migen.build.generic_platform import *
from migen.build.platforms.versaecp55g import Platform


class Yumewatari(Module):
    def __init__(self, **kwargs):
        self.platform = Platform(**kwargs)
        self.platform.add_extension([
             ("tp0", 0, Pins("X3:5"), IOStandard("LVCMOS33")),
        ])

        refclk = self.platform.request("ext_clk")
        self.clock_domains.cd_refclk = ClockDomain()
        self.comb += self.cd_refclk.clk.eq(refclk.p)

        refcounter = Signal(32)
        self.sync.refclk += refcounter.eq(refcounter + 1)

        rpclk = Signal()
        rxd0  = Signal(8)
        rxk0  = Signal()
        rlol  = Signal()
        rlos  = Signal()

        pcie = self.platform.request("pcie_x1")
        self.specials.dcu0 = Instance("DCUA",
            # DCU — power management
            p_D_MACROPDB="0b1",
            p_D_IB_PWDNB="0b1", # undocumented, seems to be "input buffer power down"
            i_D_FFC_MACROPDB=1,

            # DCU — reset
            i_D_FFC_MACRO_RST=0,
            i_D_FFC_DUAL_RST=0,

            # DCU — clocking
            p_D_REFCK_MODE="0b100", # 25x REFCLK

            # RX CH ­— power management
            p_CH0_RPWDNB="0b1",
            i_CH0_FFC_RXPWDNB=1,

            # RX CH ­— reset
            i_CH0_FFC_RRST=0,
            i_CH0_FFC_LANE_RX_RST=0,

            # RX CH — protocol
            p_CH0_PROTOCOL="PCIE",
            p_CH0_PCIE_MODE="0b1",

            # RX CH ­— input
            i_CH0_HDINP=pcie.rx_p,
            i_CH0_HDINN=pcie.rx_n,

            p_CH0_RTERM_RX="0d22",      # 50 Ohm (wizard value used, does not match datasheet)
            p_CH0_RXIN_CM="0b11",       # CMFB (wizard value used, fixed by Lattice)
            p_CH0_RXTERM_CM="0b11",     # RX Input (wizard value used)
            p_CH0_CTC_BYPASS="0b1",     # bypass CTC FIFO

            # RX CH ­— clocking
            i_CH0_RX_REFCLK=refclk.p,
            o_CH0_FF_RX_PCLK=rpclk,
            i_CH0_FF_RXI_CLK=rpclk,

            p_CH0_CDR_MAX_RATE="2.5",
            p_CH0_PDEN_SEL="0b1",       # phase detector disabled on LOS
            p_CH0_SEL_SD_RX_CLK="0b1",  # FIFO driven by recovered clock
            p_CH0_AUTO_FACQ_EN="0b1",   # unknown
            p_CH0_AUTO_CALIB_EN="0b1",  # unknown

            p_CH0_DCOATDCFG = "0b00",
            p_CH0_DCOATDDLY = "0b00",
            p_CH0_DCOBYPSATD = "0b1",
            p_CH0_DCOCALDIV = "0b010",
            p_CH0_DCOCTLGI = "0b011",
            p_CH0_DCODISBDAVOID = "0b1",
            p_CH0_DCOFLTDAC = "0b00",
            p_CH0_DCOFTNRG = "0b010",
            p_CH0_DCOIOSTUNE = "0b010",
            p_CH0_DCOITUNE = "0b00",
            p_CH0_DCOITUNE4LSB = "0b010",
            p_CH0_DCOIUPDNX2 = "0b1",
            p_CH0_DCONUOFLSB = "0b101",
            p_CH0_DCOSCALEI = "0b01",
            p_CH0_DCOSTARTVAL = "0b010",
            p_CH0_DCOSTEP = "0b11",

            # RX CH — link state machine
            p_CH0_LSM_DISABLE="0b1",

            # RX CH — data
            **{"o_CH0_FF_RX_D_%d" % n: rxd0[n] for n in range(8)},
            o_CH0_FF_RX_D_8=rxk0,

            # RX CH — loss of signal
            o_CH0_FFS_RLOS=rlos,
            p_CH0_RLOS_SEL="0b1",
            p_CH0_RX_LOS_EN="0b1",
            p_CH0_RX_LOS_LVL="0b100", # Lattice "TBD" (wizard value used)
            p_CH0_RX_LOS_CEQ="0b11", # Lattice "TBD" (wizard value used)

            # RX CH — loss of lock
            o_CH0_FFS_RLOL=rlol,

            # TX CH — power management
            p_CH0_TPWDNB="0b0",
        )
        self.dcu0.attr.add(("LOC", "DCU0"))
        self.dcu0.attr.add(("CHAN", "CH0"))

        self.clock_domains.cd_rpclk = ClockDomain()
        self.comb += self.cd_rpclk.clk.eq(rpclk)

        rpclkcounter = Signal(32)
        self.sync.rpclk += rpclkcounter.eq(rpclkcounter + 1)

        led_att1 = self.platform.request("user_led")
        led_att2 = self.platform.request("user_led")
        led_sta1 = self.platform.request("user_led")
        led_sta2 = self.platform.request("user_led")
        led_err1 = self.platform.request("user_led")
        led_err2 = self.platform.request("user_led")
        led_err3 = self.platform.request("user_led")
        led_err4 = self.platform.request("user_led")
        self.comb += [
            led_att1.eq(~(refcounter[25])),
            led_att2.eq(~(rpclkcounter[25])),
            led_sta1.eq(~(0)),
            led_sta1.eq(~(0)),
            led_err1.eq(~(rxk0 & (rxd0 == 0xee))),
            led_err2.eq(~(rlos)),
            led_err3.eq(~(rlol)),
            led_err4.eq(~(0)),
        ]

        tp0 = self.platform.request("tp0")
        self.comb += tp0.eq(rpclkcounter[1])


if __name__ == "__main__":
    design = Yumewatari()
    design.platform.build(design, toolchain_path="/usr/local/diamond/3.10_x64/bin/lin64")
    import subprocess
    subprocess.call(["/home/whitequark/Projects/prjtrellis/tools/bit_to_svf.py",
                     "build/top.bit",
                     "build/top.svf"])
    subprocess.call(["openocd",
                     "-f", "/home/whitequark/Projects/prjtrellis/misc/openocd/ecp5-versa5g.cfg",
                     "-c", "init; svf build/top.svf; exit"])
