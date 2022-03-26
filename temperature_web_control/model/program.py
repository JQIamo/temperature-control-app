from collections import namedtuple
from typing import List

ActionDefinition = namedtuple("Action", ["name", "display_name", "status_word", "description", "params_desc",
                                         "need_device", "standalone", "attention_level"])

ATTN_LOW = 0
ATTN_HIGH = 1

actions = {
    "CHANGE": ActionDefinition(
        "CHANGE",
        "Change",
        "Changing",
        "Immediately change the setpoint to a value and wait until temperature settles.",
        [
            ("SETPOINT", "Target setpoint."),
        ],
        True,
        True,
        ATTN_HIGH
    ),
    "LINEAR_RAMP": ActionDefinition(
        "LINEAR_RAMP",
        "Ramp",
        "Ramping",
        "Linearly ramp up/down the temperature.",
        [
            ("TARGET_TEMP", "Target temperature."),
            ("RATE", "Temperature raise/drop per minute.")
        ],
        True,
        True,
        ATTN_HIGH
    ),
    "SOAK": ActionDefinition(
        "SOAK",
        "Soak",
        "Soaking",
        "Hold the current temperature.",
        [("TIME", "Duration of soak in minutes.")],
        True,
        False,
        ATTN_LOW
    ),
    "STANDBY": ActionDefinition(
        "STANDBY",
        "Standby",
        "Standby",
        "Disengage the controller. Put it into Standby mode.",
        [],
        True,
        False,
        ATTN_LOW
    ),
    "LOOP": ActionDefinition(
        "LOOP",
        "Loop",
        "",
        "Jump back to a specific step and loop for a defined number of times.",
        [
            ("GOTO", "The number of the step to jump back to."),
            ("TIMES", "The number of times to loop.")
        ],
        False,
        False,
        ATTN_LOW
    ),
}

Action = namedtuple("Action", ["name", "device", "params"])

class Program:
    def __init__(self, name: str, description: str, steps: List[List[Action]]):
        self.name = name
        self.description = description
        self.steps = steps
        self.occupied_device = []

        self._calculate_occupied_devices()

    def _calculate_occupied_devices(self):
        for step in self.steps:
            for action in step:
                if action.device and action.device not in self.occupied_device:
                    self.occupied_device.append(action.device)

    @staticmethod
    def from_dict(steps_dict: dict):
        steps = [
            [
                Action(action['action'],
                       action['device'] if 'device' in action else None,
                       action['params'] if 'params' in action else None)
                for action in step ]
            for step in steps_dict['steps']
        ]

        return Program(steps_dict['name'], steps_dict['description'], steps)

    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'steps': [
                [{ 'action': action.name,
                   'device': action.device,
                   'params': action.params } for action in step]
                for step in self.steps]
        }
