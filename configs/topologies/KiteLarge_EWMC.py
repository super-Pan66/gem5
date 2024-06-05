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

# Creates a generic Mesh assuming an equal number of cache
# and directory controllers.
# XY routing is enforced (using link weights)
# to guarantee deadlock freedom.


class KiteLarge_EWMC(SimpleTopology):
    description = "Mesh_XY"

    def __init__(self, controllers):
        self.nodes = controllers

    # Makes a generic mesh
    # assuming an equal number of cache and directory cntrls

    def makeTopology(
        self, options, full_system, network, IntLink, ExtLink, Router
    ):
        nodes = self.nodes

        print(len(nodes))
        print("nodes:\n", nodes)

        # default values for link latency and router latency.
        # Can be over-ridden on a per link/router basis
        link_latency = options.link_latency
        router_latency = options.router_latency

        # Concentration factor for NoC->NoI routers
        conc_factor = options.concentration_factor
        num_chiplets = options.num_chiplets

        # Compatible only with Garnet 3.0+ only
        # The following assumes square chiplets
        # with equal number of cores per chiplet
        conc_x = int(math.sqrt(conc_factor))
        conc_y = int(math.sqrt(conc_factor))
        chiplets_x = int(math.sqrt(num_chiplets))
        chiplets_y = int(math.sqrt(num_chiplets))
        num_noc_routers = options.num_cpus
        cpus_per_chiplet = int(options.num_cpus / num_chiplets)
        cores_x = int(math.sqrt(cpus_per_chiplet))
        cores_y = int(math.sqrt(cpus_per_chiplet))
        num_noc_rows = options.mesh_rows
        num_noc_columns = int(cpus_per_chiplet / num_noc_rows)
        num_noi_routers = 20
        num_noi_rows = 4
        num_noi_columns = 5
        mem_ctrls = options.num_mem_ctrls

        # One extra router for extra routers, if any
        total_routers = num_noc_routers + num_noi_routers + 1
        total_cpus = options.num_cpus + options.num_mem_ctrls

        # Create the routers in the topology
        routers = [
            Router(router_id=i, latency=router_latency)
            for i in range(total_routers)
        ]
        network.routers = routers

        # link counter to set unique link ids
        link_count = 0

        # Add all but the remainder nodes to the list of nodes to be uniformly
        # distributed across the network.
        network_nodes = nodes

        int_links = []
        ext_links = []

        # Create the mesh links for each chiplet.
        for chiplet_id_y in range(chiplets_y):
            for chiplet_id_x in range(chiplets_x):
                router_base_x = chiplet_id_x * cores_x + (
                    chiplet_id_y * chiplets_x * cpus_per_chiplet
                )
                chiplet_link_width = options.chiplet_width
                ext_link_width = options.chiplet_width

                # Connect each node to the appropriate router
                for core_id_y in range(cores_y):
                    for core_id_x in range(cores_x):
                        core_id = (
                            router_base_x
                            + core_id_x
                            + core_id_y * chiplets_x * cores_x
                        )
                        chiplet_clk_domain = SrcClockDomain(
                            clock=options.chiplet_clock,
                            voltage_domain=VoltageDomain(
                                voltage=options.sys_voltage
                            ),
                        )
                        ext_links.append(
                            ExtLink(
                                link_id=link_count,
                                ext_node=network_nodes[core_id],
                                int_node=routers[core_id],
                                width=ext_link_width,
                                clk_domain=chiplet_clk_domain,
                                latency=link_latency,
                            )
                        )
                        routers[core_id].vcs_per_vnet = options.top_vc
                        print(
                            "ExtLink %d: CPUNode<->Router[%d]"
                            % (link_count, core_id)
                        )
                        link_count += 1

                # Connect each dir to the appropriate router
                for core_id_y in range(cores_y):
                    for core_id_x in range(cores_x):
                        core_id = (
                            router_base_x
                            + core_id_x
                            + core_id_y * chiplets_x * cores_x
                        )
                        chiplet_clk_domain = SrcClockDomain(
                            clock=options.chiplet_clock,
                            voltage_domain=VoltageDomain(
                                voltage=options.sys_voltage
                            ),
                        )
                        ext_links.append(
                            ExtLink(
                                link_id=link_count,
                                ext_node=network_nodes[total_cpus + core_id],
                                int_node=routers[core_id],
                                width=ext_link_width,
                                clk_domain=chiplet_clk_domain,
                                latency=link_latency,
                            )
                        )
                        print("DirNode ", network_nodes[total_cpus + core_id])
                        print(
                            "ExtLink %d: DirNode[%d]<->Router[%d]"
                            % (link_count, total_cpus + core_id, core_id)
                        )
                        link_count += 1

                # East output to West input links (weight = 1)
                for core_id_y in range(cores_y):
                    for core_id_x in range(cores_x - 1):
                        east_out = (
                            router_base_x
                            + core_id_x
                            + (core_id_y * chiplets_x * cores_x)
                        )
                        west_in = (
                            router_base_x
                            + core_id_x
                            + 1
                            + (core_id_y * chiplets_x * cores_x)
                        )
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
                                width=chiplet_link_width,
                                clk_domain=chiplet_clk_domain,
                                weight=1,
                            )
                        )
                        print(
                            "IntLink %d: Router[%d]->Router[%d]"
                            % (link_count, east_out, west_in)
                        )
                        link_count += 1
                        routers[east_out].clk_domain = chiplet_clk_domain
                        routers[west_in].clk_domain = chiplet_clk_domain
                        routers[east_out].width = chiplet_link_width
                        routers[west_in].width = chiplet_link_width

                # West output to East input links (weight = 1)
                for core_id_y in range(cores_y):
                    for core_id_x in range(cores_x - 1):
                        east_in = (
                            router_base_x
                            + core_id_x
                            + (core_id_y * chiplets_x * cores_x)
                        )
                        west_out = (
                            router_base_x
                            + core_id_x
                            + 1
                            + (core_id_y * chiplets_x * cores_x)
                        )
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
                                width=chiplet_link_width,
                                clk_domain=chiplet_clk_domain,
                                weight=1,
                            )
                        )
                        print(
                            "IntLink %d: Router[%d]->Router[%d]"
                            % (link_count, west_out, east_in)
                        )
                        link_count += 1
                        routers[west_out].clk_domain = chiplet_clk_domain
                        routers[east_in].clk_domain = chiplet_clk_domain
                        routers[west_out].width = chiplet_link_width
                        routers[east_in].width = chiplet_link_width

                # North output to South input links (weight = 2)
                for core_id_y in range(cores_y - 1):
                    for core_id_x in range(cores_x):
                        north_out = (
                            router_base_x
                            + core_id_x
                            + (core_id_y * chiplets_x * cores_x)
                        )
                        south_in = (
                            router_base_x
                            + core_id_x
                            + ((core_id_y + 1) * chiplets_x * cores_x)
                        )
                        int_links.append(
                            IntLink(
                                link_id=link_count,
                                src_node=routers[north_out],
                                dst_node=routers[south_in],
                                src_outport="North",
                                dst_inport="South",
                                latency=link_latency,
                                width=chiplet_link_width,
                                clk_domain=chiplet_clk_domain,
                                weight=2,
                            )
                        )
                        print(
                            "IntLink %d: Router[%d]->Router[%d]"
                            % (link_count, north_out, south_in)
                        )
                        link_count += 1
                        routers[north_out].clk_domain = chiplet_clk_domain
                        routers[south_in].clk_domain = chiplet_clk_domain
                        routers[north_out].width = chiplet_link_width
                        routers[south_in].width = chiplet_link_width

                # South output to North input links (weight = 2)
                for core_id_y in range(cores_y - 1):
                    for core_id_x in range(cores_x):
                        north_in = (
                            router_base_x
                            + core_id_x
                            + (core_id_y * chiplets_x * cores_x)
                        )
                        south_out = (
                            router_base_x
                            + core_id_x
                            + ((core_id_y + 1) * chiplets_x * cores_x)
                        )
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
                                width=chiplet_link_width,
                                clk_domain=chiplet_clk_domain,
                                weight=2,
                            )
                        )
                        print(
                            "IntLink %d: Router[%d]->Router[%d]"
                            % (link_count, south_out, north_in)
                        )
                        link_count += 1
                        routers[south_out].clk_domain = chiplet_clk_domain
                        routers[north_in].clk_domain = chiplet_clk_domain
                        routers[south_out].width = chiplet_link_width
                        routers[north_in].width = chiplet_link_width

        # Connect NoC to NoI routers
        # These are the TSV links
        bridge_link_width = options.tsv_width
        for row in range(num_noc_rows * chiplets_y):
            for col in range(num_noc_columns * chiplets_x):
                noc_router = col + (
                    row * num_noc_columns * int(math.sqrt(num_chiplets))
                )
                noi_col = int((col + 1) / conc_x)
                noi_row = int(row / conc_y)
                noi_router = (
                    num_noc_routers + noi_col + (noi_row * num_noi_columns)
                )
                chip_serdes = True
                noi_serdes = True
                if options.chiplet_width == options.tsv_width:
                    chip_serdes = False
                if options.noi_width == options.tsv_width:
                    noi_serdes = False

                bridge_clk_domain = SrcClockDomain(
                    clock=options.tsv_clock,
                    voltage_domain=VoltageDomain(voltage=options.sys_voltage),
                )
                int_links.append(
                    IntLink(
                        link_id=link_count,
                        src_node=routers[noc_router],
                        dst_node=routers[noi_router],
                        src_outport="Down",
                        dst_inport="Up",
                        width=bridge_link_width,
                        src_serdes=chip_serdes,
                        dst_serdes=noi_serdes,
                        clk_domain=bridge_clk_domain,
                        src_cdc=True,
                        latency=link_latency,
                        weight=1,
                    )
                )
                print(
                    "IntLink %d: NoCRouter[%d]->NoIRouter[%d]"
                    % (link_count, noc_router, noi_router)
                )
                link_count += 1

                bridge_clk_domain = SrcClockDomain(
                    clock=options.tsv_clock,
                    voltage_domain=VoltageDomain(voltage=options.sys_voltage),
                )
                int_links.append(
                    IntLink(
                        link_id=link_count,
                        src_node=routers[noi_router],
                        dst_node=routers[noc_router],
                        src_outport="Up",
                        dst_inport="Down",
                        latency=link_latency,
                        width=bridge_link_width,
                        dst_serdes=chip_serdes,
                        src_serdes=noi_serdes,
                        clk_domain=bridge_clk_domain,
                        dst_cdc=True,
                        weight=1,
                    )
                )
                print(
                    "IntLink %d: NoIRouter[%d]->NoCRouter[%d]"
                    % (link_count, noi_router, noc_router)
                )
                link_count += 1
                routers[noi_router].vcs_per_vnet = options.bottom_vc

        # Create NoI
        # East output to West input links (weight = 1)
        noi_link_width = options.noi_width
        noi_router_base = num_noc_routers

        # Black Lattitudes
        for row in range(num_noi_rows):
            noi_router_1 = noi_router_base + (row * num_noi_columns)
            noi_router_2 = noi_router_base + (row * num_noi_columns) + 1
            mc_clk_domain = SrcClockDomain(
                clock=options.mem_clock,
                voltage_domain=VoltageDomain(voltage=options.sys_voltage),
            )
            int_links.append(
                IntLink(
                    link_id=link_count,
                    src_node=routers[noi_router_1],
                    dst_node=routers[noi_router_2],
                    latency=link_latency,
                    width=noi_link_width,
                    clk_domain=mc_clk_domain,
                    weight=2,
                )
            )
            print(
                "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
                % (link_count, noi_router_1, noi_router_2)
            )
            link_count += 1
            int_links.append(
                IntLink(
                    link_id=link_count,
                    src_node=routers[noi_router_2],
                    dst_node=routers[noi_router_1],
                    latency=link_latency,
                    width=noi_link_width,
                    clk_domain=mc_clk_domain,
                    weight=2,
                )
            )
            print(
                "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
                % (link_count, noi_router_2, noi_router_1)
            )
            link_count += 1

            noi_router_1 = (row * num_noi_columns) + noi_router_base + 3
            noi_router_2 = (row * num_noi_columns) + noi_router_base + 4
            mc_clk_domain = SrcClockDomain(
                clock=options.mem_clock,
                voltage_domain=VoltageDomain(voltage=options.sys_voltage),
            )
            int_links.append(
                IntLink(
                    link_id=link_count,
                    src_node=routers[noi_router_1],
                    dst_node=routers[noi_router_2],
                    latency=link_latency,
                    width=noi_link_width,
                    clk_domain=mc_clk_domain,
                    weight=2,
                )
            )
            print(
                "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
                % (link_count, noi_router_1, noi_router_2)
            )
            link_count += 1
            int_links.append(
                IntLink(
                    link_id=link_count,
                    src_node=routers[noi_router_2],
                    dst_node=routers[noi_router_1],
                    latency=link_latency,
                    width=noi_link_width,
                    clk_domain=mc_clk_domain,
                    weight=2,
                )
            )
            print(
                "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
                % (link_count, noi_router_2, noi_router_1)
            )
            link_count += 1

        # Black Meridians
        noi_router_1 = noi_router_base + 0
        noi_router_2 = noi_router_base + num_noi_columns
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )
        link_count += 1

        noi_router_1 = noi_router_base + 2 * num_noi_columns
        noi_router_2 = noi_router_base + 3 * num_noi_columns
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )
        link_count += 1

        noi_router_1 = noi_router_base + 4
        noi_router_2 = noi_router_base + num_noi_columns + 4
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )
        link_count += 1

        noi_router_1 = noi_router_base + (2 * num_noi_columns) + 4
        noi_router_2 = noi_router_base + (3 * num_noi_columns) + 4
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )
        link_count += 1

        # Green 60
        noi_router_1 = noi_router_base + 0
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 1
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (3 * num_noi_columns)
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 1
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + 4
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 3
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (3 * num_noi_columns) + 4
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 3
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        # Green 30
        noi_router_1 = noi_router_base + 0
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 2
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (3 * num_noi_columns)
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 2
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + 4
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 2
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (3 * num_noi_columns) + 4
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 2
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        # Green 30-Mid
        noi_router_1 = noi_router_base + (1 * num_noi_columns)
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 2
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (2 * num_noi_columns)
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 2
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (1 * num_noi_columns) + 4
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 2
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (2 * num_noi_columns) + 4
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 2
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        # Green 30-Center
        noi_router_1 = noi_router_base + (0 * num_noi_columns) + 1
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 3
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (1 * num_noi_columns) + 1
        noi_router_2 = noi_router_base + (0 * num_noi_columns) + 3
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (2 * num_noi_columns) + 1
        noi_router_2 = noi_router_base + (3 * num_noi_columns) + 3
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (3 * num_noi_columns) + 1
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 3
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        # Green Center Spider Down
        noi_router_1 = noi_router_base + (0 * num_noi_columns) + 2
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 0
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (0 * num_noi_columns) + 2
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 1
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (0 * num_noi_columns) + 2
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 3
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (0 * num_noi_columns) + 2
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 4
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        # Green Center Spider Up
        noi_router_1 = noi_router_base + (3 * num_noi_columns) + 2
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 0
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (3 * num_noi_columns) + 2
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 1
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (3 * num_noi_columns) + 2
        noi_router_2 = noi_router_base + (1 * num_noi_columns) + 3
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        noi_router_1 = noi_router_base + (3 * num_noi_columns) + 2
        noi_router_2 = noi_router_base + (2 * num_noi_columns) + 4
        mc_clk_domain = SrcClockDomain(
            clock=options.mem_clock,
            voltage_domain=VoltageDomain(voltage=options.sys_voltage),
        )
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_1],
                dst_node=routers[noi_router_2],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_1, noi_router_2)
        )
        link_count += 1
        int_links.append(
            IntLink(
                link_id=link_count,
                src_node=routers[noi_router_2],
                dst_node=routers[noi_router_1],
                latency=link_latency,
                width=noi_link_width,
                clk_domain=mc_clk_domain,
                weight=2,
            )
        )
        print(
            "IntLink %d: NoIRouter[%d]->NoIRouter[%d]"
            % (link_count, noi_router_2, noi_router_1)
        )

        # Connect MCs
        mcs_per_noi_router = int(mem_ctrls / (2 * num_noi_rows))
        noi_router_base = num_noc_routers
        # East
        for row in range(num_noi_rows):
            noi_router = noi_router_base + (row * num_noi_columns)

            for mc in range(mcs_per_noi_router):
                mc_id = options.num_cpus + (row * mcs_per_noi_router) + mc
                mc_clk_domain = SrcClockDomain(
                    clock=options.mem_clock,
                    voltage_domain=VoltageDomain(voltage=options.sys_voltage),
                )
                ext_links.append(
                    ExtLink(
                        link_id=link_count,
                        ext_node=network_nodes[mc_id],
                        int_node=routers[noi_router],
                        width=noi_link_width,
                        clk_domain=mc_clk_domain,
                        latency=link_latency,
                    )
                )
                print("mc_id", mc_id)
                print("noi_router", noi_router)
                print("MCNode ", network_nodes[mc_id])
                print(
                    "ExtLink %d: MCNode[%d]<->Router[%d]"
                    % (link_count, mc_id, noi_router)
                )
                link_count += 1

                mc_clk_domain = SrcClockDomain(
                    clock=options.mem_clock,
                    voltage_domain=VoltageDomain(voltage=options.sys_voltage),
                )
                ext_links.append(
                    ExtLink(
                        link_id=link_count,
                        ext_node=network_nodes[total_cpus + mc_id],
                        int_node=routers[noi_router],
                        width=noi_link_width,
                        clk_domain=mc_clk_domain,
                        latency=link_latency,
                    )
                )
                print("total_cpus + mc_id", total_cpus + mc_id)
                print("noi_router", noi_router)
                print("DirMcNode ", network_nodes[total_cpus + mc_id])
                print(
                    "ExtLink %d: DirMCNode[%d]<->Router[%d]"
                    % (link_count, total_cpus + mc_id, noi_router)
                )
                link_count += 1

        # West
        for row in range(num_noi_rows):
            noi_router = noi_router_base + ((row + 1) * num_noi_columns) - 1

            for mc in range(mcs_per_noi_router):
                mc_id = (
                    options.num_cpus
                    + num_noi_rows * mcs_per_noi_router
                    + (row * mcs_per_noi_router)
                    + mc
                )
                print("mc_id", mc_id)
                mc_clk_domain = SrcClockDomain(
                    clock=options.mem_clock,
                    voltage_domain=VoltageDomain(voltage=options.sys_voltage),
                )
                ext_links.append(
                    ExtLink(
                        link_id=link_count,
                        ext_node=network_nodes[mc_id],
                        int_node=routers[noi_router],
                        width=noi_link_width,
                        clk_domain=mc_clk_domain,
                        latency=link_latency,
                    )
                )
                print("mc_id", mc_id)
                print("noi_router", noi_router)
                print("MCNode ", network_nodes[mc_id])
                print(
                    "ExtLink %d: MCNode[%d]<->Router[%d]"
                    % (link_count, mc_id, noi_router)
                )
                link_count += 1

                mc_clk_domain = SrcClockDomain(
                    clock=options.mem_clock,
                    voltage_domain=VoltageDomain(voltage=options.sys_voltage),
                )
                ext_links.append(
                    ExtLink(
                        link_id=link_count,
                        ext_node=network_nodes[total_cpus + mc_id],
                        int_node=routers[noi_router],
                        width=noi_link_width,
                        clk_domain=mc_clk_domain,
                        latency=link_latency,
                    )
                )
                print("total_cpus + mc_id", total_cpus + mc_id)
                print("noi_router", noi_router)
                print("DirMcNode ", network_nodes[total_cpus + mc_id])
                print(
                    "ExtLink %d: DirMCNode[%d]<->Router[%d]"
                    % (link_count, total_cpus + mc_id, noi_router)
                )
                link_count += 1

        extra_nodes = len(network_nodes) - 2 * (
            options.num_cpus + options.num_mem_ctrls
        )
        print(extra_nodes)
        for extradir in range(extra_nodes):
            mc_clk_domain = SrcClockDomain(
                clock=options.mem_clock,
                voltage_domain=VoltageDomain(voltage=options.sys_voltage),
            )
            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=network_nodes[(2 * total_cpus) + extradir],
                    int_node=routers[-1],
                    width=noi_link_width,
                    clk_domain=mc_clk_domain,
                    latency=link_latency,
                )
            )
            print(
                "ExtLink %d: ExtraDirNode(%d)<->Router[%d]"
                % (link_count, (2 * total_cpus) + extradir, len(routers) - 1)
            )
            link_count += 1

        network.int_links = int_links
        network.ext_links = ext_links

        # Register nodes with filesystem
        if not full_system and buildEnv["PROTOCOL"] != "Garnet_standalone":
            for i in range(options.num_cpus):
                FileSystemConfig.register_node(
                    [i],
                    int(MemorySize(options.mem_size) / options.num_cpus),
                    i,
                )

    # Register nodes with filesystem
    def registerTopology(self, options):
        for i in range(options.num_cpus):
            FileSystemConfig.register_node(
                [i], MemorySize(options.mem_size) // options.num_cpus, i
            )
