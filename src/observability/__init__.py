"""
Observability Module
Comprehensive monitoring, metrics, and alerting system for the YouTube Agentic RAG system

This module provides:
- LangSmith integration for tracing
- Performance metrics collection
- Health checks
- Alerting system
- RAGAS evaluation
"""

from .langsmith_tracker import LangSmithTracker, langsmith_tracker

from .performance_monitor import MetricPoint, AlertRule, Alert, PerformanceMonitor, performance_monitor

from .ragas_evaluator import EvaluationQuestion, EvaluationResult, RAGASEvaluator

from .health_checker import (
    HealthStatus,
    HealthCheck,
    HealthCheckResult,
    DatabaseHealthCheck,
    APIHealthCheck,
    VectorStoreHealthCheck,
    get_health_checker,
)

from .metrics_collector import MetricsCollector, record_metric, get_metrics_collector, Counter, Histogram, Gauge

from .alert_manager import (
    AlertManager,
    NotificationChannel,
    EmailNotification,
    WebhookNotification,
    LogNotification,
    get_alert_manager,
)

from .dashboard import MonitoringDashboard, get_monitoring_dashboard

from .monitoring_initializer import (
    MonitoringInitializer,
    get_monitoring_initializer,
    initialize_monitoring,
    get_monitoring_status,
    monitor_function,
)

__all__ = [
    # LangSmith
    "LangSmithTracker",
    "langsmith_tracker",
    # Performance Monitor
    "MetricPoint",
    "AlertRule",
    "Alert",
    "PerformanceMonitor",
    "performance_monitor",
    # RAGAS
    "EvaluationQuestion",
    "EvaluationResult",
    "RAGASEvaluator",
    # Health Checks
    "HealthStatus",
    "HealthCheck",
    "HealthCheckResult",
    "DatabaseHealthCheck",
    "APIHealthCheck",
    "VectorStoreHealthCheck",
    "get_health_checker",
    # Metrics
    "MetricsCollector",
    "record_metric",
    "get_metrics_collector",
    "Counter",
    "Histogram",
    "Gauge",
    # Alerts
    "AlertManager",
    "NotificationChannel",
    "EmailNotification",
    "WebhookNotification",
    "LogNotification",
    "get_alert_manager",
    # Dashboard
    "MonitoringDashboard",
    "get_monitoring_dashboard",
    # Monitoring Initializer
    "MonitoringInitializer",
    "get_monitoring_initializer",
    "initialize_monitoring",
    "get_monitoring_status",
    "monitor_function",
]

__version__ = "1.0.0"
