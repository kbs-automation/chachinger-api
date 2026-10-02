import uuid

import pytest
from sqlalchemy import select

from app.models import Play
from tests.helpers import begin_suggested_play, new_session, register

MODES = [
    ("entertainment", 1000),
    ("entertainment_plus", 1300),
    ("strike", 555),
    ("pursuit", 625),
    ("deep_run_pro", 775),
]


@pytest.mark.parametrize(("mode", "budget"), MODES)
async def test_every_mode_stores_click_cap_96_on_p1(client, db, mode, budget):
    headers = await register(client)
    session = await new_session(client, headers, mode, budget)
    assert session["mode_click_cap"] == 96
    assert (session["play_number"], session["cycle_number"]) == (1, 1)

    play = await begin_suggested_play(client, headers, session)
    assert play["click_cap"] == 96

    row = await db.scalar(select(Play).where(Play.id == uuid.UUID(play["play_id"])))
    assert row.click_cap == 96
    assert row.p1_mode == mode
    assert row.p1_mode_active is (mode != "entertainment")
