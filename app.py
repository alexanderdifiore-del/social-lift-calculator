"""Launcher so both `streamlit run app.py` and `streamlit run social_lift_calculator.py` open lollie."""

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("social_lift_calculator.py")), run_name="__main__")
