"""
EchoMind Guardian Service Entry Point.

NATS subscriber that monitors DLQ advisories and sends alerts.

Usage:
    python -m guardian.main

Environment Variables:
    GUARDIAN_ENABLED: Enable guardian service (default: true)
    GUARDIAN_HEALTH_PORT: Health check port (default: 8080)
    GUARDIAN_NATS_URL: NATS server URL
    GUARDIAN_ALERTERS: Comma-separated alerter names (default: logging)
    GUARDIAN_LOG_LEVEL: Logging level (default: INFO)
"""

import asyncio
import logging
import os
import signal
import sys
import threading
from typing import Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nats.aio.msg import Msg

from echomind_lib.db.nats_subscriber import (
    JetStreamSubscriber,
    close_nats_subscriber,
    init_nats_subscriber,
)
from echomind_lib.helpers.readiness_probe import HealthServer

from guardian.alerters.base import Alerter
from guardian.alerters.logging_alerter import LoggingAlerter
from guardian.alerters.pagerduty_alerter import PagerDutyAlerter
from guardian.alerters.slack_alerter import SlackAlerter
from guardian.alerters.webhook_alerter import WebhookAlerter
from guardian.config import GuardianSettings, get_settings
from guardian.logic.guardian_service import GuardianService
from guardian.logic.rate_limiter import RateLimiter

# Configure logging
logging.basicConfig(
    level=os.getenv("GUARDIAN_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("echomind-guardian")


class GuardianApp:
    """
    Main Guardian application.

    Manages lifecycle of NATS subscriber and alerters.
    Uses graceful degradation - starts health server first,
    retries failed connections in background.
    """

    def __init__(self) -> None:
        """Initialize Guardian application."""
        self._settings = get_settings()
        self._subscriber: JetStreamSubscriber | None = None
        self._health_server: HealthServer | None = None
        self._service: GuardianService | None = None
        self._running = False
        self._retry_tasks: list[asyncio.Task[None]] = []

        # Connection status
        self._nats_connected = False

    async def start(self) -> None:
        """
        Start the Guardian service.

        Uses graceful degradation - starts health server first,
        retries failed connections in background.
        """
        logger.info("🛡️ Starting EchoMind Guardian Service...")
        logger.info("📋 Configuration:")
        logger.info("   Enabled: %s", self._settings.enabled)
        logger.info("   Health port: %d", self._settings.health_port)
        logger.info("   NATS: %s", self._settings.nats_url)
        logger.info("   Source stream: %s", self._settings.nats_source_stream)
        logger.info("   DLQ stream: %s", self._settings.nats_stream_name)
        logger.info("   Alerters: %s", self._settings.alerters)
        logger.info(
            "   Rate limit: %d per %ds",
            self._settings.alert_rate_limit_per_subject,
            self._settings.alert_rate_limit_window_seconds,
        )

        if not self._settings.enabled:
            logger.warning("⚠️ Guardian is disabled via configuration")
            return

        # Start health server FIRST
        self._health_server = HealthServer(port=self._settings.health_port)
        health_thread = threading.Thread(
            target=self._health_server.start,
            daemon=True,
        )
        health_thread.start()
        logger.info("💓 Health server started on port %d", self._settings.health_port)

        # Initialize alerters
        alerters = self._create_alerters()
        logger.info("✅ Initialized %d alerter(s)", len(alerters))

        # Initialize rate limiter
        rate_limiter = RateLimiter(
            max_per_subject=self._settings.alert_rate_limit_per_subject,
            window_seconds=self._settings.alert_rate_limit_window_seconds,
        )

        # Initialize service
        self._service = GuardianService(
            alerters=alerters,
            rate_limiter=rate_limiter,
        )

        # Initialize NATS with graceful degradation
        logger.info("🔌 Connecting to NATS...")
        try:
            self._subscriber = await init_nats_subscriber(
                servers=[self._settings.nats_url],
                user=(
                    self._settings.nats_user
                    if self._settings.nats_user
                    else None
                ),
                password=(
                    self._settings.nats_password
                    if self._settings.nats_password
                    else None
                ),
            )
            self._nats_connected = True
            logger.info("📥 NATS subscriber connected")

            # Setup subscriptions
            await self._setup_subscriptions()

        except Exception as e:
            logger.warning("⚠️ NATS connection failed: %s", e)
            logger.info("🔄 Will retry NATS connection in background...")
            self._retry_tasks.append(
                asyncio.create_task(self._retry_nats_connection())
            )

        # Update readiness
        self._update_readiness()
        self._running = True

        if self._is_ready():
            logger.info("🚀 Guardian ready and listening for advisories")
        else:
            logger.warning("⚠️ Guardian started but waiting for connections...")

    def _create_alerters(self) -> list[Alerter]:
        """
        Create configured alerters.

        Returns:
            List of alerter instances.
        """
        alerters: list[Alerter] = []
        alerter_names = self._settings.get_alerter_list()

        for name in alerter_names:
            alerter = self._create_alerter(name)
            if alerter:
                alerters.append(alerter)
                logger.info("   📢 Configured alerter: %s", name)

        # Always have at least logging alerter
        if not alerters:
            alerters.append(LoggingAlerter())
            logger.warning("⚠️ No alerters configured, using LoggingAlerter")

        return alerters

    def _create_alerter(self, name: str) -> Alerter | None:
        """
        Create an alerter by name.

        Args:
            name: Alerter name.

        Returns:
            Alerter instance or None if config is missing.
        """
        if name == "logging":
            return LoggingAlerter()

        elif name == "slack":
            if not self._settings.slack_webhook_url:
                logger.warning("⚠️ Slack alerter enabled but GUARDIAN_SLACK_WEBHOOK_URL not set")
                return None
            return SlackAlerter(
                webhook_url=self._settings.slack_webhook_url,
                channel=self._settings.slack_channel,
            )

        elif name == "pagerduty":
            if not self._settings.pagerduty_routing_key:
                logger.warning("⚠️ PagerDuty alerter enabled but GUARDIAN_PAGERDUTY_ROUTING_KEY not set")
                return None
            return PagerDutyAlerter(
                routing_key=self._settings.pagerduty_routing_key,
                severity=self._settings.pagerduty_severity,
            )

        elif name == "webhook":
            if not self._settings.webhook_url:
                logger.warning("⚠️ Webhook alerter enabled but GUARDIAN_WEBHOOK_URL not set")
                return None
            return WebhookAlerter(
                webhook_url=self._settings.webhook_url,
                secret=self._settings.webhook_secret,
                timeout=self._settings.webhook_timeout,
            )

        else:
            logger.warning("⚠️ Unknown alerter: %s", name)
            return None

    async def _retry_nats_connection(self) -> None:
        """Background task to retry NATS connection."""
        while not self._nats_connected:
            await asyncio.sleep(30)
            try:
                self._subscriber = await init_nats_subscriber(
                    servers=[self._settings.nats_url],
                    user=(
                        self._settings.nats_user
                        if self._settings.nats_user
                        else None
                    ),
                    password=(
                        self._settings.nats_password
                        if self._settings.nats_password
                        else None
                    ),
                )
                self._nats_connected = True
                logger.info("📥 NATS subscriber reconnected")
                await self._setup_subscriptions()
                self._update_readiness()
            except Exception as e:
                logger.warning("⚠️ NATS reconnection attempt failed: %s", e)

    def _is_ready(self) -> bool:
        """Check if all required services are connected."""
        return self._nats_connected

    def _update_readiness(self) -> None:
        """Update health server readiness based on connection status."""
        if self._health_server:
            ready = self._is_ready()
            self._health_server.set_ready(ready)
            if ready:
                logger.info("🚀 All services connected - marking as ready")

    async def _setup_subscriptions(self) -> None:
        """Setup NATS subscriptions for advisory messages."""
        if not self._subscriber:
            return

        source_stream = self._settings.nats_source_stream

        # Subscribe to both advisory types
        subjects = [
            f"$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.{source_stream}.>",
            f"$JS.EVENT.ADVISORY.CONSUMER.MSG_TERMINATED.{source_stream}.>",
        ]

        for subject in subjects:
            # Extract advisory type from subject (MAX_DELIVERIES or MSG_TERMINATED)
            advisory_type = subject.split(".")[4].lower().replace("_", "-")
            consumer_name = f"{self._settings.nats_consumer_name}-{advisory_type}"
            try:
                await self._subscriber.subscribe(
                    stream=self._settings.nats_stream_name,
                    consumer=consumer_name,
                    subject=subject,
                    handler=self._handle_advisory,
                )
                logger.info("📥 Subscribed to %s", subject)
            except Exception as e:
                logger.warning("⚠️ Failed to subscribe to %s: %s", subject, e)

    async def _handle_advisory(self, msg: Msg) -> None:
        """
        Handle incoming NATS advisory message.

        Args:
            msg: NATS message with advisory payload.
        """
        if not self._is_ready() or not self._service:
            logger.warning("⚠️ Advisory received but service not ready, will NAK")
            await msg.nak()
            return

        start_time = asyncio.get_event_loop().time()

        try:
            # Process advisory
            details = await self._service.process_advisory(msg.data)

            # ACK message on success
            await msg.ack()
            logger.info(
                "✅ Advisory processed: type=%s seq=%d",
                details.advisory_type,
                details.stream_seq,
            )

        except Exception as e:
            logger.exception("❌ Advisory processing failed: %s", e)
            # NAK to retry
            await msg.nak()

        finally:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.debug("⏰ Processing time: %.2fs", elapsed)

    async def stop(self) -> None:
        """Stop the Guardian service gracefully."""
        logger.info("🛑 Guardian shutting down...")
        self._running = False

        if self._health_server:
            self._health_server.set_ready(False)

        # Cancel retry tasks
        for task in self._retry_tasks:
            task.cancel()

        # Close service (closes alerters)
        if self._service:
            await self._service.close()
            logger.info("🛑 Alerters closed")

        # Close NATS
        try:
            await close_nats_subscriber()
            logger.info("📥 NATS subscriber disconnected")
        except Exception:
            pass

        logger.info("👋 Guardian stopped")


async def main() -> None:
    """Main entry point."""
    app = GuardianApp()

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("⚠️ Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await app.start()
        await stop_event.wait()

    except KeyboardInterrupt:
        logger.info("⚠️ Received keyboard interrupt")

    except Exception as e:
        logger.exception("💀 Fatal error: %s", e)

    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
