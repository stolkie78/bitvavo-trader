import json
import os
import logging

class ConfigLoader:
    """
    A utility class to load JSON configuration files and handle missing configurations gracefully.
    """

    @staticmethod
    def load_config(file_name: str) -> dict:
        """
        Loads a JSON configuration file.

        Args:
            file_name (str): The name of the configuration file.

        Returns:
            dict: The configuration data as a dictionary.
        """
        config_path = os.path.join("./config", file_name)
        if not os.path.exists(config_path):
            logging.error(f"Configuration file not found: {config_path}")
            raise FileNotFoundError(f"Configuration file {file_name} not found.")

        with open(config_path, 'r') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON in {file_name}: {e}")
                raise
