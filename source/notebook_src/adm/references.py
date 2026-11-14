"""Clean-data reference workflows and dummy models (Section 10.4). Trusted, evaluator-side computations;
agents never see these outputs."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import modeling
from .core import Paths, instance_dirs, read_json, write_json, derive_seed, small_seed
from .datasets import cv_splits
from .tasks import ensure_instance


def _labels(dirs) -> tuple[pd.DataFrame, pd.DataFrame]:
    lab = pd.read_parquet(dirs["trusted"] / "labels.parquet")
    test = pd.read_parquet(dirs["private"] / "labels_test.parquet")
    return lab, test


def reference_workflow(paths: Paths, suite: str, family: str, template: str, rep: int) -> dict:
    ensure_instance(paths, suite, family, template, "C0", rep)
    dirs = instance_dirs(paths, suite, family, template, "C0", rep)
    contract = read_json(dirs["visible"] / "contract.json")
    rule = read_json(dirs["visible"] / "visible_partition_manifest.json")["cv_policy"]["rule"]
    refs = {p: pd.read_parquet(dirs["private"] / f"reference_{p}.parquet") for p in ("train", "validation", "test")}
    lab, test = _labels(dirs)
    cv = cv_splits(lab, rule)
    seed = small_seed(derive_seed("estimator", family, f"{family}-{template}", rep, "C0"))
    tt = contract["task_type"]
    results = [modeling.fit_evaluate(c, refs["train"], refs["validation"], lab, cv, contract, seed)
               for c in contract["candidate_models"]]
    best = modeling.select_best(results, contract["selection_metric"])
    model, info = modeling.refit(best, refs["train"], refs["validation"], lab, contract, seed)
    X = refs["test"].merge(test, on="observation_id")
    feats = info["numeric"] + info["categorical"]
    pred = modeling.predict_scores(model, X[feats], tt)
    metrics = modeling.full_metrics(tt, X["target"].to_numpy(), pred)
    # dummy model on the correct canonical workflow
    trv = lab[lab["partition"].isin(["train", "validation"])]
    dm = modeling.dummy_model(tt)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dm.fit(np.zeros((len(trv), 1)), trv["target"].to_numpy())
    Z = np.zeros((len(X), 1))
    if tt == "regression":
        dpred = dm.predict(Z)
    elif tt == "binary":
        classes = list(dm.classes_)
        dpred = dm.predict_proba(Z)[:, classes.index(1)]
    else:
        dpred = (list(dm.classes_), dm.predict_proba(Z))
    dmetrics = modeling.full_metrics(tt, X["target"].to_numpy(), dpred)
    return {"suite": suite, "family": family, "template": template, "repetition": rep, "task_type": tt,
            "selected_candidate": best, "validation": {r["candidate"]: r["validation"] for r in results},
            "test_metrics": metrics, "dummy_test_metrics": dmetrics}


def build_references(paths: Paths, suite: str, families: list, templates: list, reps: list, log=print) -> dict:
    out_path = paths.outputs / f"references_{suite}.json"
    out = read_json(out_path) if out_path.exists() else {}
    for f in families:
        for t in templates:
            for r in reps:
                k = f"{f}-{t}/r{r}"
                if k in out:
                    continue
                out[k] = reference_workflow(paths, suite, f, t, r)
                write_json(out_path, out)
    log(f"reference workflows ({suite}): {len(out)}")
    return out
