"""Hypothesis Maker — entry point."""
import sys
import os

# Ensure the app directory is in sys.path when running as exe
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

from gui.app import HypothesisMakerApp

if __name__ == '__main__':
    app = HypothesisMakerApp()
    app.run()
