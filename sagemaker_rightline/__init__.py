import logging

__version__ = "0.0.0"

# Sagemaker continuously complains about config since newer versions. Suppressing this.
logging.getLogger("sagemaker.config").setLevel(logging.WARNING)
