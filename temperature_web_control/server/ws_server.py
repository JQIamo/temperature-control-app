import json
import asyncio
import signal
from functools import wraps, partial
from logging import Logger

import websockets


class WebSocketServer:
    def __init__(self, bind_addr, port, logger):
        self.bind_addr = bind_addr
        self.port = port
        self.active_ws = []
        self.event_handlers = {}
        self.logger: Logger = logger

    def register_event_handler(self, event, handler):
        if event not in self.event_handlers:
            self.event_handlers[event] = [handler]
        else:
            self.event_handlers[event].append(handler)

    async def handler(self, websocket):
        self.logger.info(f"WSServer: New connection from "
                         f"{websocket.remote_address[0]}:{websocket.remote_address[1]}.")
        self.active_ws.append(websocket)
        try:
            async for message in websocket:
                self.logger.info(f"WSServer: Incoming message from "
                                  f"{websocket.remote_address[0]}:{websocket.remote_address[1]}.")
                self.logger.info(message)

                event = json.loads(message)

                event_type = event['event']
                if event_type in self.event_handlers:
                    event['_client_ws'] = websocket
                    await asyncio.gather(*[ handler(event, partial(self.send_event, websocket, event_type))
                                           for handler in self.event_handlers[event_type] ])
        except (websockets.ConnectionClosed, websockets.ConnectionClosedOK, websockets.ConnectionClosedError):
            self.logger.info(f"WSServer: Connection to client "
                              f"{websocket.remote_address[0]}:{websocket.remote_address[1]} closed.")
        finally:
            self.logger.info(f"WSServer: Remove client "
                             f"{websocket.remote_address[0]}:{websocket.remote_address[1]} from the broadcast list.")
            self.active_ws.remove(websocket)
            if 'disconnected' in self.event_handlers:
                event = {
                    'event': 'disconnected',
                    '_client_ws': websocket
                }

                await asyncio.gather(*[handler(event, None) for handler in self.event_handlers['disconnected']])

    async def send(self, websocket, message_dict):
        try:
            self.logger.debug(f"Send to : {websocket}" + json.dumps(message_dict))
            await websocket.send(json.dumps(message_dict))
        except websockets.ConnectionClosed:
            pass

    async def send_event(self, websocket, event, message_dict):
        try:
            message_dict.update({ 'event': event })
            self.logger.debug(f"WSServer: Send to : {websocket}" + json.dumps(message_dict))
            await websocket.send(json.dumps(message_dict))
        except websockets.ConnectionClosed:
            pass

    async def broadcast(self, websocket_clients, message_dict):
        self.logger.debug("Broadcast: " + json.dumps(message_dict))
        websockets.broadcast(websocket_clients, json.dumps(message_dict))

    async def serve_until_exit(self):
        self.logger.info(f"WSServer: Websocket server running at ws://{self.bind_addr}:{self.port}")

        loop = asyncio.get_running_loop()
        stop = loop.create_future()
        loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)

        async with websockets.serve(self.handler, self.bind_addr, self.port, ping_timeout=20, ping_interval=5):
            await stop
