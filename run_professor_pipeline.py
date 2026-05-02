import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
STEPS = [
    ('build neutral master', 'build_professor_master.py'),
    ('enrich faculty-page details', 'enrich_professor_master.py'),
    ('deep-enrich individual profile pages', 'deep_enrich_professor_profiles.py'),
    ('publish frontend dataset', 'build_publish_json.py'),
]


def run_step(label, script):
    path = BASE / script
    print(f'\n=== {label}: {script} ===')
    result = subprocess.run([sys.executable, str(path)], cwd=BASE)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    for label, script in STEPS:
        run_step(label, script)
    print('\nPipeline complete.')
    print('Updated artifacts:')
    print('- ucsb_professors_master.csv')
    print('- ucsb_professors_master.json')
    print('- ucsb_professor_connections.json')
    print('- ucsb_professor_screening.json')


if __name__ == '__main__':
    main()
