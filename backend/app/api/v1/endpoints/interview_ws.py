from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app.core.database import SessionLocal
from app.schemas.interview import WebSocketMessageType
from app.services.interview_service import interview_service

router = APIRouter()
service = interview_service
logger = logging.getLogger(__name__)


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

    reconnecting = service.is_recently_disconnected(session_id)

    await manager.connect(user_id, websocket)
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        async with SessionLocal() as db:
            session = await service.get_owned_session(db=db, session_id=session_id, user_id=user_id)
            before_stage = session.current_stage or "WELCOME"
            state = await service.ensure_welcome_turn(db=db, session=session)
            trace_id = str(state.get("trace_id") or "")

            logger.info(
                "interview_ws_connected session_id=%s user_id=%s trace_id=%s reconnecting=%s stage=%s",
                session_id,
                user_id,
                trace_id,
                reconnecting,
                state["current_stage"].value,
            )

            if reconnecting:
                await websocket.send_json(
                    {
                        "type": WebSocketMessageType.STATE_CHANGE.value,
                        "data": {
                            "old_stage": before_stage,
                            "new_stage": state["current_stage"].value,
                            "reason": "reconnect_restore",
                        },
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

            await _push_latest_interviewer_message(websocket, state)

            while True:
                raw = await websocket.receive_text()
                payload = _parse_client_payload(raw)
                payload_type = str(payload.get("type") or "").strip()

                if payload_type == WebSocketMessageType.PONG.value:
                    continue

                if payload_type == WebSocketMessageType.END_INTERVIEW.value:
                    message = "结束面试"
                elif payload_type == WebSocketMessageType.SKIP.value:
                    message = "跳过当前问题"
                else:
                    message = str(payload.get("message") or "").strip()

                if not message:
                    continue

                old_stage = state["current_stage"].value
                logger.info(
                    "interview_ws_message_received session_id=%s user_id=%s trace_id=%s stage=%s type=%s",
                    session_id,
                    user_id,
                    trace_id,
                    old_stage,
                    payload_type or "message",
                )

                stream_queue: asyncio.Queue[str] = asyncio.Queue()
                streamed_any = False
                loop = asyncio.get_running_loop()

                def _on_token(chunk: str) -> None:
                    if not chunk:
                        return
                    loop.call_soon_threadsafe(stream_queue.put_nowait, chunk)

                state_task = asyncio.create_task(
                    service.handle_candidate_message(
                        db=db,
                        session=session,
                        message=message,
                        token_callback=_on_token,
                    )
                )

                while not state_task.done():
                    try:
                        chunk = await asyncio.wait_for(stream_queue.get(), timeout=0.05)
                    except TimeoutError:
                        continue
                    streamed_any = True
                    for ch in str(chunk):
                        await websocket.send_json(
                            {
                                "type": WebSocketMessageType.TOKEN.value,
                                "data": ch,
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        )

                state = await state_task

                while not stream_queue.empty():
                    chunk = stream_queue.get_nowait()
                    streamed_any = True
                    for ch in str(chunk):
                        await websocket.send_json(
                            {
                                "type": WebSocketMessageType.TOKEN.value,
                                "data": ch,
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        )

                new_stage = state["current_stage"].value
                if old_stage != new_stage:
                    logger.info(
                        "interview_ws_stage_changed session_id=%s user_id=%s trace_id=%s old_stage=%s new_stage=%s",
                        session_id,
                        user_id,
                        trace_id,
                        old_stage,
                        new_stage,
                    )
                    await websocket.send_json(
                        {
                            "type": WebSocketMessageType.STATE_CHANGE.value,
                            "data": {"old_stage": old_stage, "new_stage": new_stage},
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )

                if not streamed_any:
                    await _push_latest_interviewer_message(websocket, state)
                else:
                    await _push_latest_interviewer_message_without_tokens(websocket, state)

                if state["status"] == "ENDED":
                    logger.info(
                        "interview_ws_report_ready session_id=%s user_id=%s trace_id=%s",
                        session_id,
                        user_id,
                        trace_id,
                    )

                    await service.generate_report_for_session(db=db, session=session, state=state)
                    await websocket.send_json(
                        jsonable_encoder(
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
                    )
                    break

    except WebSocketDisconnect:
        logger.info("interview_ws_disconnected session_id=%s user_id=%s", session_id, user_id)
        service.mark_disconnect(session_id)
    except Exception:
        logger.exception("interview_ws_failed session_id=%s user_id=%s", session_id, user_id)
        try:
            await websocket.send_json(
                {
                    "type": WebSocketMessageType.ERROR.value,
                    "data": {"message": "interview websocket internal error"},
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        except Exception:
            pass
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


async def _push_latest_interviewer_message_without_tokens(websocket: WebSocket, state: dict) -> None:
    if not state.get("message_history"):
        return
    latest = state["message_history"][-1]
    if latest.get("role") != "interviewer":
        return

    await websocket.send_json(
        {
            "type": WebSocketMessageType.MESSAGE.value,
            "data": {
                "content": str(latest.get("content", "")),
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
