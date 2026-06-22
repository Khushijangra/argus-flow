# ARGUS Stream A Standalone

This folder is a clean standalone extraction of **Stream A only** from the main ARGUS repo:

- backbone: `VideoMAE-v2 Base`
- scorer: `MULDE`
- tasks included:
  - training
  - frame-level evaluation
  - checkpoint ranking
  - evaluation sweep
  - interactive demo
- bundled artifacts:
  - frozen Stream A checkpoint
  - Stream A benchmark reports
  - UBnormal metadata
  - UBnormal pre-extracted VideoMAE features

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the demo:

```bash
python demo.py
```

The demo now exposes two built-in analysis profiles:

- `Avenue (main reported frame-centric result)`
- `UBnormal (locked frozen baseline)`

It also uses a faster interactive path than the benchmark scripts:

- adaptive frame thinning for long videos
- in-memory VideoMAE extraction
- per-video caching when switching between Avenue and UBnormal

Windows quick launch:

```bat
run_demo.bat
```

Run the frozen evaluation:

```bash
python scripts/eval_frame_level.py --dataset stream_a_locked --checkpoint outputs/checkpoints/stream_a_locked_videomae_beta1_score_norm_sigma0.pt --split test --output-json outputs/reports/standalone_stream_a_test.json
```

Windows quick launch:

```bat
run_eval_frozen.bat
```

Reproduce / retrain Stream A:

```bash
python scripts/train.py --dataset stream_a_locked --output-dir outputs/stream_a_locked_repro
python scripts/select_stream_a_checkpoint.py --dataset stream_a_locked --checkpoint-dir outputs/stream_a_locked_repro/checkpoints/stream_a --promote-best --output-json outputs/reports/stream_a_locked_repro_rank_val.json --output-csv outputs/reports/stream_a_locked_repro_rank_val.csv
python scripts/eval_frame_level.py --dataset stream_a_locked --checkpoint outputs/stream_a_locked_repro/checkpoints/stream_a/best_frame.pt --split test --output-json outputs/reports/stream_a_locked_repro_test.json
```

Windows quick launch:

```bat
run_train_locked.bat
```

## Included Artifacts

- `data/metadata/`
  - UBnormal split / frame-label / scene metadata
- `data/features/ubnormal/videomae/`
  - pre-extracted VideoMAE features for UBnormal
- `outputs/checkpoints/`
  - frozen Stream A checkpoint
- `outputs/reports/`
  - historical Stream A ranking and benchmark JSON/CSV files

## Folder Purpose

This standalone copy exists for lab-project evaluation where only Stream A needs to be shown, without exposing the active Stream B research branch.

## Avenue Support Notes

This standalone package is more portable than the original repo:

- metadata loading is dataset-name based, not hardcoded to UBnormal
- feature loading supports both:
  - `Scene{n}/{video}.npy`
  - flat `{video}.npy`

To rebuild or retune Avenue locally:

1. extract features with:

```bash
python scripts/extract_features.py --video-dir <avenue_videos_dir> --output-dir data/features/avenue/videomae
```

Recommended audited source choice:

- prefer pre-extracted RGB frames over SD-MAE-specific caches
- see [docs/avenue_dataset_audit.md](docs/avenue_dataset_audit.md)

2. prepare metadata files:

- `data/metadata/avenue_splits.json`
- `data/metadata/avenue_frame_labels.json`
- `data/metadata/avenue_scenes.json`

You can scaffold the inventory, scenes, and split template from the extracted
Avenue folder with:

```bash
python scripts/scaffold_avenue_metadata.py --dataset-root "C:\Users\jatin\OneDrive\Desktop\SD-MAE\Avenue_Extracted\Avenue Dataset" --output-metadata-dir data/metadata --val-train-videos 14 15 16
```

The scaffold uses split-prefixed canonical names like `train_01` and `test_01`
because raw Avenue train/test ids overlap and would otherwise collide.

After reviewing the held-out train videos, copy the generated template to the
actual split file expected by the loader:

```bash
copy data\\metadata\\avenue_splits_template.json data\\metadata\\avenue_splits.json
```

This standalone package already includes a ready starter config:

```text
configs/avenue_stream_a.yaml
```

If you already have SD-MAE's local Avenue labels, you can import and validate
them directly:

```bash
python scripts/import_avenue_labels.py --txt-label-dir "C:\Users\jatin\OneDrive\Desktop\SD-MAE\VAD-DTI\data\avenue\gt_txt_labels" --mat-mask-dir "C:\Users\jatin\OneDrive\Desktop\SD-MAE\VAD-DTI\data\avenue\gt_labels\ground_truth_demo\testing_label_mask" --metadata-dir data/metadata --output-json data/metadata/avenue_frame_labels.json
```

For feature extraction, run train and test separately with matching prefixes:

```bash
python scripts/extract_features.py --video-dir "C:\Users\jatin\OneDrive\Desktop\SD-MAE\Avenue_Extracted\Avenue Dataset\training_videos" --output-dir data/features/avenue/videomae --name-prefix train
python scripts/extract_features.py --video-dir "C:\Users\jatin\OneDrive\Desktop\SD-MAE\Avenue_Extracted\Avenue Dataset\testing_videos" --output-dir data/features/avenue/videomae --name-prefix test
```

Important caveat:

- the standalone trainer now supports a normal-only holdout selection path for Avenue via
  `training.model_selection_metric: normal_holdout_score`
- this means you can train with a held-out set of normal training videos even before you add
  benchmark labels for test evaluation
- real abnormal/test benchmarking still requires `data/metadata/avenue_frame_labels.json`

3. edit the Avenue config if needed:

```text
configs/avenue_stream_a.yaml
```

and then run:

```bash
python scripts/train.py --dataset avenue_stream_a --output-dir outputs/avenue_stream_a
```

For a quick integrity smoke test before a full run:

```bash
python scripts/train.py --dataset avenue_stream_a_smoke --output-dir outputs/avenue_stream_a_smoke
```

For the current practical Avenue default, use:

```bash
python scripts/train.py --dataset avenue_stream_a --output-dir outputs/avenue_stream_a
```

The Avenue default config is now tuned for the stronger frame-centric recipe:

- `beta = 0.1`
- `learning_rate = 4e-5`
- `signal_kind = log_density`
- `sigma_strategy = gmm`
- `gmm_components = 1`
- balanced Avenue smoothing tuned from the best checkpoint

Current best checked Avenue result from this standalone package:

- checkpoint: `outputs/avenue_stream_a_ld_gmm1_beta01_lr4e5_run1/checkpoints/stream_a/best_holdout.pt`
- report: `outputs/reports/avenue_stream_a_best_test.json`
- test micro AUC: `0.8451`
- test macro AUC: `0.8514`
- clip AUC: `0.8400`

Important comparison note:

- the often-cited `94.3` MULDE Avenue score is the paper's **object-centric**
  setup
- this standalone Stream A is the **frame-centric** path
- the current Avenue result should be presented as a competitive
  **frame-centric** result, not as a direct reproduction of the object-centric
  paper headline

For tomorrow's presentation, the most useful files are:

- `lab_evaluation_summary.md`
- `presentation_script.md`
- `viva_qa.md`

## Notes

- This folder is intentionally self-contained and does not modify the parent repo.
- The frozen Stream A baseline doc is in [docs/stream_a_frozen_baseline.md](docs/stream_a_frozen_baseline.md).
- A standalone context file is in [CODEX.md](CODEX.md).
