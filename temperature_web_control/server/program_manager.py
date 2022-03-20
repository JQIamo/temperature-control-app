import asyncio
from collections import deque

from temperature_web_control.model.program import Program
from temperature_web_control.model.temperature_monitor import TemperatureMonitor
from temperature_web_control.server.utils import Config


def float_range(start, stop, step):
  while start < stop:
    yield float(start)
    start += step


class TemperatureProgramException(Exception):
    pass


class ProgramManager:
    def __init__(self, config: Config, device_instances, update_state_callback):
        self.config = config
        self.dev_instances = device_instances
        self.current_programs = []
        self.current_step = {}
        self.current_dev_program = {}
        self.current_dev_action = {}
        self.current_program_task = {}
        self.occupied_devices = []

        self.update_state_callback = update_state_callback


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
        if program in self.current_programs:
            raise TemperatureProgramException(f"Program {program.name} is running.")

        for dev in program.occupied_device:
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
                                                           action.params['SETPOINT']))

                    if action.name == "LINEAR_RAMP":
                        coroutines.append(self.linear_ramp(device,
                                                           action.params['TARGET_TEMP'],
                                                           action.params['RATE']))

                    elif action.name == "SOAK":
                        coroutines.append(asyncio.sleep(action.params['TIME'] * 60))

                    elif action.name == "LOOP":
                        target_action = action.params['GOTO']
                        loop_times = action.params['TIMES']
                        if pointer not in loop_counters:
                            loop_counters[pointer] = 0
                        if loop_counters[pointer] < loop_times:
                            loop_counters[pointer] += 1
                            pointer = target_action - 1  # there a +1 at the end of the while body
                        else:
                            del loop_counters[pointer]

                    elif action.name == "STANDBY":
                        device.control_enabled = False

                await asyncio.gather(*coroutines)
                await self.update_state_callback()

                pointer += 1

        except asyncio.CancelledError:
            asyncio.create_task(self.update_state_callback())
        finally:
            self.current_programs.remove(program)
            del self.current_step[program.name]

            for dev in program.occupied_device:
                self.occupied_devices.remove(dev)
                del self.current_dev_program[dev]
                del self.current_dev_action[dev]

    async def linear_ramp(self, device: TemperatureMonitor, target, rate):
        ramp_interval = self.config.get('ramp_interval', default=1)  # in minutes
        last_temp = device.temperature
        delta = target - last_temp
        ramp_time = delta / rate  # in minutes
        if delta < 0:
            rate = -1 * abs(rate)
        else:
            rate = abs(rate)

        device.control_enabled = True

        for i in float_range(0, ramp_time, ramp_interval):
            await asyncio.sleep(0)  # A chance to stop the program

            next_temp = ramp_interval * rate + last_temp

            if next_temp > target:
                next_temp = target

            if int(next_temp * 10) != int(last_temp * 10):
                device.setpoint = next_temp
            last_temp = next_temp
            await asyncio.sleep(ramp_interval * 60)

    async def change_temperature(self, device: TemperatureMonitor, target):
        tolerance = self.config.get('temperature_tolerance', default=1)  # in degrees

        device.setpoint = target

        average_length = 12
        average_deque = deque(maxlen=average_length)

        while True:
            await asyncio.sleep(5)
            average_deque.append(device.temperature)

            avg = sum(average_deque) / len(average_deque)

            if target - tolerance < avg < target + tolerance:
                break
