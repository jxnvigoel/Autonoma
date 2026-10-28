"""Tests never contact a cloud provider, whatever config/model_router.json says."""
import os

os.environ["AUTONOMA_ALLOW_CLOUD"] = "0"
