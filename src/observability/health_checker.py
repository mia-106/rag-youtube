"""
Health Checker Module
Provides comprehensive health checks for all system components
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Health check result"""

    component: str
    status: HealthStatus
    message: str
    response_time_ms: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class HealthCheck(ABC):
    """Abstract health check"""

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """Perform health check"""
        pass


class DatabaseHealthCheck(HealthCheck):
    """Database health check"""

    def __init__(self, connection_string: str, timeout: float = 5.0):
        self.connection_string = connection_string
        self.timeout = timeout

    async def check(self) -> HealthCheckResult:
        """Check database health"""
        start_time = time.time()

        try:
            # Simulate database check
            await asyncio.sleep(0.1)  # Simulate connection time

            # In real implementation, would check:
            # - Connection availability
            # - Query execution time
            # - Connection pool status

            response_time = (time.time() - start_time) * 1000

            return HealthCheckResult(
                component="database",
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"connection_string": self.connection_string, "timeout": self.timeout},
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Database health check failed: {str(e)}")

            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message="Database connection failed",
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error=str(e),
            )


class APIHealthCheck(HealthCheck):
    """API health check"""

    def __init__(self, api_name: str, endpoint: str, timeout: float = 5.0):
        self.api_name = api_name
        self.endpoint = endpoint
        self.timeout = timeout

    async def check(self) -> HealthCheckResult:
        """Check API health"""
        start_time = time.time()

        try:
            # Simulate API check
            await asyncio.sleep(0.05)  # Simulate API call

            response_time = (time.time() - start_time) * 1000

            # Check response time
            if response_time > 2000:
                status = HealthStatus.DEGRADED
                message = f"{self.api_name} API response time degraded"
            elif response_time > self.timeout * 1000:
                status = HealthStatus.UNHEALTHY
                message = f"{self.api_name} API timeout"
            else:
                status = HealthStatus.HEALTHY
                message = f"{self.api_name} API healthy"

            return HealthCheckResult(
                component=f"api.{self.api_name}",
                status=status,
                message=message,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"endpoint": self.endpoint, "timeout": self.timeout},
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"API health check failed: {str(e)}")

            return HealthCheckResult(
                component=f"api.{self.api_name}",
                status=HealthStatus.UNHEALTHY,
                message=f"{self.api_name} API check failed",
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error=str(e),
            )


class VectorStoreHealthCheck(HealthCheck):
    """Vector store health check"""

    def __init__(self, vector_store_type: str, config: Dict[str, Any]):
        self.vector_store_type = vector_store_type
        self.config = config

    async def check(self) -> HealthCheckResult:
        """Check vector store health"""
        start_time = time.time()

        try:
            # Simulate vector store check
            await asyncio.sleep(0.08)  # Simulate check

            response_time = (time.time() - start_time) * 1000

            return HealthCheckResult(
                component="vector_store",
                status=HealthStatus.HEALTHY,
                message=f"{self.vector_store_type} vector store healthy",
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"type": self.vector_store_type, "config": self.config},
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Vector store health check failed: {str(e)}")

            return HealthCheckResult(
                component="vector_store",
                status=HealthStatus.UNHEALTHY,
                message=f"{self.vector_store_type} vector store unhealthy",
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error=str(e),
            )


class SystemHealthCheck(HealthCheck):
    """System resource health check"""

    def __init__(self):
        pass

    async def check(self) -> HealthCheckResult:
        """Check system health"""
        start_time = time.time()

        try:
            # Check memory usage
            import psutil

            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)

            response_time = (time.time() - start_time) * 1000

            # Determine health status
            status = HealthStatus.HEALTHY
            issues = []

            if memory.percent > 90:
                status = HealthStatus.UNHEALTHY
                issues.append(f"High memory usage: {memory.percent:.1f}%")

            elif memory.percent > 80:
                status = HealthStatus.DEGRADED
                issues.append(f"Elevated memory usage: {memory.percent:.1f}%")

            if cpu_percent > 90:
                status = HealthStatus.UNHEALTHY
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")

            elif cpu_percent > 80:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED
                issues.append(f"Elevated CPU usage: {cpu_percent:.1f}%")

            if disk.percent > 95:
                status = HealthStatus.UNHEALTHY
                issues.append(f"Low disk space: {100 - disk.percent:.1f}% free")

            message = "; ".join(issues) if issues else "System resources healthy"

            return HealthCheckResult(
                component="system",
                status=status,
                message=message,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_free_gb": disk.free / (1024**3),
                },
            )

        except ImportError:
            # psutil not available
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="system",
                status=HealthStatus.UNKNOWN,
                message="Cannot check system resources (psutil not installed)",
                response_time_ms=response_time,
                timestamp=datetime.now(),
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"System health check failed: {str(e)}")

            return HealthCheckResult(
                component="system",
                status=HealthStatus.UNHEALTHY,
                message="System health check failed",
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error=str(e),
            )


class HealthChecker:
    """Health checker orchestrator"""

    def __init__(self):
        self.checks: List[HealthCheck] = []
        self.last_check: Optional[datetime] = None
        self.last_results: List[HealthCheckResult] = []

    def add_check(self, check: HealthCheck):
        """Add a health check"""
        self.checks.append(check)
        logger.info(f"Added health check: {check.__class__.__name__}")

    async def run_all_checks(self) -> List[HealthCheckResult]:
        """Run all health checks"""
        logger.info(f"Running {len(self.checks)} health checks")

        self.last_check = datetime.now()
        results = []

        # Run checks concurrently
        tasks = [check.check() for check in self.checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    HealthCheckResult(
                        component=self.checks[i].__class__.__name__,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check error: {str(result)}",
                        response_time_ms=0,
                        timestamp=datetime.now(),
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        self.last_results = processed_results

        # Log results
        healthy_count = sum(1 for r in processed_results if r.status == HealthStatus.HEALTHY)
        logger.info(f"Health check complete: {healthy_count}/{len(processed_results)} healthy")

        return processed_results

    async def get_overall_status(self) -> HealthStatus:
        """Get overall system health status"""
        if not self.last_results:
            await self.run_all_checks()

        if not self.last_results:
            return HealthStatus.UNKNOWN

        # Check for any unhealthy components
        for result in self.last_results:
            if result.status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # Check for any degraded components
        for result in self.last_results:
            if result.status == HealthStatus.DEGRADED:
                return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def get_summary(self) -> Dict[str, Any]:
        """Get health check summary"""
        if not self.last_results:
            return {"status": "unknown", "total_checks": len(self.checks), "last_check": None}

        status_counts = {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0}

        for result in self.last_results:
            status_counts[result.status.value] += 1

        return {
            "status": self.last_results[0].status.value if self.last_results else "unknown",
            "total_checks": len(self.last_results),
            "healthy": status_counts["healthy"],
            "degraded": status_counts["degraded"],
            "unhealthy": status_counts["unhealthy"],
            "unknown": status_counts["unknown"],
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "results": [
                {
                    "component": r.component,
                    "status": r.status.value,
                    "message": r.message,
                    "response_time_ms": r.response_time_ms,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in self.last_results
            ],
        }


# Global health checker instance
_health_checker = None


def get_health_checker() -> HealthChecker:
    """Get global health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
        _health_checker.add_check(SystemHealthCheck())
        # Add more checks as needed
    return _health_checker


def test_health_checker():
    """Test health checker"""
    print(" Testing Health Checker...")

    # Create health checker
    checker = HealthChecker()

    # Add checks
    checker.add_check(DatabaseHealthCheck("postgresql://localhost"))
    checker.add_check(APIHealthCheck("youtube", "https://api.youtube.com"))
    checker.add_check(VectorStoreHealthCheck("supabase", {}))

    print(" Health checker created")

    # Run checks
    print("\n Running health checks...")
    results = asyncio.run(checker.run_all_checks())

    print(f"\n Health Check Results ({len(results)} checks):")
    for result in results:
        status_symbol = {
            HealthStatus.HEALTHY: "",
            HealthStatus.DEGRADED: "",
            HealthStatus.UNHEALTHY: "",
            HealthStatus.UNKNOWN: "",
        }[result.status]
        print(f"  {status_symbol} {result.component}: {result.message}")
        print(f"     Response time: {result.response_time_ms:.2f}ms")

    # Get summary
    print("\n Health Summary:")
    summary = checker.get_summary()
    for key, value in summary.items():
        if key != "results":
            print(f"  {key}: {value}")

    print("\n Health checker test complete")


if __name__ == "__main__":
    test_health_checker()
