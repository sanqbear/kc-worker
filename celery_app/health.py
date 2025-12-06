"""
Health check HTTP server for monitoring worker availability.

Provides simple HTTP endpoints for liveness and readiness probes in orchestration systems.
"""

import asyncio
from typing import Dict, Any

from aiohttp import web

from .celery import app as celery_app
from .config import settings
from .utils.logging import get_logger


logger = get_logger(__name__)


async def health_check(request: web.Request) -> web.Response:
    """
    Basic health check endpoint.

    Returns 200 OK if the worker process is running.

    Returns:
        web.Response: HTTP 200 with health status
    """
    return web.json_response({
        "status": "healthy",
        "service": "celery-worker",
        "environment": settings.environment,
    })


async def liveness_check(request: web.Request) -> web.Response:
    """
    Liveness probe endpoint.

    Indicates whether the worker is alive and should not be restarted.
    Returns 200 if the process is running.

    Returns:
        web.Response: HTTP 200 if alive
    """
    return web.json_response({
        "status": "alive",
    })


async def readiness_check(request: web.Request) -> web.Response:
    """
    Readiness probe endpoint.

    Indicates whether the worker is ready to accept tasks.
    Checks Redis connection and worker registration.

    Returns:
        web.Response: HTTP 200 if ready, HTTP 503 if not ready
    """
    try:
        # Check Redis connection by pinging
        inspect = celery_app.control.inspect()
        stats = inspect.stats()

        if stats is None or len(stats) == 0:
            return web.json_response(
                {
                    "status": "not_ready",
                    "reason": "No workers registered",
                },
                status=503
            )

        return web.json_response({
            "status": "ready",
            "workers": len(stats),
        })

    except Exception as e:
        logger.error("Readiness check failed", extra={"error": str(e)})
        return web.json_response(
            {
                "status": "not_ready",
                "reason": str(e),
            },
            status=503
        )


async def metrics_endpoint(request: web.Request) -> web.Response:
    """
    Basic metrics endpoint.

    Returns worker statistics and queue information.

    Returns:
        web.Response: HTTP 200 with metrics
    """
    try:
        inspect = celery_app.control.inspect()

        # Get worker stats
        stats = inspect.stats() or {}
        active_tasks = inspect.active() or {}
        reserved_tasks = inspect.reserved() or {}

        # Calculate metrics
        total_workers = len(stats)
        total_active = sum(len(tasks) for tasks in active_tasks.values())
        total_reserved = sum(len(tasks) for tasks in reserved_tasks.values())

        return web.json_response({
            "workers": {
                "total": total_workers,
                "names": list(stats.keys()),
            },
            "tasks": {
                "active": total_active,
                "reserved": total_reserved,
            },
        })

    except Exception as e:
        logger.error("Metrics collection failed", extra={"error": str(e)})
        return web.json_response(
            {"error": str(e)},
            status=500
        )


def create_health_app() -> web.Application:
    """
    Create the health check web application.

    Returns:
        web.Application: Configured aiohttp application
    """
    app = web.Application()

    # Add routes
    app.router.add_get("/health", health_check)
    app.router.add_get("/health/live", liveness_check)
    app.router.add_get("/health/ready", readiness_check)
    app.router.add_get("/metrics", metrics_endpoint)

    return app


async def start_health_server() -> None:
    """
    Start the health check HTTP server.

    Runs alongside the Celery worker to provide health endpoints.
    """
    if not settings.health_check_enabled:
        logger.info("Health check server disabled")
        return

    app = create_health_app()

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", settings.health_check_port)
    await site.start()

    logger.info(
        "Health check server started",
        extra={"port": settings.health_check_port}
    )

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Health check server shutting down")
        await runner.cleanup()


def run_health_server() -> None:
    """
    Run the health check server (blocking).

    This is intended to be run in a separate thread or process.
    """
    asyncio.run(start_health_server())
