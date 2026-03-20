# websocket.py

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Import logic from index
import index

router = APIRouter()

# =============================
# --------- WEB SOCKETS --------
# ==============================

@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = str(id(websocket))

    index.load_data_realtime()

    lang = "en"
    initial_message = index.BOT_DATA.get(
        "initial_message", {}
    ).get(lang, "Hello! How can I help?")

    await websocket.send_json({
        "reply": initial_message,
        "carousel": None,
        "suggestions": index.get_dynamic_suggestions(user_id, "greeting", lang)
    })

    try:
        while True:
            msg = await websocket.receive_text()

            bot = index.generate_bot_response(user_id, msg)

            await asyncio.sleep(0.2)
            await websocket.send_json(bot)

    except WebSocketDisconnect:
        logging.info(f"User disconnected: {user_id}")

    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass
