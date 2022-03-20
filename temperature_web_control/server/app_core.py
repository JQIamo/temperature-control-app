import asyncio
import time
from functools import wraps, partial
from logging import Logger
from collections import deque

from temperature_web_control.driver import load_driver
from temperature_web_control.model.program import Program, actions
from temperature_web_control.model.temperature_monitor import TemperatureMonitor
from temperature_web_control.server.program_manager import ProgramManager
from temperature_web_control.server.utils import Config


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


class SubscriberGroup:
    def __init__(self, group_id, subscribers, message_handler):
        self.group_id = group_id
        self.subscribers = subscribers
        self.message_handler = message_handler


class TemperatureHistory:
    def __init__(self, length, devices):
        self.times = {}
        self.temperatures = {}
        for device in devices:
            self.times[device] = deque(maxlen=length)
            self.temperatures[device] = deque(maxlen=length)

    async def status_update_handler(self, subscribers, status_dict):
        dev_status = status_dict['status']

        for dev, status in dev_status.items():
            self.times[dev].append(time.time())
            self.temperatures[dev].append(status['temperature'])

    def dump_data(self):
        ret = {}
        for dev in self.times.keys():
            ret[dev] = {}
            ret[dev]['time'] = list(self.times[dev])
            ret[dev]['temperature'] = list(self.temperatures[dev])

        return ret


class TemperatureAppCore:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
        self.dev_instances = {}
        self.programs = {}
        self.subscribers = {
            'status_available': {},
            'control_changed': {},
        }
        self.last_status = {}

        self._load_devices()
        self._load_programs()

        self.program_manager = ProgramManager(config, self.dev_instances,
                                              lambda: asyncio.gather(self.update_status_and_fire_event(),
                                                                     self.fire_control_changed_event())
                                              )
        history_len = config.get('history_length', default=1000)
        self.history = TemperatureHistory(history_len, self.dev_instances)
        self.subscribe_to('status_available', self.history, self.history.status_update_handler)

    def _load_devices(self):
        dev_instances = {}
        for dev in self.config.get('devices'):
            self.dev_instances[dev["name"]] = load_driver(dev)

        return dev_instances

    def get_event_handlers(self):
        # The events that can be handled by this class
        event_handlers = {
            'request_status': self.on_request_status_event,
            'run_predefined_program': self.on_predefined_program_run_event,
            'run_program': self.on_run_program_event,
            'abort_program': self.on_abort_program_event,
            'edit_program': self.on_edit_program_event,
            'list_programs': self.on_list_program_event,
            'list_actions': self.on_list_actions_event,
            'current_programs': self.on_current_programs_event,
            'fetch_history': self.on_fetch_history_event,
            'standby_device': self.on_standby_device_event,
        }
        return event_handlers

    def subscribe_to(self, event_name, subscriber, handler, group_id=None):
        if event_name in self.subscribers:
            if group_id:
                if group_id not in self.subscribers[event_name]:
                    self.subscribers[event_name][group_id] = SubscriberGroup(group_id, [subscriber], handler)
                else:
                    self.subscribers[event_name][group_id].subscribers.append(subscriber)
                    self.subscribers[event_name][group_id].message_handler = handler
            else:
                self.subscribers[event_name][subscriber] = SubscriberGroup(subscriber, [subscriber], handler)

    def unsubscribe_to_all(self, subscriber):
        for event, subscriber_grp in self.subscribers:
            if subscriber in subscriber_grp.subscribers:
                subscriber_grp.subscribers.remove(subscriber)
            self._purge_empty_subscriber_groups(event)

    def _purge_empty_subscriber_groups(self, event_name):
        grp_keys = list(self.subscribers[event_name].keys())
        for key in grp_keys:
            if len(self.subscribers[event_name][key].subscribers) == 0:
                del self.subscribers[event_name][key]

    async def _fire_event(self, event, message):
        message['event'] = event
        if event not in self.subscribers:
            return

        for subscriber_grp in self.subscribers[event].values():
            await subscriber_grp.message_handler(subscriber_grp.subscribers, message)

    async def monitor_status(self):
        self.logger.info("AppManager: Monitor start")
        interval = self.config.get('update_interval', default=5)
        try:
            while True:
                await asyncio.sleep(interval)
                await self.update_status_and_fire_event()

        except KeyboardInterrupt:
            pass

    async def update_status_and_fire_event(self):
        status = await self.acquire_status()
        await self._fire_event('status_available', {'status': status})

    async def fire_control_changed_event(self):
        await self._fire_event('control_changed', {})

    async def acquire_status(self):
        name_list = []
        dev_list = []
        for name, dev in self.dev_instances.items():
            name_list.append(name)
            dev_list.append(dev)

        device_status_list = await asyncio.gather(*[self.gather_dev_status(dev) for dev in dev_list])

        status = {name: status for name, status in zip(name_list, device_status_list)}
        self.last_status = status

        return status

    async def on_request_status_event(self, event, callback):
        if self.last_status:
            status = self.last_status
        else:
            status = await self.acquire_status()
        await self._return_ok(callback, {'status': status})

    async def _return_error(self, callback, error_msg):
        await callback({"result": "error", "error_msg": error_msg})

    async def _return_ok(self, callback, message=None):
        result = {"result": "ok"}
        if message:
            result.update(message)
        await callback(result)

    @async_wrap
    def gather_dev_status(self, dev):
        current_action = self.program_manager.current_dev_action[dev.name].name \
            if dev.name in self.program_manager.current_dev_action else ""

        current_program = self.program_manager.current_dev_program[dev.name].name \
            if dev.name in self.program_manager.current_dev_program else ""

        try:
            return {
                'name': dev.name,
                'temperature': dev.temperature,
                'control_enabled': dev.control_enabled,
                'current_program': current_program,
                'current_action': current_action,
                'setpoint': dev.setpoint,
                'status': 'ok'
            }
        except Exception as e:
            self.logger.error(f"Exception caught while gather status of {dev.name}:")
            self.logger.exception(e)
            return {
                'status': 'error',
                'error_msg': str(e)
            }

    def _load_programs(self):
        programs = self.config.get("programs")

        if not self.config.get("programs"):
            return

        for program_dict in programs:
            program = Program.from_dict(program_dict)
            self.programs[program.name] = program
            self.logger.debug(f"Load program '{program.name}'")

    async def on_predefined_program_run_event(self, event, callback):
        if event["program"] not in self.programs:
            await self._return_error(callback, "Unknown program.")

        program = self.programs[event["program"]]

        self.program_manager.create_program_task(program)
        await self._return_ok(callback)
        await self.update_status_and_fire_event()
        await self.fire_control_changed_event()

    async def on_abort_program_event(self, event, callback):
        await self.program_manager.abort_program(event["program"])
        await self.fire_control_changed_event()
        await self._return_ok(callback)

    async def on_current_programs_event(self, event, callback):
        programs = self.program_manager.current_programs
        await self._return_ok(callback, {'current_programs':
                                             [program.name for program in programs] })

    async def on_list_program_event(self, event, callback):
        await self._return_ok(callback, {'programs': [
            {
                'name': program.name,
                'description': program.description
            } for program in self.programs.values()
        ]})

    async def on_fetch_history_event(self, event, callback):
        await self._return_ok(callback, {'data': self.history.dump_data()})

    async def on_list_actions_event(self, event, callback):
        await self._return_ok(
            callback,
            {
                "actions": {
                    name: {
                        "name": action.name,
                        "display_name": action.display_name,
                        "status_word": action.status_word,
                        "description": action.description,
                        "params_desc": action.params_desc,
                        "need_device": action.need_device,
                        "standalone": action.standalone,
                        "attention_level": action.attention_level
                    } for name, action in actions.items()
                }
            })

    async def on_run_program_event(self, event, callback):
        import uuid

        if 'steps' not in event:
            await self._return_error(callback, "Malformed message.")
            return

        if 'name' not in event:
            event['name'] = str(uuid.uuid1())

        if 'description' not in event:
            event['description'] = ''

        try:
            program = Program.from_dict(event)
        except (KeyError, TypeError) as e:
            await self._return_error(callback, f"Syntax error in program {event['name']}: {str(e)}")
            return

        self.program_manager.create_program_task(program)
        await self._return_ok(callback, {'name': event['name']})
        await self.update_status_and_fire_event()
        await self.fire_control_changed_event()

    async def on_edit_program_event(self, event, callback):
        if 'name' not in event:
            await self._return_error(callback, f"Name of the program unspecified.")
            return

        try:
            program = Program.from_dict(event)
            self.programs[program.name] = program

            program_list = [program.to_dict() for program in self.programs]
            self.config.set('programs', value=program_list)
            self.config.write()
        except (KeyError, TypeError) as e:
            await self._return_error(callback, f"Syntax error in program {event['name']}: {str(e)}")
            return

    async def on_standby_device_event(self, event, callback):
        device = self.dev_instances[event['device']]
        device.control_enabled = False
        await self.update_status_and_fire_event()
        await self._return_ok(callback)



