# websocket.py
# ============================================================
# WEBSOCKET ENDPOINT — Real-time chat with the AI chatbot
# ============================================================

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedOK

import index

router = APIRouter()
logger = logging.getLogger("WebSocket")

# ============================================================
# CONNECTION REGISTRY
# ============================================================

active_connections: set = set()


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Handles the full WebSocket lifecycle:
    - Accept connection
    - Send initial greeting
    - Process messages in a loop
    - Clean up on disconnect or timeout
    """
    await websocket.accept()
    user_id = str(id(websocket))
    active_connections.add(user_id)
    logger.info(f"[CONNECTED] user_id={user_id} | active={len(active_connections)}")

    try:
        # ------------------------------------------------
        # LOAD LATEST DATA FROM DB
        # ------------------------------------------------
        _safe_load_data(user_id)

        # ------------------------------------------------
        # SEND INITIAL GREETING
        # ------------------------------------------------
        lang = "en"
        initial_message = (
            index.BOT_DATA.get("initial_message", {}).get(lang)
            or "Hello! How can I help you today?"
        )
        suggestions = _safe_get_suggestions(user_id, "greeting", lang)

        await websocket.send_json({
            "reply": initial_message,
            "carousel": None,
            "suggestions": suggestions
        })

        # ------------------------------------------------
        # MAIN MESSAGE LOOP
        # ------------------------------------------------
        while True:
            msg = await _receive_with_timeout(websocket, user_id, timeout=300)

            if msg is None:
                # Timeout reached — close gracefully
                break

            msg = msg.strip()
            if not msg:
                continue  # Ignore blank messages

            response = _safe_generate_response(user_id, msg)

            # Small delay prevents flooding on rapid-fire sends
            await asyncio.sleep(0.15)
            await websocket.send_json(response)

    # ------------------------------------------------
    # CLEAN DISCONNECT HANDLING
    # ------------------------------------------------
    except (WebSocketDisconnect, ConnectionClosedOK):
        logger.info(f"[DISCONNECTED] user_id={user_id} (clean)")

    except Exception as e:
        logger.error(f"[ERROR] user_id={user_id} | {type(e).__name__}: {e}")

    finally:
        active_connections.discard(user_id)
        logger.info(f"[REMOVED] user_id={user_id} | active={len(active_connections)}")
        await _safe_close(websocket)


# ============================================================
# PRIVATE HELPERS
# ============================================================

async def _receive_with_timeout(
    websocket: WebSocket,
    user_id: str,
    timeout: int
) -> str | None:
    """
    Waits for a message from the client with a timeout.
    Returns the message text, or None on timeout.
    """
    try:
        return await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.info(f"[TIMEOUT] user_id={user_id} — idle for {timeout}s")
        return None


def _safe_load_data(user_id: str) -> None:
    """Loads realtime data from the database, suppressing errors."""
    try:
        index.load_data_realtime()
    except Exception as e:
        logger.warning(f"[DATA LOAD] user_id={user_id} | {e}")


def _safe_get_suggestions(user_id: str, context: str, lang: str) -> list:
    """Fetches dynamic suggestions, returning [] on error."""
    try:
        return index.get_dynamic_suggestions(user_id, context, lang)
    except Exception as e:
        logger.warning(f"[SUGGESTIONS] user_id={user_id} | {e}")
        return []


def _safe_generate_response(user_id: str, msg: str) -> dict:
    """
    Calls the bot response generator.
    Returns a safe error response on unexpected failure.
    """
    try:
        return index.generate_bot_response(user_id, msg)
    except Exception as e:
        logger.error(f"[BOT ERROR] user_id={user_id} | {type(e).__name__}: {e}")
        return {
            "reply": "Hmm, something went wrong on my end. Please try again.",
            "carousel": None,
            "suggestions": []
        }


async def _safe_close(websocket: WebSocket) -> None:
    """Attempts to close the WebSocket, silently ignoring errors."""
    try:
        await websocket.close()
    except Exception:
        pass
