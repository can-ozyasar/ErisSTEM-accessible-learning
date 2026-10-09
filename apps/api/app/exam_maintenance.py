"""Run periodically against the application's database to enforce exam retention."""
import argparse
import json
import time

from .exam_practice import ExamStore
from .job_store import make_session_factory
from .learning_operations import LearningOperationsStore

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    store = LearningOperationsStore(make_session_factory())
    while True:
        print(json.dumps(ExamStore(store).cleanup()), flush=True)
        if not args.watch:
            break
        time.sleep(30)
