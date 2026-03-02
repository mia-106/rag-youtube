"""
Metrics Collector Module
Provides metric collection and aggregation capabilities
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging
import statistics
import json

logger = logging.getLogger(__name__)


@dataclass
class MetricConfig:
    """Metric configuration"""

    name: str
    type: str  # 'counter', 'gauge', 'histogram'
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    aggregations: List[str] = field(default_factory=lambda: ["avg", "min", "max", "count"])


class Counter:
    """Counter metric"""

    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value = 0.0
        self._lock = asyncio.Lock()

    async def increment(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment counter"""
        async with self._lock:
            self._value += value

    async def reset(self):
        """Reset counter"""
        async with self._lock:
            self._value = 0.0

    async def get_value(self) -> float:
        """Get current value"""
        return self._value


class Gauge:
    """Gauge metric"""

    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value = 0.0
        self._lock = asyncio.Lock()

    async def set(self, value: float):
        """Set gauge value"""
        async with self._lock:
            self._value = value

    async def increment(self, value: float = 1.0):
        """Increment gauge"""
        async with self._lock:
            self._value += value

    async def decrement(self, value: float = 1.0):
        """Decrement gauge"""
        async with self._lock:
            self._value -= value

    async def get_value(self) -> float:
        """Get current value"""
        return self._value


class Histogram:
    """Histogram metric for tracking value distributions"""

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.buckets = buckets or [0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._values = deque(maxlen=10000)  # Store last 10k values
        self._lock = asyncio.Lock()

    async def observe(self, value: float):
        """Observe a value"""
        async with self._lock:
            self._values.append(value)

    async def get_stats(self) -> Dict[str, float]:
        """Get histogram statistics"""
        async with self._lock:
            if not self._values:
                return {
                    "count": 0,
                    "sum": 0.0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "p50": 0.0,
                    "p90": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                }

            values = list(self._values)

            return {
                "count": len(values),
                "sum": sum(values),
                "avg": statistics.mean(values),
                "min": min(values),
                "max": max(values),
                "p50": self._percentile(values, 50),
                "p90": self._percentile(values, 90),
                "p95": self._percentile(values, 95),
                "p99": self._percentile(values, 99),
            }

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile"""
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


class MetricsCollector:
    """Metrics collector"""

    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.counters: Dict[str, Counter] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.configs: Dict[str, MetricConfig] = {}
        self._lock = asyncio.Lock()

    async def record_value(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None, timestamp: Optional[datetime] = None
    ):
        """Record a metric value"""
        async with self._lock:
            if timestamp is None:
                timestamp = datetime.now()

            metric_point = {"name": name, "value": value, "labels": labels or {}, "timestamp": timestamp}

            self.metrics[name].append(metric_point)
            logger.debug(f" Recorded metric: {name} = {value}")

    async def create_counter(
        self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None
    ) -> Counter:
        """Create a counter metric"""
        async with self._lock:
            counter = Counter(name, description, labels)
            self.counters[name] = counter
            logger.info(f" Created counter: {name}")
            return counter

    async def create_gauge(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Gauge:
        """Create a gauge metric"""
        async with self._lock:
            gauge = Gauge(name, description, labels)
            self.gauges[name] = gauge
            logger.info(f" Created gauge: {name}")
            return gauge

    async def create_histogram(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        """Create a histogram metric"""
        async with self._lock:
            histogram = Histogram(name, description, labels, buckets)
            self.histograms[name] = histogram
            logger.info(f" Created histogram: {name}")
            return histogram

    async def get_metric_values(self, name: str, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get metric values"""
        async with self._lock:
            if name not in self.metrics:
                return []

            cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)

            return [point for point in self.metrics[name] if point["timestamp"] >= cutoff_time]

    async def get_metric_statistics(self, name: str, duration_minutes: int = 60) -> Dict[str, Any]:
        """Get metric statistics"""
        values = await self.get_metric_values(name, duration_minutes)

        if not values:
            return {"name": name, "count": 0, "duration_minutes": duration_minutes}

        numeric_values = [v["value"] for v in values]

        stats = {
            "name": name,
            "count": len(values),
            "duration_minutes": duration_minutes,
            "start_time": values[0]["timestamp"].isoformat(),
            "end_time": values[-1]["timestamp"].isoformat(),
            "min": min(numeric_values),
            "max": max(numeric_values),
            "avg": statistics.mean(numeric_values),
            "median": statistics.median(numeric_values),
            "p95": self._percentile(numeric_values, 95),
            "p99": self._percentile(numeric_values, 99),
        }

        return stats

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile"""
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

    async def get_all_metrics_summary(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """Get summary of all metrics"""
        async with self._lock:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "duration_minutes": duration_minutes,
                "total_metrics": len(self.metrics),
                "metrics": {},
            }

            for metric_name in self.metrics.keys():
                stats = await self.get_metric_statistics(metric_name, duration_minutes)
                summary["metrics"][metric_name] = stats

            return summary

    async def export_metrics(self, name: str, format: str = "json", duration_minutes: int = 60) -> str:
        """Export metrics"""
        values = await self.get_metric_values(name, duration_minutes)

        if format.lower() == "json":
            return json.dumps(values, default=str, indent=2)
        else:
            # CSV format
            lines = ["timestamp,name,value,labels"]
            for point in values:
                labels_str = json.dumps(point["labels"])
                lines.append(f"{point['timestamp'].isoformat()},{point['name']},{point['value']},{labels_str}")
            return "\n".join(lines)

    async def clear_metrics(self, name: Optional[str] = None):
        """Clear metrics"""
        async with self._lock:
            if name:
                if name in self.metrics:
                    del self.metrics[name]
                    logger.info(f" Cleared metrics: {name}")
            else:
                self.metrics.clear()
                logger.info(" Cleared all metrics")


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


async def record_metric(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Record a metric"""
    collector = get_metrics_collector()
    await collector.record_value(name, value, labels)


def test_metrics_collector():
    """Test metrics collector"""
    print(" Testing Metrics Collector...")

    async def run_test():
        # Create collector
        collector = MetricsCollector()

        print(" Metrics collector created")

        # Test value recording
        print("\n Testing value recording...")
        for i in range(10):
            await collector.record_value("response_time", 0.5 + i * 0.1)
            await collector.record_value("cpu_usage", 50 + i * 2)

        print(" Value recording complete")

        # Test metric types
        print("\n Testing metric types...")
        counter = await collector.create_counter("request_count", "Number of requests")
        await counter.increment()

        gauge = await collector.create_gauge("memory_usage", "Memory usage percentage")
        await gauge.set(65.5)

        histogram = await collector.create_histogram("latency", "Request latency")
        await histogram.observe(1.2)
        await histogram.observe(0.8)
        await histogram.observe(1.5)

        print(" Metric types created")

        # Get statistics
        print("\n Getting statistics...")
        stats = await collector.get_metric_statistics("response_time")
        print(" Response time statistics:")
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.3f}")
            else:
                print(f"  {key}: {value}")

        # Get histogram stats
        histogram_stats = await histogram.get_stats()
        print("\n Histogram statistics:")
        for key, value in histogram_stats.items():
            print(f"  {key}: {value}")

        # Get all metrics summary
        print("\n All metrics summary...")
        summary = await collector.get_all_metrics_summary()
        print(f" Total metrics: {summary['total_metrics']}")

        print("\n Metrics collector test complete")

    asyncio.run(run_test())


if __name__ == "__main__":
    test_metrics_collector()
