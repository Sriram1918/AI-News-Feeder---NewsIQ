"""
Scheduler Package

APScheduler-based background task scheduling for Render deployment.
"""

from app.scheduler.background_scheduler import background_scheduler

__all__ = ["background_scheduler"]
