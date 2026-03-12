from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import SessionLocal
from app.schemas.interview import WebSocketMessageType
from app.services.interview_service import interview_service

router = APIRouter()
service = interview_service


class ConnectionManager:
    def __init__(self) -> None:
        self.active_by_user: dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        old = self.active_by_user.get(user_id)
        if old and old is not websocket:
            await old.close(code=4000, reason="replaced by new interview connection")
        self.active_by_user[user_id] = websocket

    def disconnect(self, user_id: int) -> None:
        self.active_by_user.pop(user_id, None)


manager = ConnectionManager()


@router.websocket("/ws")
async def interview_ws(websocket: WebSocket) -> None:
    session_id = int(websocket.query_params.get("session_id", "0"))
    user_id = int(websocket.query_params.get("user_id", "0"))
    if session_id <= 0 or user_id <= 0:
        await websocket.close(code=1008, reason="invalid session_id or user_id")
        return

    await manager.connect(user_id, websocket)
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        async with SessionLocal() as db:
            session = await service.get_owned_session(db=db, session_id=session_id, user_id=user_id)
            state = await service.ensure_welcome_turn(db=db, session=session)
            await _push_latest_interviewer_message(websocket, state)

            while True:
                raw = await websocket.receive_text()
                payload = _parse_client_payload(raw)
                if payload.get("type") == WebSocketMessageType.PONG.value:
                    continue

                message = str(payload.get("message") or "").strip()
                if not message:
                    continue

                old_stage = state["current_stage"].value
                state = await service.handle_candidate_message(db=db, session=session, message=message)
                new_stage = state["current_stage"].value
                if old_stage != new_stage:
                    await websocket.send_json(
                        {
                            "type": WebSocketMessageType.STATE_CHANGE.value,
                            "data": {"old_stage": old_stage, "new_stage": new_stage},
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )

                await _push_latest_interviewer_message(websocket, state)

                if state["status"] == "ENDED":
                    await websocket.send_json(
                        {
                            "type": WebSocketMessageType.REPORT_READY.value,
                            "data": {
                                "session_id": state["session_id"],
                                "summary": state.get("report", {}).get("interview_summary", ""),
                                "report": state.get("report", {}),
                            },
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                    break

    except WebSocketDisconnect:
        service.mark_disconnect(session_id)
    finally:
        heartbeat_task.cancel()
        manager.disconnect(user_id)
        service.cleanup_expired(ttl_minutes=15)


async def _heartbeat(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(30)
        await websocket.send_json(
            {
                "type": WebSocketMessageType.PING.value,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )


async def _push_latest_interviewer_message(websocket: WebSocket, state: dict) -> None:
    if not state.get("message_history"):
        return
    latest = state["message_history"][-1]
    if latest.get("role") != "interviewer":
        return

    content = str(latest.get("content", ""))
    for ch in content:
        await websocket.send_json(
            {
                "type": WebSocketMessageType.TOKEN.value,
                "data": ch,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    await websocket.send_json(
        {
            "type": WebSocketMessageType.MESSAGE.value,
            "data": {
                "content": content,
                "stage": latest.get("stage"),
                "question_index": latest.get("question_index", 0),
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


def _parse_client_payload(raw: str) -> dict:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"type": "message", "message": raw}
