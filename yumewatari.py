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

        rpclk = Signal()  # recovered word clock
        rxd0  = Signal(8) # receive data
        rxk0  = Signal()  # receive comma
        rxde0 = Signal()  # disparity error
        rxce0 = Signal()  # coding violation error
        rlos  = Signal()  # loss of signal
        rlol  = Signal()  # loss of lock
        rlsm  = Signal()  # link state machine up

        tpclk = Signal()  # generated word clock
        txd0  = Signal(8) # transmit data
        txk0  = Signal()  # transmit comma
        txfd  = Signal()  # force disparity
        txds  = Signal()  # disparity
        tlol  = Signal()  # loss of lock

        pcie = self.platform.request("pcie_x1")
        self.specials.dcu0 = Instance("DCUA",
            # DCU — power management
            p_D_MACROPDB="0b1",
            p_D_IB_PWDNB="0b1",             # undocumented, seems to be "input buffer power down"
            p_D_TXPLL_PWDNB="0b1",
            i_D_FFC_MACROPDB=1,

            # DCU — reset
            i_D_FFC_MACRO_RST=0,
            i_D_FFC_DUAL_RST=0,
            i_D_FFC_TRST=0,

            # DCU — clocking
            i_D_REFCLKI=refclk.p,
            o_D_FFS_PLOL=tlol,
            p_D_REFCK_MODE="0b100",         # 25x REFCLK
            p_D_TX_MAX_RATE="2.5",          # 2.5 Gbps
            p_D_TX_VCO_CK_DIV="0b000",      # DIV/1
            p_D_BITCLK_LOCAL_EN="0b1",      # undocumented (PCIe sample code used)

            # DCU ­— unknown
            p_D_CMUSETBIASI="0b00",         # begin undocumented (PCIe sample code used)
            p_D_CMUSETI4CPP="0d4",
            p_D_CMUSETI4CPZ="0d3",
            p_D_CMUSETI4VCO="0b00",
            p_D_CMUSETICP4P="0b01",
            p_D_CMUSETICP4Z="0b101",
            p_D_CMUSETINITVCT="0b00",
            p_D_CMUSETISCL4VCO="0b000",
            p_D_CMUSETP1GM="0b000",
            p_D_CMUSETP2AGM="0b000",
            p_D_CMUSETZGM="0b100",
            p_D_SETIRPOLY_AUX="0b10",
            p_D_SETICONST_AUX="0b01",
            p_D_SETIRPOLY_CH="0b10",
            p_D_SETICONST_CH="0b10",
            p_D_SETPLLRC="0d1",
            p_D_RG_EN="0b1",
            p_D_RG_SET="0b00",              # end undocumented

            # DCU — FIFOs
            p_D_LOW_MARK="0d4",
            p_D_HIGH_MARK="0d12",

            # CH0 — protocol
            p_CH0_PROTOCOL="PCIE",
            p_CH0_PCIE_MODE="0b1",

            # RX CH ­— power management
            p_CH0_RPWDNB="0b1",
            i_CH0_FFC_RXPWDNB=1,

            # RX CH ­— reset
            i_CH0_FFC_RRST=0,
            i_CH0_FFC_LANE_RX_RST=0,

            # RX CH ­— input
            i_CH0_HDINP=pcie.rx_p,
            i_CH0_HDINN=pcie.rx_n,

            p_CH0_RTERM_RX="0d22",          # 50 Ohm (wizard value used, does not match datasheet)
            p_CH0_RXIN_CM="0b11",           # CMFB (wizard value used)
            p_CH0_RXTERM_CM="0b11",         # RX Input (wizard value used)
            p_CH0_CTC_BYPASS="0b1",         # bypass CTC FIFO

            # RX CH ­— clocking
            i_CH0_RX_REFCLK=refclk.p,
            o_CH0_FF_RX_PCLK=rpclk,
            i_CH0_FF_RXI_CLK=rpclk,

            p_CH0_CDR_MAX_RATE="2.5",       # 2.5 Gbps
            p_CH0_RX_DCO_CK_DIV="0b000",    # DIV/1
            p_CH0_PDEN_SEL="0b1",           # phase detector disabled on LOS
            p_CH0_SEL_SD_RX_CLK="0b1",      # FIFO driven by recovered clock
            p_CH0_AUTO_FACQ_EN="0b1",       # undocumented (wizard value used)
            p_CH0_AUTO_CALIB_EN="0b1",      # undocumented (wizard value used)

            p_CH0_DCOATDCFG="0b00",         # begin undocumented (PCIe sample code used)
            p_CH0_DCOATDDLY="0b00",
            p_CH0_DCOBYPSATD="0b1",
            p_CH0_DCOCALDIV="0b010",
            p_CH0_DCOCTLGI="0b011",
            p_CH0_DCODISBDAVOID="0b1",
            p_CH0_DCOFLTDAC="0b00",
            p_CH0_DCOFTNRG="0b010",
            p_CH0_DCOIOSTUNE="0b010",
            p_CH0_DCOITUNE="0b00",
            p_CH0_DCOITUNE4LSB="0b010",
            p_CH0_DCOIUPDNX2="0b1",
            p_CH0_DCONUOFLSB="0b101",
            p_CH0_DCOSCALEI="0b01",
            p_CH0_DCOSTARTVAL="0b010",
            p_CH0_DCOSTEP="0b11",           # end undocumented

            # RX CH — link state machine
            o_CH0_FFS_LS_SYNC_STATUS=rlsm,
            p_CH0_LSM_DISABLE="0b1",
            p_CH0_ENABLE_CG_ALIGN="0b1",    # enable comma aligner
            p_CH0_UDF_COMMA_MASK="0x3ff",
            p_CH0_UDF_COMMA_A="0x283",      # ???
            p_CH0_UDF_COMMA_B="0x17C",      # K28.3 IDLE

            p_CH0_MIN_IPG_CNT="0b11",       # minimum interpacket gap of 4
            p_CH0_MATCH_4_ENABLE="0b1",     # 4 character skip matching
            p_CH0_CC_MATCH_1="0x1BC",       # K28.5 K
            p_CH0_CC_MATCH_2="0x11C",       # K28.0 SKIP
            p_CH0_CC_MATCH_3="0x11C",       # K28.0 SKIP
            p_CH0_CC_MATCH_4="0x11C",       # K28.0 SKIP

            # RX CH — loss of signal
            o_CH0_FFS_RLOS=rlos,
            p_CH0_RLOS_SEL="0b1",
            p_CH0_RX_LOS_EN="0b1",
            p_CH0_RX_LOS_LVL="0b100",       # Lattice "TBD" (wizard value used)
            p_CH0_RX_LOS_CEQ="0b11",        # Lattice "TBD" (wizard value used)

            # RX CH — loss of lock
            o_CH0_FFS_RLOL=rlol,

            # RX CH — data
            **{"o_CH0_FF_RX_D_%d" % (0 + n): rxd0[n] for n in range(8)},
            o_CH0_FF_RX_D_8=rxk0,
            o_CH0_FF_RX_D_9=rxde0,
            o_CH0_FF_RX_D_10=rxce0,

            # TX CH — power management
            p_CH0_TPWDNB="0b1",
            i_CH0_FFC_TXPWDNB=1,

            # TX CH ­— reset
            i_CH0_FFC_LANE_TX_RST=0,

            # TX CH ­— output
            i_CH0_HDOUTP=pcie.tx_p,
            i_CH0_HDOUTN=pcie.tx_n,

            p_CH0_TXAMPLITUDE="0d1000",     # 1000 mV

            p_CH0_TDRV_SLICE0_CUR="0b011",  # 400 uA
            p_CH0_TDRV_SLICE0_SEL="0b01",   # main data
            p_CH0_TDRV_SLICE1_CUR="0b000",  # 100 uA
            p_CH0_TDRV_SLICE1_SEL="0b00",   # power down
            p_CH0_TDRV_SLICE2_CUR="0b11",   # 3200 uA
            p_CH0_TDRV_SLICE2_SEL="0b01",   # main data
            p_CH0_TDRV_SLICE3_CUR="0b11",   # 3200 uA
            p_CH0_TDRV_SLICE3_SEL="0b01",   # main data
            p_CH0_TDRV_SLICE4_CUR="0b11",   # 3200 uA
            p_CH0_TDRV_SLICE4_SEL="0b01",   # main data
            p_CH0_TDRV_SLICE5_CUR="0b00",   # 800 uA
            p_CH0_TDRV_SLICE5_SEL="0b00",   # power down

            # TX CH ­— clocking
            o_CH0_FF_TX_PCLK=tpclk,
            i_CH0_FF_TXI_CLK=tpclk,

            # TX CH — data
            **{"o_CH0_FF_TX_D_%d" % n: txd0[n] for n in range(8)},
            o_CH0_FF_TX_D_8=txk0,
            o_CH0_FF_TX_D_9=txfd,
            o_CH0_FF_TX_D_10=txds,
        )
        self.dcu0.attr.add(("LOC", "DCU0"))
        self.dcu0.attr.add(("CHAN", "CH0"))

        self.comb += [
            txd0.eq(0x7C),
            txk0.eq(1),
        ]

        self.clock_domains.cd_rx = ClockDomain()
        self.clock_domains.cd_tx = ClockDomain()
        self.comb += [
            self.cd_rx.clk.eq(rpclk),
            self.cd_tx.clk.eq(tpclk),
        ]

        rpclkcounter = Signal(32)
        self.sync.rx += rpclkcounter.eq(rpclkcounter + 1)
        tpclkcounter = Signal(32)
        self.sync.tx += tpclkcounter.eq(tpclkcounter + 1)

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
            led_att2.eq(~(rlsm)),
            led_sta1.eq(~(rpclkcounter[25])),
            led_sta2.eq(~(tpclkcounter[25])),
            led_err1.eq(~(rlos)),
            led_err2.eq(~(rlol | tlol)),
            led_err3.eq(~(rxde0)),
            led_err4.eq(~(rxce0)),
        ]

        tp0 = self.platform.request("tp0")
        self.comb += tp0.eq(rxde0)


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
