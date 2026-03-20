# websocket.py

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedOK

import index

router = APIRouter()

# =============================
# -------- CONNECTIONS --------
# =============================

active_connections = set()

# =============================
# --------- WEBSOCKET ---------
# =============================

@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = str(id(websocket))

    active_connections.add(user_id)
    logging.info(f"Connected: {user_id} | Active: {len(active_connections)}")

    try:
        # Load data safely
        try:
            index.load_data_realtime()
        except Exception as e:
            logging.warning(f"Data load issue: {e}")

        lang = "en"

        initial_message = index.BOT_DATA.get(
            "initial_message", {}
        ).get(lang, "Hello! How can I help?")

        await websocket.send_json({
            "reply": initial_message,
            "carousel": None,
            "suggestions": index.get_dynamic_suggestions(user_id, "greeting", lang)
        })

        # =============================
        # -------- MAIN LOOP ----------
        # =============================

        while True:
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=300  # 5 min idle timeout
                )
            except asyncio.TimeoutError:
                logging.info(f"Timeout: {user_id}")
                break

            try:
                bot = index.generate_bot_response(user_id, msg)
            except Exception as e:
                logging.error(f"Bot error: {e}")
                bot = {
                    "reply": "Something went wrong. Please try again.",
                    "carousel": None,
                    "suggestions": []
                }

            await asyncio.sleep(0.2)
            await websocket.send_json(bot)

    # =============================
    # -------- CLEAN EXIT ---------
    # =============================

    except (WebSocketDisconnect, ConnectionClosedOK):
        logging.info(f"Disconnected cleanly: {user_id}")

    except Exception as e:
        logging.error(f"WebSocket critical error: {e}")

    finally:
        active_connections.discard(user_id)
        logging.info(f"Removed: {user_id} | Active: {len(active_connections)}")

        try:
            await websocket.close()
        except:
            pass
