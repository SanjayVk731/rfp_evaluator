"""Metadata for the bundled synthetic proposals (used by the UI demo and the CLI)."""
import os

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_rfps")

# (supplier_name, submission_date, experience_rating 0-5, file_name)
SAMPLE_SUPPLIERS = [
    ("Apex Systems", "2026-10-20", 4.2, "Apex_Systems_Proposal.pdf"),
    ("BrightPath Tech", "2026-10-18", 2.5, "BrightPath_Tech_Proposal.pdf"),
    ("NexaWorks", "2026-10-20", 4.0, "NexaWorks_Proposal.pdf"),
    ("Orbit Digital", "2026-10-22", 4.8, "Orbit_Digital_Proposal.pdf"),
]
BLANK_SAMPLE = ("Zenith Consulting", "2026-10-21", 3.0, "Zenith_Scanned_Blank_Proposal.pdf")
