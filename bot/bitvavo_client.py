from python_bitvavo_api.bitvavo import Bitvavo

def initialize_bitvavo(config: dict) -> Bitvavo:
    """
    Initializes the Bitvavo client with the given configuration.

    Args:
        config (dict): Configuration for the Bitvavo API client.

    Returns:
        Bitvavo: An initialized Bitvavo client instance.
    """
    return Bitvavo({
        'APIKEY': config.get('API_KEY'),
        'APISECRET': config.get('API_SECRET'),
        'RESTURL': config.get('RESTURL', 'https://api.bitvavo.com/v2'),
        'WSURL': config.get('WSURL', 'wss://ws.bitvavo.com/v2/'),
        'ACCESSWINDOW': config.get('ACCESSWINDOW', 10000),
        'DEBUGGING': config.get('DEBUGGING', False)
    })
