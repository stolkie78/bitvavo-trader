import logging
import os
from bot.slack_notifier import SlackNotifier


class LoggingFacility:
    """
    A centralized logging facility for both console and Slack logging.
    """

    def __init__(self, config: dict):
        """
        Initializes the logging facility.

        Args:
            config (dict): Configuration for Slack webhook and logging options.
        """
        self.console_logger = logging.getLogger("console")
        self.console_logger.setLevel(logging.INFO)
        self.console_logger.propagate = False
        # Only add a handler if none exist
        if not self.console_logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(message)s"))
            self.console_logger.addHandler(console_handler)

        self.slack_notifier = SlackNotifier(config.get("SLACK_WEBHOOK_URL"))
        self.slack_results_only = config.get("SLACK_RESULTS_ONLY", True)

    def log_to_console(self, message: str):
        """
        Logs a message to the console.

        Args:
            message (str): The message to log.
        """
        self.console_logger.info(message)

    def log_to_slack(self, message: str, results_only: bool = False):
        """
        Sends a message to Slack if allowed by the configuration.

        Args:
            message (str): The message to send.
            results_only (bool): Whether the message is a result-only notification.
        """
        if results_only and not self.slack_results_only:
            return
        self.slack_notifier.send_message(message)

    def log(self, message: str, to_console: bool = True, to_slack: bool = False, results_only: bool = False):
        """
        Logs a message to both console and Slack.

        Args:
            message (str): The message to log.
            to_console (bool): Whether to log the message to the console.
            to_slack (bool): Whether to send the message to Slack.
            results_only (bool): Whether to restrict Slack messages to result-only notifications.
        """
        if to_console:
            self.log_to_console(message)
        if to_slack:
            self.log_to_slack(message, results_only)
