import time
import asyncio
from abc import ABC, abstractmethod
from collections import deque
from logging import Logger
from typing import Union

from temperature_web_control.plugin.plugin_base import PluginState
from temperature_web_control.server.app_core import TemperatureAppCore
from temperature_web_control.utils import Config


class StatusAlertCondition(ABC):
    def __init__(self, name, last_for, logger):
        self.name = name
        self.logger = logger
        self.last_for = last_for

        self.triggered_time = 0

    @abstractmethod
    def is_condition_satisfied(self, status):
        pass

    def should_alert(self, status):
        if self.is_condition_satisfied(status):
            current_time = time.time()

            if self.triggered_time == 0:
                self.triggered_time = current_time

            if self.last_for != 0 and current_time - self.triggered_time < self.last_for:
                self.logger.info(
                    f"Alert Plugin: Event occurred: {self.name}, lasting for {current_time - self.triggered_time:.2f} s")
                return False

            return True

        self.triggered_time = 0
        return False

    @abstractmethod
    def get_alert_devices(self):
        pass

    @staticmethod
    @abstractmethod
    def create_from_config(config, logger):
        pass


class HighTemperatureStatusAlertCondition(StatusAlertCondition):
    def __init__(self, dev, temperature, last_for, logger):
        super().__init__(f"Temperature of {dev} higher than {temperature} degrees", last_for, logger)
        self.dev = dev
        self.temperature = temperature

    @staticmethod
    def create_from_config(config, logger):
        assert 'device' in config, "Missing parameter"
        assert 'temperature_threshold' in config, "Missing parameter"
        last_for = config.get('last_for', 0) * 60

        return HighTemperatureStatusAlertCondition(config['device'], config['temperature_threshold'], last_for, logger)

    def is_condition_satisfied(self, status):
        if self.dev not in status:
            self.logger.debug(f"Alert Plugin: {self.dev} not in status dict, ignored.")
            return False

        dev = status[self.dev]

        if dev['temperature'] > self.temperature:
            return True
        return False

    def get_alert_devices(self):
        return [self.dev]


class LowTemperatureStatusAlertCondition(StatusAlertCondition):
    def __init__(self, dev, temperature, last_for, logger):
        super().__init__(f"Temperature of {dev} lower than {temperature} degrees", last_for, logger)
        self.dev = dev
        self.temperature = temperature

    @staticmethod
    def create_from_config(config, logger):
        assert 'device' in config, "Missing parameter"
        assert 'temperature_threshold' in config, "Missing parameter"
        last_for = config.get('last_for', 0) * 60

        return LowTemperatureStatusAlertCondition(config['device'], config['temperature_threshold'], last_for, logger)

    def is_condition_satisfied(self, status):
        if self.dev not in status:
            self.logger.debug(f"Alert Plugin: {self.dev} not in status dict, ignored.")
            return False

        dev = status[self.dev]

        if dev['temperature'] < self.temperature:
            return True
        return False

    def get_alert_devices(self):
        return [self.dev]


class TemperatureDifferencesTooLargeStatusAlertCondition(StatusAlertCondition):
    def __init__(self, devs, temperature_diff, last_for, logger):
        super().__init__(f"Temperatures difference among of {', '.join(devs)} higher than {temperature_diff} degrees",
                         last_for, logger)
        self.devs = devs
        self.temperature_diff = temperature_diff
        self.alert_dev = None

    @staticmethod
    def create_from_config(config, logger):
        assert 'devices' in config, "Missing parameter"
        assert 'temperature_difference' in config, "Missing parameter"
        last_for = config.get('last_for', 0) * 60
        assert len(config['devices']) > 1, "Need more than one device to compare difference"

        return TemperatureDifferencesTooLargeStatusAlertCondition(config['devices'], config['temperature_difference'],
                                                                  last_for, logger)

    def get_alert_devices(self):
        return self.devs

    def is_condition_satisfied(self, status):
        for dev in self.devs:
            if dev not in status:
                self.logger.debug(f"Alert Plugin: {dev} not in status dict, ignored.")
                return False

        highest = 0
        lowest = 0

        for dev_name in self.devs:
            dev = status[dev_name]
            if dev['temperature'] > highest:
                highest = dev['temperature']
            elif dev['temperature'] < lowest:
                lowest = dev['temperature']

        if highest - lowest > self.temperature_diff:
            return True
        return False


class TemperatureChangingTooFastStatusAlertCondition(StatusAlertCondition):
    def __init__(self, dev, rate, last_for, logger):
        super().__init__(f"Temperature changing rate of {dev} higher than {rate} degrees/min", last_for, logger)
        self.dev = dev
        self.rate = rate
        self.last_temperature = None
        self.last_time = None
        self.history_rate = deque(maxlen=3)

    @staticmethod
    def create_from_config(config, logger):
        assert 'device' in config, "Missing parameter"
        assert 'rate_threshold' in config, "Missing parameter"
        last_for = config.get('last_for', 0) * 60

        return TemperatureChangingTooFastStatusAlertCondition(config['device'], config['rate_threshold'],
                                                              last_for, logger)

    def get_alert_devices(self):
        return [self.dev]

    def is_condition_satisfied(self, status):
        if self.dev not in status:
            self.logger.debug(f"Alert Plugin: {self.dev} not in status dict, ignored.")
            return False

        dev = status[self.dev]

        if self.last_temperature is None:
            self.last_temperature = dev['temperature']
            self.last_time = time.time()
            return False

        current_temperature = dev['temperature']
        current_time = time.time()

        diff_time = current_time - self.last_time
        rate = (current_temperature - self.last_temperature) / (diff_time / 60)
        self.last_temperature = current_temperature
        self.last_time = current_time

        self.history_rate.append(rate)

        if self.compare_rate():
            return True

        return False

    def compare_rate(self):
        if abs(sum(self.history_rate) / len(self.history_rate)) > self.rate:
            return True
        return False


class TemperatureRisingTooFastAlertMonitor(TemperatureChangingTooFastStatusAlertCondition):
    def __init__(self, dev, rate, last_for, logger):
        super().__init__(dev, abs(rate), last_for, logger)
        self.name = f"Temperature of {dev} rising faster than {abs(rate)} degrees/min"

    @staticmethod
    def create_from_config(config, logger):
        assert 'device' in config, "Missing parameter"
        assert 'rate_threshold' in config, "Missing parameter"
        last_for = config.get('last_for', 0) * 60

        return TemperatureRisingTooFastAlertMonitor(config['device'], config['rate_threshold'],
                                                    last_for, logger)

    def compare_rate(self):
        if abs(sum(self.history_rate) / len(self.history_rate)) > self.rate:
            return True
        return False


class TemperatureDroppingTooFastAlertMonitor(TemperatureChangingTooFastStatusAlertCondition):
    def __init__(self, dev, rate, last_for, logger):
        super().__init__(dev, -1 * abs(rate), last_for, logger)
        self.name = f"Temperature of {dev} dropping faster than {-1 * abs(rate)} degrees/min"

    @staticmethod
    def create_from_config(config, logger):
        assert 'device' in config, "Missing parameter"
        assert 'rate_threshold' in config, "Missing parameter"
        last_for = config.get('last_for', 0) * 60

        return TemperatureDroppingTooFastAlertMonitor(config['device'], config['rate_threshold'],
                                                      last_for, logger)

    def compare_rate(self):
        avg_rate = sum(self.history_rate) / len(self.history_rate)
        if avg_rate < 0 and avg_rate < self.rate:
            return True
        return False


class ErrorAlertCondition(ABC):
    def __init__(self, name, logger):
        self.name = name
        self.logger = logger

        self.triggered_time = 0

    @abstractmethod
    def should_alert(self, error):
        pass

    @staticmethod
    @abstractmethod
    def create_from_config(config, logger):
        pass


class RegexFilterErrorAlertCondition(ErrorAlertCondition):
    def __init__(self, filter, logger):
        super().__init__(f"Error filter {filter.pattern}", logger)
        self.logger = logger
        self.filter = filter

    def should_alert(self, error):
        return self.filter.match(error)

    @staticmethod
    def create_from_config(config, logger):
        import re

        assert 'includes' in config or 'regex' in config, "Missing parameters"

        regex = ""
        if 'includes' in config:
            regex = ".*" + re.escape(config['includes']) + ".*"

        if 'regex' in config:
            regex = config['regex']

        if config.get("ignore_case", False):
            compiled_regex = re.compile(regex, re.IGNORECASE)
        else:
            compiled_regex = re.compile(regex)

        return RegexFilterErrorAlertCondition(compiled_regex, logger)


class AlertAction(ABC):
    def __init__(self, name, app_core: TemperatureAppCore, logger):
        self.name = name
        self.app_core = app_core
        self.logger = logger

    @abstractmethod
    def execute(self, status, error, alert):
        pass

    @staticmethod
    @abstractmethod
    def create_from_config(config, app_core, logger):
        pass


class DisengageAction(AlertAction):
    def __init__(self, dev, app_core, logger):
        super().__init__(f"Disengage {dev}", app_core, logger)
        self.dev = dev

    @staticmethod
    def create_from_config(config, app_core, logger):
        if type(config) is dict:
            assert 'device' in config, "Missing parameter"
            return DisengageAction(config['device'], app_core, logger)
        elif type(config) is str:
            dev = config
            return DisengageAction(dev, app_core, logger)
        else:
            raise TypeError("Wrong parameter type")

    def execute(self, status, error, alert):
        self.logger.warning(f"Alert Plugin: Disengage {self.dev}")
        self.app_core.dev_instances[self.dev].control_enabled = False


class EngageAction(AlertAction):
    def __init__(self, dev, app_core, logger):
        super().__init__(f"Engage {dev}", app_core, logger)
        self.dev = dev

    @staticmethod
    def create_from_config(config, app_core, logger):
        if type(config) is dict:
            assert 'device' in config, "Missing parameter"
            return EngageAction(config['device'], app_core, logger)
        elif type(config) is str:
            dev = config
            return EngageAction(dev, app_core, logger)
        else:
            raise TypeError("Wrong parameter type")

    def execute(self, status, error, alert):
        self.logger.warning(f"Alert Plugin: Engage {self.dev}")
        self.app_core.dev_instances[self.dev].control_enabled = True


class SetpointAction(AlertAction):
    def __init__(self, dev, setpoint, app_core, logger):
        super().__init__(f"Set setpoint of {dev} to {setpoint}", app_core, logger)
        self.dev = dev
        self.setpoint = setpoint

    @staticmethod
    def create_from_config(config, app_core, logger):
        assert 'device' in config, "Missing parameter"
        assert 'setpoint' in config, "Missing parameter"
        return SetpointAction(config['device'], config['setpoint'], app_core, logger)

    def execute(self, status, error, alert):
        self.logger.warning(f"Alert Plugin: Set setpoint of {self.dev} to {self.setpoint}")
        self.app_core.dev_instances[self.dev].setpoint = self.setpoint


class RunProgramAction(AlertAction):
    def __init__(self, program, app_core, logger):
        super().__init__(f"Run program {program}", app_core, logger)
        self.program = program

    @staticmethod
    def create_from_config(config, app_core, logger):
        assert type(config) is dict or type(config) is str, "Syntax error"

        if type(config) is dict:
            assert 'program' in config, "Missing parameter"
            return RunProgramAction(config['program'], app_core, logger)
        else:
            return RunProgramAction(config, app_core, logger)

    def execute(self, status, error, alert):
        if self.program in self.app_core.programs:
            program = self.app_core.programs[self.program]
            self.logger.warning(f"Alert Plugin: Run program {self.program}")
            self.app_core.program_manager.create_program_task(program)
        else:
            self.logger.warning(f"Alert Plugin: Program {self.program} doesn't exist")


class AbortProgramAction(AlertAction):
    def __init__(self, program, app_core, logger):
        super().__init__(f"Abort program {program}", app_core, logger)
        self.program = program

    @staticmethod
    def create_from_config(config, app_core, logger):
        assert type(config) is dict or type(config) is str, "Syntax error"

        if type(config) is dict:
            assert 'program' in config, "Missing parameter"
            return AbortProgramAction(config['program'], app_core, logger)
        else:
            return AbortProgramAction(config, app_core, logger)

    def execute(self, status, error, alert):
        if self.program in self.app_core.programs:
            program = self.app_core.programs[self.program]
            self.logger.warning(f"Alert Plugin: Abort program {self.program}")
            self.app_core.program_manager.abort_program(program.name)
        else:
            self.logger.warning(f"Alert Plugin: Program {self.program} doesn't exist")


class AbortAllProgramsAction(AlertAction):
    def __init__(self, app_core, logger):
        super().__init__(f"Abort all running programs", app_core, logger)

    @staticmethod
    def create_from_config(config, app_core, logger):
        return AbortAllProgramsAction(app_core, logger)

    def execute(self, status, error, alert):
        self.logger.warning(f"Alert Plugin: Abort all programs")
        self.app_core.program_manager.abort_all_programs()


class DisplayAlertAction(AlertAction):
    @staticmethod
    def create_from_config(config, app_core, logger):
        return DisplayAlertAction(f"Display alert to users", app_core, logger)

    def execute(self, status, error, alert):
        asyncio.create_task(self.app_core.fire_program_error(alert.name))


class SendEmailAction(AlertAction):
    def __init__(self, *, recipients, sender, smtp_host, smtp_port, ssl, ssl_verify, password, subject, content, app_core, logger):
        super().__init__(f"Send email to {', '.join(recipients)}", app_core, logger)
        self.recipients = recipients
        self.sender = sender
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.ssl = ssl
        self.ssl_verify = ssl_verify
        self.password = password
        self.subject = subject
        self.content = content

    @staticmethod
    def create_from_config(config, app_core, logger):
        _config = {}
        _config.update(email_config_dict)
        _config.update(config)

        config = _config

        assert 'sender' in config, "Missing parameter"
        assert SendEmailAction.validate_email_addr(config['sender']), "Invalid email address"
        sender = config['sender']

        assert 'recipient' in config or 'recipients' in config, "Missing parameter"
        if 'recipient' in config:
            assert SendEmailAction.validate_email_addr(config['recipient']), "Invalid email address"
            recipients = [config['recipient']]
        else:
            assert type(config['recipients']) is list, "Invalid syntax"
            assert all([SendEmailAction.validate_email_addr(recip) for recip in config['recipients']]),\
                "Invalid email address"
            recipients = config['recipients']

        assert 'smtp_host' in config, "Missing parameter"
        smtp_host = config['smtp_host']
        smtp_port = config.get('smtp_port', 25)

        ssl = config.get('ssl', False)
        ssl_verify = config.get('ssl_verify', True)
        password = config.get('password', None)
        subject = config.get('subject', None)
        content = config.get('content', None)

        return SendEmailAction(recipients=recipients,
                               sender=sender,
                               smtp_host=smtp_host,
                               smtp_port=smtp_port,
                               ssl=ssl,
                               ssl_verify=ssl_verify,
                               password=password,
                               subject=subject,
                               content=content,
                               app_core=app_core,
                               logger=logger)

    @staticmethod
    def validate_email_addr(addr):
        import re
        if re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', addr):
            return True
        return False

    def execute(self, status, error, alert):
        import smtplib
        from email.message import EmailMessage
        from datetime import datetime

        subject = self.subject
        content = self.content

        if not subject:
            subject = f"TEMPERATURE ALERT: {alert.name}"

        if not content:
            time = datetime.now().isoformat()
            content = f"""\
            TEMPERATURE ALERT: {alert.name}
            
            Time: {time}
            """

            if error:
                content += f"""\
                Error: {error}
                """

        msg = EmailMessage()
        msg.set_content(content)
        msg['Subject'] = subject
        msg['From'] = self.sender
        msg['To'] = ', '.join(self.recipients)

        self.logger.warning(f"Alert Plugin: Send email \n {msg.as_string()}")

        server = None
        try:
            if not self.ssl:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            else:
                import ssl
                context = ssl.create_default_context()
                if not self.ssl_verify:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context)

            if self.password:
                server.login(self.sender, self.password)

            server.send_message(msg)
        finally:
            if server:
                server.quit()


alert_condition_mapping = {
    'high_temperature': HighTemperatureStatusAlertCondition,
    'low_temperature': LowTemperatureStatusAlertCondition,
    'large_temperature_difference': TemperatureDifferencesTooLargeStatusAlertCondition,
    'large_temperature_changing_rate': TemperatureChangingTooFastStatusAlertCondition,
    'large_temperature_rising_rate': TemperatureRisingTooFastAlertMonitor,
    'large_temperature_dropping_rate': TemperatureDroppingTooFastAlertMonitor,
    'error_message_matches': RegexFilterErrorAlertCondition
}

alert_action_mapping = {
    'display_alert': DisplayAlertAction,
    'disengage': DisengageAction,
    'engage': EngageAction,
    'change_setpoint': SetpointAction,
    'run_program': RunProgramAction,
    'abort_all_programs': AbortAllProgramsAction,
    'abort_program': AbortProgramAction,
    'send_email': SendEmailAction
}

email_config_dict = {}


class AlertPluginState(PluginState):
    def __init__(self, config: Config, app_core: TemperatureAppCore, logger: Logger):
        self.config = config
        self.app_core = app_core
        self.logger = logger
        self.current_alert_list = []

        alerts = self.config.get("alerts", default=None)
        self.condition_action_tuples = []

        for alert_condition in alerts:
            assert len(list(alert_condition.keys())) == 1, "Syntax error"
            _type = list(alert_condition.keys())[0]
            _config = alert_condition[_type]
            assert "actions" in alert_condition[_type], "Missing actions"
            _actions = alert_condition[_type]["actions"]

            assert _type in alert_condition_mapping, "Unknown alert condition type"
            condition_instance = alert_condition_mapping[_type].create_from_config(_config, logger)

            self.logger.info(f"Alert Plugin: Load alert condition: {condition_instance.name}")

            action_instances = []
            for action in _actions:
                assert type(action) is dict or type(action) is str, "Syntax error"
                if type(action) is dict:
                    assert len(list(action.keys())) == 1, "Syntax error"
                    _action_type = list(action.keys())[0]
                    _action_config = action[_action_type]
                else:
                    _action_type = action
                    _action_config = {}

                assert _action_type in alert_action_mapping, "Unknown action type"
                action_instance = alert_action_mapping[_action_type].create_from_config(_action_config,
                                                                                        app_core,
                                                                                        logger)

                self.logger.info(f"Alert Plugin: - action: {action_instance.name}")

                action_instances.append(action_instance)

            self.condition_action_tuples.append((condition_instance, action_instances))


        self.app_core.subscribe_to("status_available", self, self.on_status_available_event)
        self.app_core.subscribe_to("program_error", self, self.on_error_event)

    async def on_status_available_event(self, subscribers, message):
        status = message['status']

        for (condition, actions) in self.condition_action_tuples:
            if isinstance(condition, ErrorAlertCondition):
                continue

            assert isinstance(condition, StatusAlertCondition)
            if condition.should_alert(status):
                if condition not in self.current_alert_list:
                    self.current_alert_list.append(condition)
                    for action in actions:
                        action.execute(status, None, condition)
            else:
                if condition in self.current_alert_list:
                    self.current_alert_list.remove(condition)

    async def on_error_event(self, subscribers, message):
        for (condition, actions) in self.condition_action_tuples:
            error = message['error']

            if isinstance(condition, StatusAlertCondition):
                continue

            assert isinstance(condition, ErrorAlertCondition)
            if condition.should_alert(error):
                self.logger.warning(f"Alert Plugin: Alert triggered: {condition.name}")
                for action in actions:
                    action.execute(None, error, condition)

    async def run(self):
        pass


async def initialize(config: Config, app_core: TemperatureAppCore, logger: Logger) -> Union[PluginState, None]:
    if config.get("alerts", default=None):
        email_config_dict.update(config.get("alert_email_settings", default={}))

        plugin = AlertPluginState(config, app_core, logger)
        return plugin
    else:
        return None
