"""Tests for angie.core.cron (CronEngine)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_cron_engine_init():
    from angie.core.cron import CronEngine

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        engine = CronEngine()
        mock_sched_cls.assert_called_once_with(timezone="UTC")
        assert engine._jobs == {}


@pytest.mark.asyncio
async def test_cron_engine_start():
    from angie.core.cron import CronEngine

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_sched_cls.return_value = mock_sched
        engine = CronEngine()
        # Mock sync_from_db to avoid DB access
        engine.sync_from_db = AsyncMock()
        engine._sync_loop = AsyncMock()
        with patch("asyncio.create_task"):
            await engine.start()
        mock_sched.start.assert_called_once()
        engine.sync_from_db.assert_called_once()


def test_cron_engine_shutdown():
    from angie.core.cron import CronEngine

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_sched_cls.return_value = mock_sched
        engine = CronEngine()
        engine.shutdown()
        mock_sched.shutdown.assert_called_once_with(wait=False)


def test_add_cron_invalid_expression():
    from angie.core.cron import CronEngine

    with patch("angie.core.cron.AsyncIOScheduler"):
        engine = CronEngine()
        try:
            engine.add_cron("job1", "invalid", "user1")
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "Invalid cron expression" in str(e)


def test_add_cron_valid():
    from angie.core.cron import CronEngine

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_job = MagicMock()
        mock_sched.add_job.return_value = mock_job
        mock_sched_cls.return_value = mock_sched

        with patch("angie.core.cron.CronTrigger") as mock_trigger_cls:
            mock_trigger = MagicMock()
            mock_trigger_cls.return_value = mock_trigger

            engine = CronEngine()
            engine.add_cron(
                job_id="job1",
                expression="0 * * * *",
                user_id="user1",
                agent_slug="test-agent",
                payload={"key": "value"},
            )

            mock_sched.add_job.assert_called_once()
            assert "job1" in engine._jobs
            assert engine._jobs["job1"]["expression"] == "0 * * * *"


def test_remove_cron():
    from angie.core.cron import CronEngine

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_sched_cls.return_value = mock_sched

        engine = CronEngine()
        engine._jobs["job1"] = {"expression": "0 * * * *", "next_run": "soon"}
        engine.remove_cron("job1")

        mock_sched.remove_job.assert_called_once_with("job1")
        assert "job1" not in engine._jobs


def test_list_crons():
    from angie.core.cron import CronEngine

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_job1 = MagicMock()
        mock_job1.id = "job1"
        mock_job1.next_run_time = "2025-01-01T00:00:00"
        mock_job2 = MagicMock()
        mock_job2.id = "job2"
        mock_job2.next_run_time = "2025-01-02T00:00:00"
        mock_sched.get_jobs.return_value = [mock_job1, mock_job2]
        mock_sched_cls.return_value = mock_sched

        engine = CronEngine()
        crons = engine.list_crons()

        assert len(crons) == 2
        assert crons[0]["id"] == "job1"
        assert crons[1]["id"] == "job2"


async def test_add_cron_fires_event():
    """Test that the _fire coroutine dispatches an AngieEvent."""
    from angie.core.cron import CronEngine

    captured_fire = []

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_job = MagicMock()

        def capture_add_job(fn, trigger, id, replace_existing):
            captured_fire.append(fn)
            return mock_job

        mock_sched.add_job.side_effect = capture_add_job
        mock_sched_cls.return_value = mock_sched

        with patch("angie.core.cron.CronTrigger"):
            engine = CronEngine()
            engine.add_cron("job1", "0 * * * *", "user1", agent_slug="test-agent")

    assert len(captured_fire) == 1

    with patch("angie.core.cron.router") as mock_router:
        mock_router.dispatch = AsyncMock()
        await captured_fire[0]()
        mock_router.dispatch.assert_called_once()
        event = mock_router.dispatch.call_args[0][0]
        assert event.payload["job_id"] == "job1"
        assert event.payload["agent_slug"] == "test-agent"


@pytest.mark.asyncio
async def test_sync_from_db_adds_new_jobs():
    """Test that sync_from_db loads enabled jobs from DB and registers them."""
    from angie.core.cron import CronEngine

    mock_job_record = MagicMock()
    mock_job_record.id = "job1"
    mock_job_record.cron_expression = "0 * * * *"
    mock_job_record.is_enabled = True

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_sched_cls.return_value = mock_sched
        engine = CronEngine()
        engine._register_job = MagicMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_job_record]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("angie.db.session.get_session_factory", return_value=mock_factory):
            await engine.sync_from_db()

        engine._register_job.assert_called_once_with(mock_job_record)


@pytest.mark.asyncio
async def test_sync_from_db_removes_stale_jobs():
    """Test that sync_from_db removes jobs no longer in DB."""
    from angie.core.cron import CronEngine

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_sched_cls.return_value = mock_sched
        engine = CronEngine()
        engine._jobs["stale-job"] = {"expression": "0 0 * * *", "next_run": "soon"}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("angie.db.session.get_session_factory", return_value=mock_factory):
            await engine.sync_from_db()

        mock_sched.remove_job.assert_called_once_with("stale-job")
        assert "stale-job" not in engine._jobs


@pytest.mark.asyncio
async def test_sync_from_db_skips_unchanged_jobs():
    """Test that sync_from_db skips jobs whose expression hasn't changed."""
    from angie.core.cron import CronEngine

    mock_job_record = MagicMock()
    mock_job_record.id = "job1"
    mock_job_record.cron_expression = "0 * * * *"

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_sched_cls.return_value = mock_sched
        engine = CronEngine()
        engine._jobs["job1"] = {"expression": "0 * * * *", "next_run": "soon"}
        engine._register_job = MagicMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_job_record]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("angie.db.session.get_session_factory", return_value=mock_factory):
            await engine.sync_from_db()

        engine._register_job.assert_not_called()


@pytest.mark.asyncio
async def test_sync_from_db_updates_changed_jobs():
    """Test that sync_from_db re-registers jobs with updated expressions."""
    from angie.core.cron import CronEngine

    mock_job_record = MagicMock()
    mock_job_record.id = "job1"
    mock_job_record.cron_expression = "30 * * * *"  # changed from 0

    with patch("angie.core.cron.AsyncIOScheduler") as mock_sched_cls:
        mock_sched = MagicMock()
        mock_sched_cls.return_value = mock_sched
        engine = CronEngine()
        engine._jobs["job1"] = {"expression": "0 * * * *", "next_run": "soon"}
        engine._register_job = MagicMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_job_record]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("angie.db.session.get_session_factory", return_value=mock_factory):
            await engine.sync_from_db()

        engine._register_job.assert_called_once_with(mock_job_record)
