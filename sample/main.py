"""Central sample runner for binary_master.

Executes all numbered samples systematically:
1. sample/01_basic_struct.py
2. sample/02_bitfields_and_alignment.py
3. sample/03_offsets_and_tables.py
4. sample/04_procedural_writer.py
5. sample/05_builder_and_reader.py
"""

import subprocess
import sys
from pathlib import Path


def run_sample(script_path: Path) -> bool:
    print(f"\n{'='*70}")
    print(f" Running {script_path.name}...")
    print(f"{'='*70}")
    result = subprocess.run([sys.executable, str(script_path)], capture_output=False)
    if result.returncode != 0:
        print(f"FAILED: {script_path.name} (exit code: {result.returncode})", file=sys.stderr)
        return False
    return True


def main():
    sample_dir = Path(__file__).parent
    samples = [
        sample_dir / "01_basic_struct.py",
        sample_dir / "02_bitfields_and_alignment.py",
        sample_dir / "03_offsets_and_tables.py",
        sample_dir / "04_procedural_writer.py",
        sample_dir / "05_builder_and_reader.py",
        sample_dir / "06_advanced_v2_features.py",
    ]

    print("======================================================================")
    print(" Binary Master: Executing All Samples")
    print("======================================================================")

    all_passed = True
    for sample in samples:
        if not run_sample(sample):
            all_passed = False
            break

    print("\n" + "=" * 70)
    if all_passed:
        print(" ALL 6 SAMPLES COMPLETED SUCCESSFULLY!")
    else:
        print(" SOME SAMPLES FAILED!")
    print("=" * 70)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
