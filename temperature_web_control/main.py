import asyncio
import logging
import argparse
import threading

from temperature_web_control.server.app_core import TemperatureAppCore
from temperature_web_control.server.ws_server import WebSocketServer
from temperature_web_control.server.http_server import serve_http
from temperature_web_control.utils import Config
from temperature_web_control.plugin import plugins

config = {}
app_manager: TemperatureAppCore = None
logger = None

async def run_ws_server():
    global app_manager
    assert isinstance(app_manager, TemperatureAppCore)

    ws_server = WebSocketServer("", 3001, logger)

    async def subscribe_event_handler(event, handler):
        app_manager.subscribe_to(event['subscribe_to'],
                                 event['_client_ws'],
                                 ws_server.broadcast,
                                 ws_server)

    async def disconnected_event_handler(event, handler):
        app_manager.unsubscribe_to_all(event['_client_ws'])

    ws_server.register_event_handler("subscribe", subscribe_event_handler)
    ws_server.register_event_handler("disconnected", disconnected_event_handler)

    app_event_handlers = app_manager.get_event_handlers()
    for name, handler in app_event_handlers.items():
        ws_server.register_event_handler(name, handler)

    await ws_server.serve_until_exit()


def run_http_server():
    global config, logger
    import json

    assert isinstance(logger, logging.Logger)

    def get_websocket(request):
        if 'websocket_access_addr' in config:
            ret = json.dumps({
                'websocket_addr': config['websocket_access_addr']
            })
        else:
            ret = json.dumps({
                'websocket_addr': "ws://localhost:3001"
            })

        return 200, 'application/json', ret

    serve_http("", 8000, { 'websocket' : get_websocket }, logger)


async def main():
    global config, app_manager, logger

    logger = logging.getLogger("root")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s %(levelname)s][%(filename)s:%(lineno)d] %(message)s', "%b %d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    parser = argparse.ArgumentParser(description="Temperature web control app.")

    parser.add_argument("-c", "--config", dest="config", type=str,
                        help="path to the config yaml file")
    args = parser.parse_args()

    config = Config(args.config)

    app_manager = TemperatureAppCore(config, logger)
    http_thread = threading.Thread(target=run_http_server)

    plugin_coroutine = []
    for plugin in plugins.values():
        plugin_run = plugin.initialize(config, app_manager, logger)
        if plugin_run:
            plugin_coroutine.append(plugin_run)

    try:
        coroutines = [run_ws_server(), app_manager.monitor_status()] + plugin_coroutine
        await asyncio.gather(*coroutines)
    except KeyboardInterrupt:
        pass
    #http_thread.start()
    #http_thread.join()