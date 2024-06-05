# Copyright (c) 2010 Advanced Micro Devices, Inc.
#               2016 Georgia Institute of Technology
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import math

from common import FileSystemConfig
from topologies.BaseTopology import SimpleTopology

from m5.objects import *
from m5.params import *


class My_Mesh(SimpleTopology):
    description = "Mesh_XY"

    def __init__(self, controllers):
        self.nodes = controllers

    def makeTopology(self, options, network, IntLink, ExtLink, Router):
        nodes = self.nodes
        num_cpus = 64
        link_latency = options.link_latency
        link_latency = options.link_latency
        router_latency = options.router_latency

        chiplet_clock = options.chiplet_clock

        l1cache_nodes = []
        l2cache_nodes = []
        dir_nodes = []
        dma_nodes = []
        for node in nodes:
            if node.type == "L1Cache_Controller":
                l1cache_nodes.append(node)
            elif node.type == "L2Cache_Controller":
                l2cache_nodes.append(node)
            elif node.type == "Directory_Controller":
                dir_nodes.append(node)
            elif node.type == "DMA_Controller":
                dma_nodes.append(node)

        # Concentration factor for NoC->NoI routers
        # conc_factor = options.concentration_factor
        # num_chiplets = options.num_chiplets
        # chip_x=int(math.sqrt(num_chiplets))
        # chip_y=chip_x

        conc_factor = 4
        num_chiplets = 4
        chip_x = 4
        chip_y = chip_x

        # num_cpu_per_chip = options.num_cpus // num_chiplets
        # num_noc_rows = options.mesh_rows
        # num_noc_col = num_cpu_per_chip // num_noc_rows

        num_cpu_per_chip = 16
        num_noc_rows = 4
        num_noc_col = 4

        # num_noi_routers = num_cpus // conc_factor
        # noi_col = int(math.sqrt(num_noi_routers))
        # noi_rows = noi_col

        num_noi_routers = num_cpus // conc_factor
        noi_col = int(math.sqrt(num_noi_routers))
        noi_rows = noi_col

        # mem_ctrls = options.num_mem_ctrls
        mem_ctrls = 8

        total_routers = num_cpus + num_noi_routers
        routers = [
            Router(router_id=i, latency=router_latency)
            for i in range(total_routers)
        ]
        network.routers = routers

        link_count = 0

        int_links = []
        ext_links = []

        # for chip_id in range(num_chiplets):
        #     router_base=chip_id*num_cpu_per_chip
        #     for n in range(chip_x*chip_y):
        #         router_id = node + router_base

        #         chiplet_clk_domain = SrcClockDomain(
        #                     clock = chiplet_clock,
        #                     voltage_domain = VoltageDomain(
        #                     voltage = options.sys_voltage))

        #         ext_links.append(
        #             ExtLink(
        #                 link_id=link_count,
        #                 ext_node=n,
        #                 int_node=routers[router_id],
        #                 latency=link_latency,
        #                 clk_domain = chiplet_clk_domain,
        #             )
        #         )

        # l1cache -> router
        for i, n in enumerate(l1cache_nodes):
            chiplet_clk_domain = SrcClockDomain(
                clock=chiplet_clock,
                voltage_domain=VoltageDomain(voltage=options.sys_voltage),
            )

            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=n,
                    int_node=routers[i],
                    latency=link_latency,
                    clk_domain=chiplet_clk_domain,
                )
            )
            print("l1cache", i, "links to Router", i, "via link", link_count)
            link_count += 1

        # l2cache -> router
        for i, n in enumerate(l2cache_nodes):
            chiplet_clk_domain = SrcClockDomain(
                clock=chiplet_clock,
                voltage_domain=VoltageDomain(voltage=options.sys_voltage),
            )

            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=n,
                    int_node=routers[i],
                    latency=link_latency,
                    clk_domain=chiplet_clk_domain,
                )
            )
            print(
                "l2cache", i, "links to Router", i, "via ext-link", link_count
            )
            link_count += 1

        # link inner-chiplet mesh
        for chip_id in range(num_chiplets):
            router_base = num_cpu_per_chip * chip_id
            # w -> e
            for x in range(chip_x):
                for y in range(chip_y):
                    if y + 1 < chip_y:
                        west_out = y + router_base + num_noc_col * x
                        east_in = west_out + 1

                        chiplet_clk_domain = SrcClockDomain(
                            clock=options.chiplet_clock,
                            voltage_domain=VoltageDomain(
                                voltage=options.sys_voltage
                            ),
                        )

                        int_links.append(
                            IntLink(
                                link_id=link_count,
                                src_node=routers[west_out],
                                dst_node=routers[east_in],
                                src_outport="West",
                                dst_inport="East",
                                latency=link_latency,
                                weight=1,
                                clk_domain=chiplet_clk_domain,
                            )
                        )
                        print(
                            "NOC Router",
                            west_out,
                            "links Router",
                            east_in,
                            "via WE int-link",
                            link_count,
                        )
                        link_count += 1
            # e->w
            for x in range(chip_x):
                for y in range(chip_y):
                    if y > 0:
                        west_in = y + router_base + num_noc_col * x - 1
                        east_out = west_in + 1
                        chiplet_clk_domain = SrcClockDomain(
                            clock=options.chiplet_clock,
                            voltage_domain=VoltageDomain(
                                voltage=options.sys_voltage
                            ),
                        )

                        int_links.append(
                            IntLink(
                                link_id=link_count,
                                src_node=routers[east_out],
                                dst_node=routers[west_in],
                                src_outport="East",
                                dst_inport="West",
                                latency=link_latency,
                                weight=1,
                                clk_domain=chiplet_clk_domain,
                            )
                        )
                        print(
                            "NOC Router",
                            east_out,
                            "links Router",
                            west_in,
                            "via EW int-link",
                            link_count,
                        )

                        link_count += 1
            # n -> s
            for y in range(chip_y):
                for x in range(chip_x):
                    if x + 1 < chip_x:
                        north_out = y + router_base + num_noc_col * x
                        south_in = north_out + num_noc_col
                        chiplet_clk_domain = SrcClockDomain(
                            clock=options.chiplet_clock,
                            voltage_domain=VoltageDomain(
                                voltage=options.sys_voltage
                            ),
                        )

                        int_links.append(
                            IntLink(
                                link_id=link_count,
                                src_node=routers[north_out],
                                dst_node=routers[south_in],
                                src_outport="North",
                                dst_inport="South",
                                latency=link_latency,
                                weight=2,
                                clk_domain=chiplet_clk_domain,
                            )
                        )
                        print(
                            "NOC Router",
                            north_out,
                            "links Router",
                            south_in,
                            "via NS int-link",
                            link_count,
                        )
                        link_count += 1
            # s -> n
            for y in range(chip_y):
                for x in range(chip_x):
                    if x > 0:
                        south_out = y + router_base + num_noc_rows * x
                        north_in = south_out - num_noc_col
                        chiplet_clk_domain = SrcClockDomain(
                            clock=options.chiplet_clock,
                            voltage_domain=VoltageDomain(
                                voltage=options.sys_voltage
                            ),
                        )

                        int_links.append(
                            IntLink(
                                link_id=link_count,
                                src_node=routers[south_out],
                                dst_node=routers[north_in],
                                src_outport="South",
                                dst_inport="North",
                                latency=link_latency,
                                weight=2,
                                clk_domain=chiplet_clk_domain,
                            )
                        )
                        print(
                            "NOC Router",
                            south_out,
                            "links Router",
                            north_in,
                            "via SN int-link",
                            link_count,
                        )
                        link_count += 1

        # link noi mesh
        noi_base = num_cpus
        for x in range(noi_rows):
            for y in range(noi_col):
                # noi w -> e
                if y + 1 < noi_col:
                    west_out = y + x * noi_col + noi_base
                    east_in = west_out + 1
                    int_links.append(
                        IntLink(
                            link_id=link_count,
                            src_node=routers[west_out],
                            dst_node=routers[east_in],
                            src_outport="West",
                            dst_inport="East",
                            latency=link_latency,
                            weight=1,
                        )
                    )
                    print(
                        "NOI Router",
                        west_out,
                        "links Router",
                        east_in,
                        "via WE int-link",
                        link_count,
                    )
                    link_count += 1
        # noi  e -> w
        for x in range(noi_rows):
            for y in range(noi_col):
                if y > 0:
                    east_out = y + x * noi_col + noi_base
                    west_in = east_out - 1
                    int_links.append(
                        IntLink(
                            link_id=link_count,
                            src_node=routers[east_out],
                            dst_node=routers[west_in],
                            src_outport="East",
                            dst_inport="West",
                            latency=link_latency,
                            weight=1,
                        )
                    )
                    print(
                        "NOI Router",
                        east_out,
                        "links Router",
                        west_in,
                        "via EW int-link",
                        link_count,
                    )
                    link_count += 1

        # noi n -> s
        for x in range(noi_rows):
            for y in range(noi_col):
                if x + 1 < noi_rows:
                    north_out = y + x * noi_col + noi_base
                    south_in = north_out + noi_col
                    int_links.append(
                        IntLink(
                            link_id=link_count,
                            src_node=routers[north_out],
                            dst_node=routers[south_in],
                            src_outport="North",
                            dst_inport="South",
                            latency=link_latency,
                            weight=2,
                        )
                    )
                    print(
                        "NOI Router",
                        north_out,
                        "links Router",
                        south_in,
                        "via NS int-link",
                        link_count,
                    )
                    link_count += 1

                # s->n
        for x in range(noi_rows):
            for y in range(noi_col):
                if x > 0:
                    south_out = y + x * noi_col + noi_base
                    north_in = south_out - noi_col
                    int_links.append(
                        IntLink(
                            link_id=link_count,
                            src_node=routers[south_out],
                            dst_node=routers[north_in],
                            src_outport="South",
                            dst_inport="North",
                            latency=link_latency,
                            weight=2,
                        )
                    )
                    print(
                        "NOI Router",
                        south_out,
                        "links Router",
                        north_in,
                        "via SN int-link",
                        link_count,
                    )
                    link_count += 1
        # link noc -> noi
        # for i in range(num_noi_routers):
        #     up = i * conc_factor
        #     down = i + noi_base
        #     int_links.append(
        #         IntLink(
        #             link_id=link_count,
        #             src_node=routers[up],
        #             dst_node=routers[down],
        #             src_outport="Up",
        #             dst_inport="Down",
        #             latency=link_latency,
        #             weight=1,

        #         )
        #     )
        #     print("NOC Router",up,"links NOI Router",down,"via U-D int-link",link_count)
        #     link_count+=1
        #     int_links.append(
        #                 IntLink(
        #                     link_id=link_count,
        #                     src_node=routers[down],
        #                     dst_node=routers[up],
        #                     src_outport="Down",
        #                     dst_inport="Up",
        #                     latency=link_latency,
        #                     weight=2,

        #                 )
        #             )
        #     print("NOI Router",down,"links NoC Router",up,"via D-U int-link",link_count)
        #     link_count+=1
        def connectIntLink(r1, r2, p1, p2, w, link_latency=1):
            print(
                "Router",
                r1,
                "links Router",
                r2,
                " via ",
                p1,
                "-",
                p2,
                "int-link",
                link_count,
            )
            return IntLink(
                link_id=link_count,
                src_node=routers[r1],
                dst_node=routers[r2],
                src_outport=p1,
                dst_inport=p2,
                latency=link_latency,
                weight=w,
            )

        int_links.append(connectIntLink(1, 0 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(0 + noi_base, 1, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(2, 1 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(1 + noi_base, 2, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(17, 2 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(2 + noi_base, 17, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(18, 3 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(3 + noi_base, 18, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(13, 4 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(4 + noi_base, 13, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(14, 5 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(5 + noi_base, 14, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(29, 6 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(6 + noi_base, 29, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(30, 7 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(7 + noi_base, 30, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(33, 8 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(8 + noi_base, 33, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(34, 9 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(9 + noi_base, 34, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(49, 10 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(10 + noi_base, 49, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(50, 11 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(11 + noi_base, 50, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(45, 12 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(12 + noi_base, 45, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(46, 13 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(13 + noi_base, 46, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(61, 14 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(14 + noi_base, 61, "Down", "Up", 2))
        link_count += 1

        int_links.append(connectIntLink(62, 15 + noi_base, "Up", "Down", 2))
        link_count += 1
        int_links.append(connectIntLink(15 + noi_base, 62, "Down", "Up", 2))
        link_count += 1

        # link dir to noi
        mem_conc = num_noi_routers // mem_ctrls
        for i in range(mem_ctrls):
            n = dir_nodes[i]
            dir_router_id = i + noi_base + (8 if i > 3 else 0)
            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=n,
                    int_node=routers[dir_router_id],
                    latency=link_latency,
                )
            )
            print(
                "Dir-Ctrl",
                i,
                "links to NoI Router",
                dir_router_id,
                "via ext_link",
                link_count,
            )
            link_count += 1

        network.ext_links = ext_links
        network.int_links = int_links

    def registerTopology(self, options):
        for i in range(options.num_cpus):
            FileSystemConfig.register_node(
                [i], MemorySize(options.mem_size) // options.num_cpus, i
            )
