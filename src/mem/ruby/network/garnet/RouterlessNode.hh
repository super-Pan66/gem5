// 文件: src/mem/ruby/network/garnet/RouterlessNode.hh

#ifndef __GARNET_ROUTERLESS_NODE_HH__
#define __GARNET_ROUTERLESS_NODE_HH__

#include "mem/ruby/network/garnet/NetworkHeader.hh"
#include "mem/ruby/network/garnet/RoutingUnit.hh"
#include "mem/ruby/network/garnet/VirtualChannel.hh"
#include "params/RouterlessNode.hh"

class RouterlessNode : public ClockedObject {
  public:
    typedef RouterlessNodeParams Params;
    RouterlessNode(const Params *p);
    
    // 初始化拓扑连接
    void init() override;
    
    // 主事件处理循环
    void wakeup() override;
    
    // 添加链路连接
    void addInPort(PortDirection dir, NetworkLink *link, CreditLink *credit_link);
    void addOutPort(PortDirection dir, NetworkLink *link, CreditLink *credit_link,
                    std::vector<NetDest>& routing_table_entry);
                    
    // 统计信息接口
    void collateStats();
    void print(std::ostream& out) const override;
    
  private:
    // 转发引擎核心逻辑
    void processFlits();
    void processCredits();
    void routeCompute(flit *t_flit);
    void doErrorCorrection(flit *t_flit);
    
    // 动态路由选择
    int selectOptimalDirection(int dest, const flit* t_flit);
    
    // 死锁检测与恢复
    void checkDeadlock();
    void triggerEmergencyMode();
    
    // 成员变量
    std::vector<NetworkLink*> m_in_links;  // 输入链路 (CW/CCW)
    std::vector<NetworkLink*> m_out_links; // 输出链路
    
    std::vector<std::vector<VirtualChannel>> m_vcs; // 虚拟通道 [dir][vc]
    std::vector<int> m_vc_round_robin;    // VC轮询指针
    
    // 路由表数据结构 [dest_id][priority] -> direction
    std::unordered_map<int, std::vector<RouteDirection>> m_routing_table; 
    
    // 信用管理系统
    struct CreditInfo {
        int max_credits;
        std::atomic<int> curr_credits;
    };
    std::map<PortDirection, CreditInfo> m_credits;
    
    // 统计信息
    Stats::Scalar m_total_forward_latency;
    Stats::Scalar m_packets_dropped;
    Stats::Histogram m_hop_distribution;
    
    // 配置参数
    bool m_enable_adaptive_routing;
    int m_deadlock_threshold;
    int m_error_correction_mode;
};

#endif // __GARNET_ROUTERLESS_NODE_HH__