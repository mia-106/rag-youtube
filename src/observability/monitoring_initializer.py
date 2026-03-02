"""
Monitoring System Initialization
Initializes and configures the monitoring and observability system
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.observability import (
    DatabaseHealthCheck,
    APIHealthCheck,
    VectorStoreHealthCheck,
    SystemHealthCheck,
    LogNotification,
    get_health_checker,
    get_metrics_collector,
    get_alert_manager,
    get_monitoring_dashboard,
    record_metric,
)

logger = logging.getLogger(__name__)


class MonitoringInitializer:
    """Monitor initialization and configuration"""

    def __init__(self):
        self.initialized = False
        self.config = {}

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Initialize monitoring system

        Args:
            config: Configuration dictionary with monitoring settings

        Returns:
            Initialization status and configuration
        """
        if self.initialized:
            return {"status": "already_initialized", "config": self.config}

        logger.info(" Initializing monitoring system...")

        self.config = config or self._get_default_config()

        try:
            # Initialize health checker
            await self._init_health_checks()

            # Initialize metrics collector
            await self._init_metrics()

            # Initialize alert manager
            await self._init_alerts()

            # Initialize dashboard
            await self._init_dashboard()

            # Run initial health check
            await self._run_initial_health_check()

            self.initialized = True

            logger.info(" Monitoring system initialized successfully")

            return {"status": "success", "config": self.config, "timestamp": datetime.now().isoformat()}

        except Exception as e:
            logger.error(f" Failed to initialize monitoring: {str(e)}")
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default monitoring configuration"""
        return {
            "monitoring_enabled": True,
            "health_check_interval": 60,  # seconds
            "metrics_retention_hours": 24,
            "alert_rules": {
                "response_time_warning": 1.0,  # seconds
                "response_time_critical": 5.0,  # seconds
                "cpu_usage_warning": 80.0,  # percent
                "cpu_usage_critical": 95.0,  # percent
                "memory_usage_warning": 85.0,  # percent
                "memory_usage_critical": 95.0,  # percent
            },
            "notifications": {
                "log_enabled": True,
                "email_enabled": False,
                "webhook_enabled": False,
                "slack_enabled": False,
            },
        }

    async def _init_health_checks(self):
        """Initialize health checks"""
        logger.info(" Initializing health checks...")

        health_checker = get_health_checker()

        # Add system health check
        health_checker.add_check(SystemHealthCheck())

        # Add database health check if config available
        db_config = self.config.get("database", {})
        if db_config.get("url"):
            health_checker.add_check(
                DatabaseHealthCheck(connection_string=db_config["url"], timeout=db_config.get("timeout", 5.0))
            )

        # Add API health checks
        api_configs = self.config.get("apis", {})
        for api_name, api_config in api_configs.items():
            if api_config.get("endpoint"):
                health_checker.add_check(
                    APIHealthCheck(
                        api_name=api_name, endpoint=api_config["endpoint"], timeout=api_config.get("timeout", 5.0)
                    )
                )

        # Add vector store health check
        vector_config = self.config.get("vector_store", {})
        if vector_config.get("type"):
            health_checker.add_check(
                VectorStoreHealthCheck(vector_store_type=vector_config["type"], config=vector_config)
            )

        logger.info(f" Health checks initialized: {len(health_checker.checks)} checks")

    async def _init_metrics(self):
        """Initialize metrics collection"""
        logger.info(" Initializing metrics collection...")

        metrics_collector = get_metrics_collector()

        # Create standard metrics
        await metrics_collector.create_counter("request_count", description="Total number of requests")

        await metrics_collector.create_counter("error_count", description="Total number of errors")

        await metrics_collector.create_gauge("active_connections", description="Number of active connections")

        await metrics_collector.create_histogram(
            "response_time", description="Request response time in seconds", buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        await metrics_collector.create_histogram("query_time", description="Database query time in seconds")

        logger.info(" Metrics collection initialized")

    async def _init_alerts(self):
        """Initialize alert manager"""
        logger.info(" Initializing alert manager...")

        alert_manager = get_alert_manager()

        # Add log notification (always enabled)
        # Email, webhook, and Slack can be configured via config
        if self.config.get("notifications", {}).get("log_enabled", True):
            alert_manager.add_channel(LogNotification())

        # Add alert rules
        alert_rules = self.config.get("alert_rules", {})

        # Response time alerts
        if alert_rules.get("response_time_warning"):
            # These would be triggered by the performance monitor
            pass

        logger.info(f" Alert manager initialized with {len(alert_manager.channels)} channels")

    async def _init_dashboard(self):
        """Initialize monitoring dashboard"""
        logger.info(" Initializing monitoring dashboard...")

        metrics_collector = get_metrics_collector()
        health_checker = get_health_checker()
        alert_manager = get_alert_manager()

        dashboard = get_monitoring_dashboard(metrics_collector, health_checker, alert_manager)

        # Add default widgets
        from src.observability.dashboard import DashboardWidget

        dashboard.add_widget(DashboardWidget(id="system_health", type="health", title="System Health", config={}))

        dashboard.add_widget(
            DashboardWidget(
                id="response_time", type="metric", title="Response Time", config={"metric": "response_time"}
            )
        )

        dashboard.add_widget(DashboardWidget(id="active_alerts", type="alert", title="Active Alerts", config={}))

        logger.info(" Monitoring dashboard initialized")

    async def _run_initial_health_check(self):
        """Run initial health check"""
        logger.info(" Running initial health check...")

        health_checker = get_health_checker()
        results = await health_checker.run_all_checks()

        healthy_count = sum(1 for r in results if r.status.value == "healthy")
        logger.info(f" Initial health check: {healthy_count}/{len(results)} components healthy")

        # Record health metrics
        metrics_collector = get_metrics_collector()
        await metrics_collector.record_value("health_check_components", len(results))
        await metrics_collector.record_value("health_check_healthy_components", healthy_count)

    async def get_status(self) -> Dict[str, Any]:
        """Get monitoring system status"""
        health_checker = get_health_checker()
        metrics_collector = get_metrics_collector()
        alert_manager = get_alert_manager()
        dashboard = get_monitoring_dashboard()

        return {
            "initialized": self.initialized,
            "config": self.config,
            "health": {
                "checks": len(health_checker.checks),
                "last_check": health_checker.last_check.isoformat() if health_checker.last_check else None,
            },
            "metrics": {
                "total_metrics": len(metrics_collector.metrics),
                "counters": len(metrics_collector.counters),
                "gauges": len(metrics_collector.gauges),
                "histograms": len(metrics_collector.histograms),
            },
            "alerts": alert_manager.get_alert_summary(),
            "dashboard": {"widgets": len(dashboard.widgets)},
        }

    async def generate_report(self) -> str:
        """Generate monitoring report"""
        dashboard = get_monitoring_dashboard()
        return await dashboard.generate_full_report()


# Global initializer instance
_initializer = None


def get_monitoring_initializer() -> MonitoringInitializer:
    """Get global monitoring initializer"""
    global _initializer
    if _initializer is None:
        _initializer = MonitoringInitializer()
    return _initializer


async def initialize_monitoring(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize monitoring system"""
    initializer = get_monitoring_initializer()
    return await initializer.initialize(config)


async def get_monitoring_status() -> Dict[str, Any]:
    """Get monitoring status"""
    initializer = get_monitoring_initializer()
    return await initializer.get_status()


# Decorator for monitoring function calls
def monitor_function(func):
    """Decorator to monitor function execution"""

    async def wrapper(*args, **kwargs):
        start_time = asyncio.get_event_loop().time()
        function_name = func.__name__

        try:
            # Record start
            await record_metric(f"{function_name}.calls", 1)

            # Execute function
            result = await func(*args, **kwargs)

            # Record success
            await record_metric(f"{function_name}.success", 1)

            return result

        except Exception as e:
            # Record error
            await record_metric(f"{function_name}.errors", 1)
            logger.error(f"Error in {function_name}: {str(e)}")
            raise

        finally:
            # Record execution time
            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time
            await record_metric(f"{function_name}.execution_time", execution_time)

    return wrapper


# Example usage
if __name__ == "__main__":

    async def main():
        print(" Initializing monitoring system...")

        # Initialize
        result = await initialize_monitoring(
            {
                "monitoring_enabled": True,
                "alert_rules": {
                    "response_time_warning": 1.0,
                    "cpu_usage_warning": 80.0,
                },
            }
        )

        print(f"Initialization result: {result}")

        # Get status
        status = await get_monitoring_status()
        print("\nMonitoring status:")
        print(f"Initialized: {status['initialized']}")
        print(f"Health checks: {status['health']['checks']}")
        print(f"Total metrics: {status['metrics']['total_metrics']}")
        print(f"Alert channels: {status['alerts']['channels']}")

        # Generate report
        report = await get_monitoring_initializer().generate_report()
        print("\nMonitoring report preview:")
        print(report[:500] + "...")

    asyncio.run(main())
