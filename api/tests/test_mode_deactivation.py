import uuid

from sqlalchemy import select

from app.models import Play
from tests.helpers import begin_play, begin_suggested_play, new_session, register, spin, submit


async def test_qualifying_p1_result_deactivates_mode_for_next_play(client, db):
    headers = await register(client)
    session = await new_session(client, headers, "pursuit", 625)
    p1 = await begin_suggested_play(client, headers, session)

    row = await db.scalar(select(Play).where(Play.id == uuid.UUID(p1["play_id"])))
    assert (row.p1_mode, row.p1_mode_active, row.click_cap) == ("pursuit", True, 96)

    s = await spin(client, headers, p1["play_id"])
    result = await submit(client, headers, p1["play_id"], s["spin_id"], "bonus")
    assert result["qualifying"] is True
    assert result["redirect"] == "next_play"

    p2 = await begin_play(client, headers, session["session_id"], 4, 10, 15)
    assert p2["click_cap"] == 70

    db.expire_all()
    p1_row = await db.scalar(select(Play).where(Play.id == uuid.UUID(p1["play_id"])))
    p2_row = await db.scalar(select(Play).where(Play.id == uuid.UUID(p2["play_id"])))
    assert p1_row.p1_mode_active is False
    assert p1_row.status == "completed"
    assert p1_row.result_type == "bonus"
    assert (p2_row.p1_mode, p2_row.p1_mode_active, p2_row.click_cap) == (None, False, 70)


async def test_p2_uses_standard_map_not_mode_map(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    p1 = await begin_suggested_play(client, headers, session)
    # Strike click 1 is MAX; the standard map's click 1 is BASE.
    assert p1["posture"] == "max"
    s = await spin(client, headers, p1["play_id"])
    await submit(client, headers, p1["play_id"], s["spin_id"], "25x")

    p2 = await begin_play(client, headers, session["session_id"], 4, 10, 15)
    assert p2["posture"] == "base"
    assert p2["next_bet_amount"] == 4.0
