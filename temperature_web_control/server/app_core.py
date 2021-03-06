import asyncio
import time
from functools import wraps, partial
from logging import Logger
from collections import deque

from temperature_web_control.driver import load_driver
from temperature_web_control.model.program import Program, actions
from temperature_web_control.server.program_manager import ProgramManager
from temperature_web_control.utils import Config


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
            if 'temperature' in status:
                self.temperatures[dev].append(status['temperature'])
            else:
                self.temperatures[dev].append(None)

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
            'program_error': {}
        }
        self.last_status = {}

        self.monitor_running = False
        self.monitor_task = None
        self.monitor_last_update = 0

        self._load_devices()
        self._load_programs()

        self.program_manager = ProgramManager(config, self.dev_instances,
                                              lambda: asyncio.gather(self.update_status_and_fire_event(),
                                                                     self.fire_control_changed_event()),
                                              self.fire_program_error,
                                              logger)
        history_len = config.get('history_length', default=1000)
        self.history = TemperatureHistory(history_len, self.dev_instances)
        self.subscribe_to('status_available', self.history, self.history.status_update_handler)

    def _load_devices(self):
        dev_instances = {}
        for dev in self.config.get('devices'):
            self.dev_instances[dev["name"]] = load_driver(dev, self.logger)

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
        self.logger.info(f"AppCore: {subscriber} subscribes to {event_name}, group id {group_id}.")
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
        self.logger.info(f"AppCore: {subscriber} unsubscribes to all events.")
        for event, subscriber_grps in self.subscribers.items():
            for subscriber_grp in subscriber_grps.values():
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

        tasks = []
        for subscriber_grp in self.subscribers[event].values():
            tasks.append(asyncio.create_task(subscriber_grp.message_handler(subscriber_grp.subscribers, message)))

        if tasks:
            (done, pending) = await asyncio.wait(tasks, timeout=10)

            if pending:
                for unfinished in pending:
                    unfinished.cancel()
                    await self.fire_program_error(f"Timeout executing event handler {unfinished}")

    def start_monitoring(self):
        def done_handler(task):
            try:
                task.result()
            except asyncio.CancelledError:
                pass  # Task cancellation should not be logged as an error.
            except Exception as e:
                self.logger.error(f'AppCore: Monitoring ended unexpectedly with error:')
                self.logger.exception(e)

        self.logger.info("AppCore: Monitor start")
        self.monitor_task = asyncio.create_task(self.monitor_status())
        asyncio.create_task(self.check_monitor_alive())
        self.monitor_running = True
        self.monitor_task.add_done_callback(done_handler)

    async def monitor_status(self):
        interval = self.config.get('update_interval', default=5)
        while True:
            await asyncio.sleep(interval)
            await self.update_status_and_fire_event()
            self.monitor_last_update = time.time()

    async def check_monitor_alive(self):
        interval = self.config.get('update_interval', default=5)
        skipped_cycle = 0
        last_update = time.time()

        await asyncio.sleep(interval)
        while True:
            if not self.monitor_running:
                return

            await asyncio.sleep(interval)

            if self.monitor_last_update > last_update:
                last_update = self.monitor_last_update
                skipped_cycle = 0
            else:
                skipped_cycle += 1
                if skipped_cycle >= 5:
                    self.logger.error("AppCore: Monitoring routine got stuck. Probably due to unresponsive drivers. "
                                      "Restarting.")
                    await self.fire_program_error(f"Monitoring routine got stuck. Probably due to unresponsive drivers. "
                                      "Restarting.")
                    self.monitor_task.cancel()
                    self.dev_instances = {}
                    self._load_devices()
                    self.start_monitoring()
                    return

    async def fire_program_error(self, error):
        self.logger.error("AppCore: Received error, broadcasting to clients...")
        if  isinstance(error, Exception):
            self.logger.exception(error)
            await self._fire_event('program_error', {'error': str(error)})
        else:
            self.logger.error(error)
            await self._fire_event('program_error', {'error': error})

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
        self.logger.debug(f"AppCore: Received event: request_status.")
        if self.last_status:
            status = self.last_status
        else:
            status = await self.acquire_status()
        await self._return_ok(callback, {'status': status})

    async def _return_error(self, callback, error_msg):
        if callback:
            await callback({"result": "error", "error_msg": error_msg})

    async def _return_ok(self, callback, message=None):
        if callback:
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
            self.logger.error(f"AppCore: Exception caught while gather status of {dev.name}:")
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
            self.logger.debug(f"AppCore: Load program '{program.name}'")

    async def on_predefined_program_run_event(self, event, callback):
        self.logger.debug(f"AppCore: Received event: run_predefined_program.")
        if event["program"] not in self.programs:
            await self._return_error(callback, "Unknown program.")

        program = self.programs[event["program"]]

        self.program_manager.create_program_task(program)
        await self._return_ok(callback)

    async def on_abort_program_event(self, event, callback):
        self.logger.debug(f"AppCore: Received event: abort_program.")
        self.program_manager.abort_program(event["program"])
        await self._return_ok(callback)

    async def on_current_programs_event(self, event, callback):
        self.logger.debug(f"AppCore: Received event: current_program.")
        programs = self.program_manager.current_programs
        await self._return_ok(callback, {'current_programs':
                                             [program.name for program in programs] })

    async def on_list_program_event(self, event, callback):
        self.logger.debug(f"AppCore: Received event: list_program.")
        await self._return_ok(callback, {'programs': [
            {
                'name': program.name,
                'description': program.description
            } for program in self.programs.values()
        ]})

    async def on_fetch_history_event(self, event, callback):
        self.logger.debug(f"AppCore: Received event: fetch_history.")
        await self._return_ok(callback, {'data': self.history.dump_data()})

    async def on_list_actions_event(self, event, callback):
        self.logger.debug(f"AppCore: Received event: list_actions.")
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

        self.logger.debug(f"AppCore: Received event: run_program.")

        if 'steps' not in event:
            await self._return_error(callback, "Malformed message.")
            return

        if 'name' not in event:
            event['name'] = str(uuid.uuid1())

        if 'description' not in event:
            event['description'] = ''

        try:
            program = Program.from_dict(event)
            self.logger.debug(f"AppCore: Program: {program.to_dict()}")
        except (KeyError, TypeError) as e:
            await self._return_error(callback, f"Syntax error in program {event['name']}: {str(e)}")
            return

        self.program_manager.create_program_task(program)
        await self._return_ok(callback, {'name': event['name']})
        await self.update_status_and_fire_event()
        await self.fire_control_changed_event()

    async def on_edit_program_event(self, event, callback):
        self.logger.debug(f"AppCore: Received event: edit_program.")
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
        self.logger.debug(f"AppCore: Received event: standby_device.")
        try:
            device = self.dev_instances[event['device']]
            device.control_enabled = False
            await self.update_status_and_fire_event()
            await self._return_ok(callback)
        except (KeyError, TypeError) as e:
            await self._return_error(callback, e)



