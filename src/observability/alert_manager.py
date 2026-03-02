"""
Alert Manager Module
Provides alerting and notification capabilities
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
import smtplib
import aiohttp
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert event"""

    id: str
    title: str
    message: str
    severity: AlertSeverity
    source: str
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None


class NotificationChannel(ABC):
    """Abstract notification channel"""

    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """Send notification"""
        pass


class LogNotification(NotificationChannel):
    """Log-based notification"""

    async def send(self, alert: Alert) -> bool:
        """Send to logs"""
        try:
            log_message = f"[{alert.severity.value.upper()}] {alert.title}: {alert.message}"
            logger.warning(log_message)

            if alert.labels:
                logger.warning(f"Labels: {json.dumps(alert.labels)}")

            return True
        except Exception as e:
            logger.error(f"Failed to send log notification: {str(e)}")
            return False


class EmailNotification(NotificationChannel):
    """Email notification"""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: List[str],
        use_tls: bool = True,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
        self.use_tls = use_tls

    async def send(self, alert: Alert) -> bool:
        """Send email notification"""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"

            body = f"""
Alert: {alert.title}
Severity: {alert.severity.value.upper()}
Source: {alert.source}
Time: {alert.timestamp.isoformat()}

Message:
{alert.message}

Labels:
{json.dumps(alert.labels, indent=2)}

Annotations:
{json.dumps(alert.annotations, indent=2)}
"""

            msg.attach(MIMEText(body, "plain"))

            if self.use_tls:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.login(self.username, self.password)
                    server.send_message(msg)

            logger.info(f"Email notification sent for alert: {alert.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
            return False


class WebhookNotification(NotificationChannel):
    """Webhook notification"""

    def __init__(self, url: str, method: str = "POST", headers: Optional[Dict[str, str]] = None, timeout: int = 10):
        self.url = url
        self.method = method.upper()
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout

    async def send(self, alert: Alert) -> bool:
        """Send webhook notification"""
        try:
            payload = {
                "id": alert.id,
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity.value,
                "source": alert.source,
                "timestamp": alert.timestamp.isoformat(),
                "labels": alert.labels,
                "annotations": alert.annotations,
                "resolved": alert.resolved,
                "acknowledged": alert.acknowledged,
            }

            timeout = aiohttp.ClientTimeout(total=self.timeout)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(self.method, self.url, json=payload, headers=self.headers) as response:
                    if response.status < 400:
                        logger.info(f"Webhook notification sent for alert: {alert.id}")
                        return True
                    else:
                        logger.error(f"Webhook notification failed: HTTP {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {str(e)}")
            return False


class SlackNotification(NotificationChannel):
    """Slack notification via webhook"""

    def __init__(
        self, webhook_url: str, channel: Optional[str] = None, username: str = "AlertBot", icon_emoji: str = ":warning:"
    ):
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji

    async def send(self, alert: Alert) -> bool:
        """Send Slack notification"""
        try:
            color_map = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9800",
                AlertSeverity.ERROR: "#f44336",
                AlertSeverity.CRITICAL: "#9c27b0",
            }

            payload = {
                "username": self.username,
                "icon_emoji": self.icon_emoji,
                "attachments": [
                    {
                        "color": color_map.get(alert.severity, "#2196f3"),
                        "title": alert.title,
                        "text": alert.message,
                        "fields": [
                            {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                            {"title": "Source", "value": alert.source, "short": True},
                            {"title": "Time", "value": alert.timestamp.isoformat(), "short": True},
                        ],
                        "mrkdwn_in": ["text", "fields"],
                    }
                ],
            }

            if self.channel:
                payload["channel"] = self.channel

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent for alert: {alert.id}")
                        return True
                    else:
                        logger.error(f"Slack notification failed: HTTP {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
            return False


class AlertManager:
    """Alert manager"""

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.resolved_alerts: Dict[str, Alert] = {}
        self.channels: List[NotificationChannel] = []
        self.notification_rules: List[Dict[str, Any]] = []
        self.suppression_rules: List[Dict[str, Any]] = []

        # Add default log channel
        self.add_channel(LogNotification())

    def add_channel(self, channel: NotificationChannel):
        """Add notification channel"""
        self.channels.append(channel)
        logger.info(f"Added notification channel: {channel.__class__.__name__}")

    def add_suppression_rule(self, labels: Dict[str, str], duration_minutes: int, reason: str):
        """Add alert suppression rule"""
        rule = {"labels": labels, "duration_minutes": duration_minutes, "reason": reason, "created_at": datetime.now()}
        self.suppression_rules.append(rule)
        logger.info(f"Added suppression rule: {reason}")

    async def create_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: str,
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
    ) -> Alert:
        """Create alert"""
        alert_id = f"{source}:{datetime.now().timestamp()}"

        alert = Alert(
            id=alert_id,
            title=title,
            message=message,
            severity=severity,
            source=source,
            timestamp=datetime.now(),
            labels=labels or {},
            annotations=annotations or {},
        )

        # Check if alert is suppressed
        if self._is_suppressed(alert):
            logger.info(f"Alert suppressed: {alert_id}")
            return alert

        self.alerts[alert_id] = alert
        self.active_alerts[alert_id] = alert

        logger.warning(f"Alert created: {alert_id} - {title}")

        # Send notifications
        await self._send_notifications(alert)

        return alert

    def _is_suppressed(self, alert: Alert) -> bool:
        """Check if alert is suppressed"""
        for rule in self.suppression_rules:
            labels_match = all(alert.labels.get(k) == v for k, v in rule["labels"].items())
            if labels_match:
                return True
        return False

    async def resolve_alert(self, alert_id: str, message: Optional[str] = None) -> bool:
        """Resolve alert"""
        if alert_id not in self.active_alerts:
            return False

        alert = self.active_alerts[alert_id]
        alert.resolved = True
        alert.resolved_at = datetime.now()

        if message:
            alert.message = message

        del self.active_alerts[alert_id]
        self.resolved_alerts[alert_id] = alert

        logger.info(f"Alert resolved: {alert_id}")
        return True

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge alert"""
        if alert_id not in self.alerts:
            return False

        alert = self.alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now()

        logger.info(f"Alert acknowledged: {alert_id}")
        return True

    async def _send_notifications(self, alert: Alert):
        """Send notifications"""
        for channel in self.channels:
            try:
                await channel.send(alert)
            except Exception as e:
                logger.error(f"Failed to send notification: {str(e)}")

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.active_alerts.values())

    def get_all_alerts(self, limit: Optional[int] = None) -> List[Alert]:
        """Get all alerts"""
        all_alerts = list(self.alerts.values())
        all_alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return all_alerts[:limit] if limit else all_alerts

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary"""
        severity_counts = {
            AlertSeverity.INFO: 0,
            AlertSeverity.WARNING: 0,
            AlertSeverity.ERROR: 0,
            AlertSeverity.CRITICAL: 0,
        }

        for alert in self.active_alerts.values():
            severity_counts[alert.severity] += 1

        return {
            "total_alerts": len(self.alerts),
            "active_alerts": len(self.active_alerts),
            "resolved_alerts": len(self.resolved_alerts),
            "severity_breakdown": {severity.value: count for severity, count in severity_counts.items()},
            "channels": len(self.channels),
            "suppression_rules": len(self.suppression_rules),
        }

    def clear_resolved_alerts(self, older_than_days: int = 7):
        """Clear resolved alerts older than specified days"""
        cutoff = datetime.now() - timedelta(days=older_than_days)

        to_remove = [
            alert_id
            for alert_id, alert in self.resolved_alerts.items()
            if alert.resolved_at and alert.resolved_at < cutoff
        ]

        for alert_id in to_remove:
            del self.resolved_alerts[alert_id]

        logger.info(f"Cleared {len(to_remove)} resolved alerts older than {older_than_days} days")


# Global alert manager instance
_alert_manager = None


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def test_alert_manager():
    """Test alert manager"""
    print(" Testing Alert Manager...")

    async def run_test():
        # Create alert manager
        manager = AlertManager()

        print(" Alert manager created")

        # Add log channel (default)
        print(f" Default channels: {len(manager.channels)}")

        # Create test alerts
        print("\n Creating test alerts...")
        alert1 = await manager.create_alert(
            title="High CPU Usage",
            message="CPU usage is above 90%",
            severity=AlertSeverity.WARNING,
            source="system",
            labels={"host": "server1"},
        )

        await manager.create_alert(
            title="Database Connection Failed",
            message="Cannot connect to database",
            severity=AlertSeverity.CRITICAL,
            source="database",
            labels={"db": "postgres"},
        )

        print(f" Alerts created: {len(manager.active_alerts)}")

        # Get alert summary
        print("\n Alert Summary:")
        summary = manager.get_alert_summary()
        for key, value in summary.items():
            print(f"  {key}: {value}")

        # Resolve alert
        print("\n Resolving alert...")
        await manager.resolve_alert(alert1.id, "CPU usage back to normal")

        print(f" Active alerts: {len(manager.active_alerts)}")

        # Get all alerts
        print("\n All Alerts:")
        all_alerts = manager.get_all_alerts()
        for alert in all_alerts:
            status = "" if alert.resolved else ""
            print(f"  {status} {alert.title} ({alert.severity.value})")

        print("\n Alert manager test complete")

    asyncio.run(run_test())


if __name__ == "__main__":
    test_alert_manager()
