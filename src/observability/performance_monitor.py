"""
性能监控模块
实现系统性能监控和告警
"""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
import logging
import statistics

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """指标数据点"""

    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """告警规则"""

    name: str
    metric_name: str
    condition: str  # '>', '<', '>=', '<=', '=='
    threshold: float
    duration: int  # 持续时间秒
    severity: str  # 'low', 'medium', 'high', 'critical'
    callback: Optional[Callable] = None


@dataclass
class Alert:
    """告警事件"""

    rule_name: str
    metric_name: str
    current_value: float
    threshold: float
    severity: str
    message: str
    timestamp: datetime
    resolved: bool = False


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.alert_rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.monitoring_enabled = True

    def record_metric(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        记录指标

        Args:
            name: 指标名称
            value: 指标值
            tags: 标签
            metadata: 元数据
        """
        try:
            if not self.monitoring_enabled:
                return

            metric_point = MetricPoint(timestamp=datetime.now(), value=value, tags=tags or {}, metadata=metadata or {})

            self.metrics[name].append(metric_point)
            logger.debug(f" 记录指标: {name} = {value}")

            # 检查告警规则
            self._check_alert_rules(name, value)

        except Exception as e:
            logger.error(f" 指标记录失败: {str(e)}")

    def _check_alert_rules(self, metric_name: str, value: float):
        """检查告警规则"""
        for rule in self.alert_rules:
            if rule.metric_name != metric_name:
                continue

            # 检查条件
            triggered = False
            if rule.condition == ">" and value > rule.threshold:
                triggered = True
            elif rule.condition == "<" and value < rule.threshold:
                triggered = True
            elif rule.condition == ">=" and value >= rule.threshold:
                triggered = True
            elif rule.condition == "<=" and value <= rule.threshold:
                triggered = True
            elif rule.condition == "==" and abs(value - rule.threshold) < 1e-6:
                triggered = True

            if triggered:
                self._trigger_alert(rule, value)
            else:
                self._resolve_alert(rule)

    def _trigger_alert(self, rule: AlertRule, value: float):
        """触发告警"""
        alert_key = f"{rule.name}:{rule.metric_name}"

        if alert_key in self.active_alerts:
            # 检查是否已存在告警
            existing_alert = self.active_alerts[alert_key]
            if existing_alert.resolved:
                # 重新触发告警
                pass
            else:
                # 告警已存在不重复触发
                return

        # 创建新告警
        alert = Alert(
            rule_name=rule.name,
            metric_name=rule.metric_name,
            current_value=value,
            threshold=rule.threshold,
            severity=rule.severity,
            message=f"{rule.metric_name} {rule.condition} {rule.threshold}, 当前值: {value}",
            timestamp=datetime.now(),
        )

        self.active_alerts[alert_key] = alert
        self.alert_history.append(alert)

        logger.warning(f" 告警触发: {alert.message}")

        # 调用告警回调
        if rule.callback:
            try:
                rule.callback(alert)
            except Exception as e:
                logger.error(f" 告警回调失败: {str(e)}")

    def _resolve_alert(self, rule: AlertRule):
        """解决告警"""
        alert_key = f"{rule.name}:{rule.metric_name}"

        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            if not alert.resolved:
                alert.resolved = True
                logger.info(f" 告警已解决: {rule.name}")

    def add_alert_rule(
        self,
        name: str,
        metric_name: str,
        condition: str,
        threshold: float,
        severity: str = "medium",
        callback: Optional[Callable] = None,
    ):
        """添加告警规则"""
        rule = AlertRule(
            name=name,
            metric_name=metric_name,
            condition=condition,
            threshold=threshold,
            duration=0,  # 简化实现
            severity=severity,
            callback=callback,
        )

        self.alert_rules.append(rule)
        logger.info(f" 添加告警规则: {name}")

    def get_metric_statistics(self, metric_name: str, duration_minutes: int = 60) -> Dict[str, Any]:
        """
        获取指标统计

        Args:
            metric_name: 指标名称
            duration_minutes: 时间范围分钟

        Returns:
            统计信息字典
        """
        try:
            if metric_name not in self.metrics:
                return {}

            # 获取时间范围内的数据
            cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
            recent_points = [point for point in self.metrics[metric_name] if point.timestamp >= cutoff_time]

            if not recent_points:
                return {"metric_name": metric_name, "count": 0, "duration_minutes": duration_minutes}

            # 计算统计信息
            values = [point.value for point in recent_points]

            stats = {
                "metric_name": metric_name,
                "count": len(values),
                "duration_minutes": duration_minutes,
                "start_time": recent_points[0].timestamp.isoformat(),
                "end_time": recent_points[-1].timestamp.isoformat(),
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
                "latest": values[-1] if values else 0.0,
                "p95": self._calculate_percentile(values, 95),
                "p99": self._calculate_percentile(values, 99),
            }

            return stats

        except Exception as e:
            logger.error(f" 获取指标统计失败: {str(e)}")
            return {}

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)

        if index == int(index):
            return sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(sorted_values) - 1)
            weight = index - lower_index
            return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight

    def get_all_metrics_summary(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """获取所有指标的摘要"""
        try:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "duration_minutes": duration_minutes,
                "total_metrics": len(self.metrics),
                "active_alerts": len([a for a in self.active_alerts.values() if not a.resolved]),
                "metrics": {},
            }

            for metric_name in self.metrics.keys():
                stats = self.get_metric_statistics(metric_name, duration_minutes)
                if stats:
                    summary["metrics"][metric_name] = stats

            return summary

        except Exception as e:
            logger.error(f" 获取指标摘要失败: {str(e)}")
            return {}

    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [alert for alert in self.active_alerts.values() if not alert.resolved]

    def get_all_alerts(self, limit: int = 100) -> List[Alert]:
        """获取所有告警"""
        return self.alert_history[-limit:]

    def clear_metrics(self, metric_name: Optional[str] = None):
        """清空指标数据"""
        if metric_name:
            if metric_name in self.metrics:
                del self.metrics[metric_name]
                logger.info(f" 清空指标: {metric_name}")
        else:
            self.metrics.clear()
            logger.info(" 清空所有指标")

    def clear_alerts(self):
        """清空告警"""
        self.active_alerts.clear()
        self.alert_history.clear()
        logger.info(" 清空告警")

    def export_metrics(self, metric_name: str, format: str = "json") -> str:
        """
        导出指标数据

        Args:
            metric_name: 指标名称
            format: 导出格式 ('json' 或 'csv')

        Returns:
            导出的数据字符串
        """
        try:
            if metric_name not in self.metrics:
                return ""

            points = list(self.metrics[metric_name])

            if format.lower() == "json":
                data = [
                    {
                        "timestamp": point.timestamp.isoformat(),
                        "value": point.value,
                        "tags": point.tags,
                        "metadata": point.metadata,
                    }
                    for point in points
                ]
                return json.dumps(data, ensure_ascii=False, indent=2)
            else:
                # CSV格式
                lines = ["timestamp,value,tags,metadata"]
                for point in points:
                    tags_str = json.dumps(point.tags)
                    metadata_str = json.dumps(point.metadata)
                    lines.append(f"{point.timestamp.isoformat()},{point.value},{tags_str},{metadata_str}")
                return "\n".join(lines)

        except Exception as e:
            logger.error(f" 指标导出失败: {str(e)}")
            return ""

    def set_monitoring_enabled(self, enabled: bool):
        """设置监控开关"""
        self.monitoring_enabled = enabled
        logger.info(f" 监控开关: {'启用' if enabled else '禁用'}")


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()


def test_performance_monitor():
    """测试性能监控器"""
    print(" 测试性能监控器...")

    # 创建监控器
    monitor = PerformanceMonitor()

    print(" 性能监控器创建成功")

    # 测试指标记录
    print("\n 测试指标记录...")
    for i in range(10):
        monitor.record_metric("response_time", 0.5 + i * 0.1)
        monitor.record_metric("cpu_usage", 50 + i * 2)
        monitor.record_metric("memory_usage", 60 + i * 3)

    print(" 指标记录完成")

    # 测试告警规则
    print("\n 测试告警规则...")
    monitor.add_alert_rule(
        name="High Response Time", metric_name="response_time", condition=">", threshold=1.0, severity="high"
    )

    # 触发告警
    monitor.record_metric("response_time", 1.5)

    # 获取告警
    alerts = monitor.get_active_alerts()
    print(f" 活跃告警: {len(alerts)}")
    for alert in alerts:
        print(f"  - {alert.rule_name}: {alert.message}")

    # 测试统计信息
    print("\n 测试统计信息...")
    stats = monitor.get_metric_statistics("response_time")
    print(" 响应时间统计:")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")

    # 测试所有指标摘要
    print("\n 所有指标摘要...")
    summary = monitor.get_all_metrics_summary()
    print(f" 总指标数: {summary['total_metrics']}")
    print(f" 活跃告警: {summary['active_alerts']}")

    print("\n 所有测试完成")


if __name__ == "__main__":
    test_performance_monitor()
