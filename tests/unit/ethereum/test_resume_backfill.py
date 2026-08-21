import json
import tempfile
from src.collectors.backfill import BackfillEngine

def test_resume_state_save_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        resume_file = f"{tmpdir}/resume.json"
        engine = BackfillEngine.__new__(BackfillEngine)
        engine.resume_file = resume_file
        engine.state = {"last_processed_block": 100}
        engine._save_resume_state()
        with open(resume_file, 'r') as f:
            data = json.load(f)
        assert data["last_processed_block"] == 100
