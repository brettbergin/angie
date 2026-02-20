"""Tests for model __repr__ methods and helpers."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def test_new_uuid_returns_string():
    from angie.models.base import new_uuid
    result = new_uuid()
    assert isinstance(result, str)
    assert len(result) == 36  # UUID4 format


def test_agent_model_repr():
    from angie.models.agent import Agent as AgentModel
    a = AgentModel(name="TestAgent", slug="test", description="desc", capabilities=["cap"])
    assert "TestAgent" in repr(a)


def test_channel_config_repr():
    from angie.models.channel import ChannelConfig, ChannelType
    c = ChannelConfig(type=ChannelType.SLACK, user_id="user-1")
    r = repr(c)
    assert "slack" in r
    assert "user-1" in r


def test_event_repr():
    from angie.models.event import Event, EventType
    e = Event(type=EventType.USER_MESSAGE, payload={})
    r = repr(e)
    assert "user_message" in r


def test_prompt_repr():
    from angie.models.prompt import Prompt
    p = Prompt(type="system", name="base", content="hello")
    r = repr(p)
    assert "system" in r
    assert "base" in r


def test_task_repr():
    from angie.models.task import Task, TaskStatus
    t = Task(title="My task", status=TaskStatus.PENDING)
    r = repr(t)
    assert "pending" in r


def test_team_repr():
    from angie.models.team import Team
    t = Team(name="My Team", slug="my-team")
    r = repr(t)
    assert "My Team" in r


def test_user_repr():
    from angie.models.user import User
    u = User(email="test@example.com", username="testuser", hashed_password="hashed")
    r = repr(u)
    assert "testuser" in r


def test_workflow_repr():
    from angie.models.workflow import Workflow
    w = Workflow(name="My Workflow", slug="my-wf")
    r = repr(w)
    assert "My Workflow" in r
