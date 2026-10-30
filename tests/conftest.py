"""Tests never contact a model: no cloud provider, and no local Ollama either, whatever is installed."""
import os

os.environ["AUTONOMA_ALLOW_CLOUD"] = "0"
# A closed local port: tests behave the same whether or not Ollama (and which models) run on this machine.
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
