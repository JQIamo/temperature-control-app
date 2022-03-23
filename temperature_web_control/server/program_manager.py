import asyncio
from collections import deque

from temperature_web_control.model.program import Program
from temperature_web_control.model.temperature_monitor import TemperatureMonitor
from temperature_web_control.utils import Config


def float_range(start, stop, step):
  while start < stop:
    yield float(start)
    start += step


class TemperatureProgramException(Exception):
    pass


class ProgramManager:
    def __init__(self, config: Config, device_instances, update_state_callback, error_callback):
        self.config = config
        self.dev_instances = device_instances
        self.current_programs = []
        self.current_step = {}
        self.current_dev_program = {}
        self.current_dev_action = {}
        self.current_program_task = {}
        self.occupied_devices = []

        self.update_state_callback = update_state_callback
        self.error_callback = error_callback

    async def abort_program(self, program_name):
        try:
            program = next(filter(lambda p: p.name == program_name, self.current_programs))
        except StopIteration as e:
            return

        if not self.current_program_task[program_name].cancelled():
            self.current_program_task[program_name].cancel()
        else:
            self.current_program_task[program_name] = None

    def create_program_task(self, program: Program):
        if program in self.current_programs:
            raise TemperatureProgramException(f"Program {program.name} is running.")

        self.current_program_task[program.name] = None
        self.current_program_task[program.name] = asyncio.create_task(self.run_program(program))

    async def run_program(self, program: Program):
        try:
            if program in self.current_programs:
                raise TemperatureProgramException(f"Program {program.name} is running.")

            if not program.occupied_device:
                raise TemperatureProgramException(f"No device specified.")

            for dev in program.occupied_device:
                if dev not in self.dev_instances:
                    raise TemperatureProgramException(
                        f"Device {dev} doesn't exist.")

                if dev in self.occupied_devices:
                    raise TemperatureProgramException(
                        f"Program {program.name} requires device {dev}, but it is occupied by program "
                        f"{self.current_dev_program[dev]}.")

                self.occupied_devices.append(dev)
                self.current_dev_program[dev] = program

            self.current_programs.append(program)

            if len(program.steps) == 0:
                return

            pointer = 0
            step_tasks = []

            try:
                loop_counters = {}
                while pointer < len(program.steps):
                    step = program.steps[pointer]
                    self.current_step[program.name] = step

                    occupied_device_in_step = []
                    coroutines = []

                    for action in step:
                        device = None
                        if action.device:
                            if action.device in occupied_device_in_step:
                                raise TemperatureProgramException(
                                    "Only one action can be performed on one device at each step.")

                            device = self.dev_instances[action.device]
                            occupied_device_in_step.append(action.device)
                            self.current_dev_action[action.device] = action

                        if action.name == "CHANGE":
                            coroutines.append(self.change_temperature(device,
                                                               float(action.params['SETPOINT'])))

                        if action.name == "LINEAR_RAMP":
                            coroutines.append(self.linear_ramp(device,
                                                               float(action.params['TARGET_TEMP']),
                                                               float(action.params['RATE'])))

                        elif action.name == "SOAK":
                            coroutines.append(asyncio.sleep(float(action.params['TIME']) * 60))

                        elif action.name == "LOOP":
                            target_action = action.params['GOTO']

                            if not (0 <= target_action < len(program.steps)):
                                raise TemperatureProgramException(
                                    "Loop target out range.")

                            loop_times = int(action.params['TIMES'])
                            if pointer not in loop_counters:
                                loop_counters[pointer] = 0
                            if loop_counters[pointer] < loop_times:
                                loop_counters[pointer] += 1
                                pointer = target_action - 1  # there a +1 at the end of the while body
                            else:
                                del loop_counters[pointer]

                        elif action.name == "STANDBY":
                            device.control_enabled = False

                    # let user know the program is running before doing time-consuming jobs
                    await self.update_state_callback()

                    # Why not gather coroutines instead, see interesting discussion
                    # https://stackoverflow.com/a/59074112/1584825
                    step_tasks = [asyncio.create_task(coro) for coro in coroutines]
                    await asyncio.gather(*step_tasks)

                    pointer += 1

            except asyncio.CancelledError:
                await self.update_state_callback()
            finally:
                for t in step_tasks:
                    t.cancel()

                self.current_programs.remove(program)
                del self.current_step[program.name]

                for dev in program.occupied_device:
                    self.occupied_devices.remove(dev)
                    del self.current_dev_program[dev]
                    del self.current_dev_action[dev]

                await self.update_state_callback()
        except Exception as e:
            await self.error_callback(e)

    async def linear_ramp(self, device: TemperatureMonitor, target, rate):
        try:
            ramp_interval = self.config.get('ramp_interval', default=1)  # in minutes
            last_temp = device.temperature
            delta = target - last_temp
            if delta < 0:
                rate = -1 * abs(rate)
            else:
                rate = abs(rate)

            ramp_time = delta / rate  # in minutes
            device.control_enabled = True

            for i in float_range(0, ramp_time, ramp_interval):
                await asyncio.sleep(0)  # A chance to stop the program

                next_temp = ramp_interval * rate + last_temp

                if (delta > 0 and next_temp > target) or (delta < 0 and next_temp < target):
                    next_temp = target

                if int(next_temp * 10) != int(last_temp * 10):
                    device.setpoint = next_temp
                last_temp = next_temp
                await asyncio.sleep(ramp_interval * 60)
        except asyncio.CancelledError:
            pass

    async def change_temperature(self, device: TemperatureMonitor, target):
        tolerance = self.config.get('temperature_tolerance', default=1)  # in degrees

        device.control_enabled = True
        device.setpoint = target

        average_length = 12
        average_deque = deque(maxlen=average_length)

        while True:
            await asyncio.sleep(5)
            average_deque.append(device.temperature)

            avg = sum(average_deque) / len(average_deque)

            if target - tolerance < avg < target + tolerance:
                break
