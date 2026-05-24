import logging

def setup_logging(name=__name__, level=logging.INFO):
    """Shared logging configuration"""
    logging.basicConfig(level=level)
    return logging.getLogger(name)
