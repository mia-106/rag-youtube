"""
状态管理器优化版
管理Agent工作流的状态信息
导入统一的AgentState模型
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import AgentState, AgentStatus

logger = logging.getLogger(__name__)


class StateManager:
    """状态管理器"""

    def __init__(self):
        self.states: Dict[str, AgentState] = {}
        self.max_states = 1000  # 最大保存状态数

    def create_initial_state(self, question: str, session_id: str) -> AgentState:
        """
        创建初始状态

        Args:
            question: 用户问题
            session_id: 会话ID

        Returns:
            初始状态
        """
        state = AgentState(
            question=question, session_id=session_id, status=AgentStatus.PENDING, original_query=question
        )

        self.states[session_id] = state
        self._cleanup_old_states()

        logger.info(f" 创建初始状态: {session_id}")
        return state

    def get_state(self, session_id: str) -> Optional[AgentState]:
        """获取状态"""
        return self.states.get(session_id)

    def update_state(self, session_id: str, updates: Dict[str, Any]) -> Optional[AgentState]:
        """
        更新状态

        Args:
            session_id: 会话ID
            updates: 更新字典

        Returns:
            更新后的状态
        """
        state = self.states.get(session_id)
        if not state:
            logger.warning(f" 状态不存在: {session_id}")
            return None

        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
                logger.debug(f"  更新 {key}: {value}")

        state.updated_at = datetime.now()
        return state

    def transition_state(
        self, session_id: str, new_status: AgentStatus, metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentState]:
        """
        状态转换

        Args:
            session_id: 会话ID
            new_status: 新状态
            metadata: 附加元数据

        Returns:
            转换后的状态
        """
        state = self.states.get(session_id)
        if not state:
            return None

        old_status = state.status
        state.update_status(new_status)

        if metadata:
            state.metadata.update(metadata)

        logger.info(f" 状态转换: {old_status.value}  {new_status.value} ({session_id})")
        return state

    def store_state(self, session_id: str, state: AgentState):
        """存储状态"""
        self.states[session_id] = state
        self._cleanup_old_states()

    def delete_state(self, session_id: str) -> bool:
        """删除状态"""
        if session_id in self.states:
            del self.states[session_id]
            logger.info(f" 删除状态: {session_id}")
            return True
        return False

    def list_active_sessions(self) -> List[str]:
        """列出活跃会话"""
        active_sessions = []
        for session_id, state in self.states.items():
            if not state.is_terminal():
                active_sessions.append(session_id)
        return active_sessions

    def get_session_statistics(self) -> Dict[str, Any]:
        """获取会话统计"""
        total = len(self.states)
        active = len(self.list_active_sessions())
        completed = sum(1 for s in self.states.values() if s.status == AgentStatus.COMPLETED)
        failed = sum(1 for s in self.states.values() if s.status == AgentStatus.FAILED)

        return {
            "total_sessions": total,
            "active_sessions": active,
            "completed_sessions": completed,
            "failed_sessions": failed,
            "success_rate": (completed / total * 100) if total > 0 else 0,
        }

    def export_state(self, session_id: str) -> Optional[str]:
        """导出状态为JSON"""
        state = self.states.get(session_id)
        if not state:
            return None

        return json.dumps(state.to_dict(), ensure_ascii=False, indent=2)

    def import_state(self, session_id: str, state_json: str) -> bool:
        """从JSON导入状态"""
        try:
            data = json.loads(state_json)
            state = AgentState.from_dict(data)
            self.states[session_id] = state
            return True
        except Exception as e:
            logger.error(f" 导入状态失败: {str(e)}")
            return False

    def _cleanup_old_states(self):
        """清理旧状态"""
        if len(self.states) > self.max_states:
            # 删除最旧的非活跃状态
            sorted_states = sorted(self.states.items(), key=lambda x: x[1].updated_at)

            for session_id, state in sorted_states:
                if state.is_terminal():
                    del self.states[session_id]
                    if len(self.states) <= self.max_states:
                        break

    def clear_all(self):
        """清空所有状态"""
        self.states.clear()
        logger.info(" 清空所有状态")


# 全局状态管理器实例
state_manager = StateManager()


def test_state_manager():
    """测试状态管理器"""
    manager = StateManager()

    print(" 测试状态管理器...")

    # 创建初始状态
    state = manager.create_initial_state("什么是Python", "session_001")
    print(f" 创建初始状态: {state.session_id}")
    print(f"  问题: {state.question}")
    print(f"  状态: {state.status.value}")

    # 更新状态
    updated_state = manager.update_state("session_001", {"query_strategy": "关键词搜索", "evaluation_score": 0.85})
    print("\n 更新状态完成")
    print(f"  查询策略: {updated_state.query_strategy}")
    print(f"  评估分数: {updated_state.evaluation_score}")

    # 状态转换
    transitioned_state = manager.transition_state(
        "session_001", AgentStatus.THINKING, {"thinking_start": datetime.now().isoformat()}
    )
    print("\n 状态转换")
    print(f"  新状态: {transitioned_state.status.value}")

    # 添加反思
    state.add_reflection("需要更多关于Python基础的信息")
    state.add_improvement_suggestion("增加Python历史相关内容")
    print("\n 添加反思和建议")
    print(f"  反思次数: {state.reflection_count}")
    print(f"  建议数量: {len(state.improvement_suggestions)}")

    # 统计信息
    stats = manager.get_session_statistics()
    print("\n 统计信息")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # 导出状态
    exported = manager.export_state("session_001")
    print(f"\n 导出状态成功: {len(exported)} 字符")

    print("\n 所有测试通过")


if __name__ == "__main__":
    test_state_manager()
