import requests
import logging

class SlackNotifier:
    """
    Handles sending notifications to a Slack channel using a webhook URL.
    """

    def __init__(self, webhook_url: str):
        """
        Initializes the SlackNotifier.

        Args:
            webhook_url (str): The webhook URL for sending Slack messages.
        """
        self.webhook_url = webhook_url

    def send_message(self, message: str):
        """
        Sends a message to the configured Slack channel.

        Args:
            message (str): The message to send.
        """
        if not message.strip():
            logging.warning("Attempted to send an empty Slack message.")
            return

        payload = {"text": message}
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            if response.status_code != 200:
                logging.error(f"Slack API error: {response.status_code} - {response.text}")
        except requests.RequestException as e:
            logging.error(f"Failed to send message to Slack: {e}")
