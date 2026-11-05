# StockPilot Korean target-company news sentiment v1

Development model, trained locally on 2026-11-05 with KLUE-RoBERTa-base and the pinned public KorFin-ASC dataset. Labels: negative=0, neutral=1, positive=2.

Input contract: `target-marked-pair-v2`. Use the project's `model_inputs.encode_rows` and `predict.py`; they mark exact target mentions and pair the target with the text. Apply `calibration.json` temperature to logits before softmax. Generic text-only pipelines do not reproduce this input contract.

Selected by validation macro-F1, not test score. Held-out public test accuracy 84.98%, macro-F1 0.8467. The prior model scored 85.57% on the same test. Final calibrated NLL 0.4358; ECE (10 bins) 0.0667. No claim of overall accuracy improvement. See evaluation.json for both models and all metrics.

No live-news AI-assisted annotations were used in training or calibration. No production database changes. Independent validation on recent Samsung news remains required; the 60-example AI-assisted review is diagnostic only.

Data attribution and license are in DATASET_ATTRIBUTION.txt. Retain them with derived data and consult source terms for deployment/distribution. Training source https://huggingface.co/datasets/amphora/korfin-asc ; base model https://huggingface.co/klue/roberta-base .

For use, run START_FINAL.cmd in the parent project or select menu 10. Detailed Korean report: ../../모델-최종결과.md.
