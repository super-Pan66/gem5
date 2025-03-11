// 文件: src/mem/ruby/network/garnet/RouterlessNode.cc

#include "RouterlessNode.hh"

RouterlessNode::RouterlessNode(const Params *p)
    : ClockedObject(p),
      m_enable_adaptive_routing(p->adaptive_routing),
      m_deadlock_threshold(p->deadlock_threshold),
      m_error_correction_mode(p->error_correction) {
      
    // 初始化虚拟通道
    for (int dir = 0; dir < 2; dir++) { // CW 和 CCW 方向
        m_vcs.push_back(std::vector<VirtualChannel>());
        for (int vc = 0; vc < p->vcs_per_dir; vc++) {
            m_vcs[dir].emplace_back(p->vc_depth);
        }
    }
    
    // 注册统计信息
    m_total_forward_latency
        .name(name() + ".total_forward_latency")
        .desc("Total forwarding latency cycles");
    // ...其他统计初始化
}

void RouterlessNode::wakeup() {
    processCredits();
    processFlits();
    scheduleWakeup(Cycles(1)); // 每个周期唤醒
}

void RouterlessNode::processFlits() {
    for (auto& in_link : m_in_links) {
        while (auto flit = in_link->consumeFlit()) {
            // 错误检测
            if (m_error_correction_mode && flit->hasError()) {
                doErrorCorrection(flit);
            }
            
            // 路由计算
            routeCompute(flit);
            
            // VC分配
            int dir = flit->get_outport();
            int vc = allocateVC(dir, flit);
            
            if (vc != -1) {
                m_vcs[dir][vc].insertFlit(flit);
                m_total_forward_latency += curCycle() - flit->get_enqueue_time();
            } else {
                m_packets_dropped++; // 丢包统计
                delete flit;
            }
        }
    }
    
    // 发送处理
    for (int dir = 0; dir < 2; dir++) {
        for (int vc = 0; vc < m_vcs[dir].size(); vc++) {
            if (m_credits[dir].curr_credits > 0 && !m_vcs[dir][vc].isEmpty()) {
                auto flit = m_vcs[dir][vc].peekFlit();
                m_out_links[dir]->sendFlit(flit);
                m_credits[dir].curr_credits--;
                m_vcs[dir][vc].removeFlit();
            }
        }
    }
    
    checkDeadlock();
}

int RouterlessNode::selectOptimalDirection(int dest, const flit* t_flit) {
    // 基础路由表查询
    auto it = m_routing_table.find(dest);
    if (it == m_routing_table.end()) {
        panic("Destination %d not found in routing table!", dest);
    }
    
    // 自适应路由决策
    if (m_enable_adaptive_routing) {
        int cw_latency = estimateCongestion(RouteDirection::CW);
        int ccw_latency = estimateCongestion(RouteDirection::CCW);
        
        return (cw_latency < ccw_latency) ? RouteDirection::CW 
                                         : RouteDirection::CCW;
    }
    
    // 静态路由选择首选项
    return it->second[0]; 
}

void RouterlessNode::checkDeadlock() {
    static int stuck_counter = 0;
    bool is_stuck = true;
    
    // 检查所有VC是否有进展
    for (auto& dir_vcs : m_vcs) {
        for (auto& vc : dir_vcs) {
            if (!vc.isStalled(m_deadlock_threshold)) {
                is_stuck = false;
                break;
            }
        }
    }
    
    if (is_stuck) {
        if (++stuck_counter > m_deadlock_threshold) {
            triggerEmergencyMode();
            stuck_counter = 0;
        }
    } else {
        stuck_counter = 0;
    }
}

void RouterlessNode::triggerEmergencyMode() {
    // 清空所有VC队列
    for (auto& dir_vcs : m_vcs) {
        for (auto& vc : dir_vcs) {
            vc.flush();
        }
    }
    
    // 广播死锁恢复包
    auto alert_flit = new flit(CONTROL_TYPE_DEADLOCK_RECOVERY);
    m_out_links[RouteDirection::CW]->sendFlit(alert_flit);
    m_out_links[RouteDirection::CCW]->sendFlit(alert_flit);
    
    warn("Deadlock detected at node %s, emergency recovery triggered!", name());
}

// 其他方法实现...