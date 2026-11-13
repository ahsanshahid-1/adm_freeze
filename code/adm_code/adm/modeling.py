"""Shared preprocessing, the fixed candidate grids (Section 10), fitting and metrics."""
from __future__ import annotations

import math
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (average_precision_score, balanced_accuracy_score, confusion_matrix, f1_score,
                             mean_absolute_error, mean_squared_error, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .core import derive_seed, small_seed

CLASSIFICATION = {
    "CL1": ("logistic", {"C": 0.1, "solver": "lbfgs", "max_iter": 2000}),
    "CL2": ("logistic", {"C": 1.0, "solver": "lbfgs", "max_iter": 2000}),
    "CL3": ("rf", {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 1, "max_features": "sqrt"}),
    "CL4": ("rf", {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 5, "max_features": "sqrt"}),
    "CL5": ("hgb", {"learning_rate": 0.1, "max_iter": 200, "max_leaf_nodes": 15, "early_stopping": False}),
    "CL6": ("hgb", {"learning_rate": 0.1, "max_iter": 200, "max_leaf_nodes": 31, "early_stopping": False}),
}
REGRESSION = {
    "RG1": ("ridge", {"alpha": 1.0}),
    "RG2": ("ridge", {"alpha": 10.0}),
    "RG3": ("rf", {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 1, "max_features": 1.0}),
    "RG4": ("rf", {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 5, "max_features": 1.0}),
    "RG5": ("hgb", {"learning_rate": 0.1, "max_iter": 200, "max_leaf_nodes": 15, "early_stopping": False}),
    "RG6": ("hgb", {"learning_rate": 0.1, "max_iter": 200, "max_leaf_nodes": 31, "early_stopping": False}),
}
MAX_ONEHOT_CATEGORIES = 64  # safeguard against identifier columns used as categorical predictors


def candidate_ids(task_type: str) -> list:
    return list(REGRESSION) if task_type == "regression" else list(CLASSIFICATION)


def is_linear(cid: str) -> bool:
    return cid in ("CL1", "CL2", "RG1", "RG2")


class CategoricalImputer(BaseEstimator, TransformerMixin):
    """Training-fitted most-frequent imputation; an entirely missing training column uses 'MISSING'."""

    def fit(self, X, y=None):
        X = pd.DataFrame(X).astype(object)
        self.fill_ = []
        for c in X.columns:
            s = X[c].dropna()
            if len(s) == 0:
                self.fill_.append("MISSING")
            else:
                vc = s.astype(str).value_counts()
                top = vc[vc == vc.max()].index.sort_values()[0]
                self.fill_.append(top)
        return self

    def transform(self, X):
        X = pd.DataFrame(X).astype(object).copy()
        for i, c in enumerate(X.columns):
            X[c] = X[c].where(X[c].notna(), self.fill_[i]).astype(str)
        return X.to_numpy()


def make_estimator(cid: str, seed: int):
    kind, params = (CLASSIFICATION.get(cid) or REGRESSION.get(cid))
    rs = small_seed(seed)
    if cid.startswith("CL"):
        if kind == "logistic":
            return LogisticRegression(**params)
        if kind == "rf":
            return RandomForestClassifier(**params, n_jobs=1, random_state=rs)
        return HistGradientBoostingClassifier(**params, random_state=rs)
    if kind == "ridge":
        return Ridge(**params)
    if kind == "rf":
        return RandomForestRegressor(**params, n_jobs=1, random_state=rs)
    return HistGradientBoostingRegressor(**params, random_state=rs)


def make_pipeline(cid: str, numeric: list, categorical: list, seed: int) -> Pipeline:
    num_steps = [("impute", SimpleImputer(strategy="median", keep_empty_features=True))]
    if is_linear(cid):
        num_steps.append(("scale", StandardScaler()))
    transformers = []
    if numeric:
        transformers.append(("num", Pipeline(num_steps), list(numeric)))
    if categorical:
        transformers.append(("cat", Pipeline([("impute", CategoricalImputer()),
                                              ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist",
                                                                       max_categories=MAX_ONEHOT_CATEGORIES,
                                                                       sparse_output=False))]), list(categorical)))
    pre = ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)
    return Pipeline([("pre", pre), ("model", make_estimator(cid, seed))])


def effective_params(cid: str) -> dict:
    est = make_estimator(cid, 0)
    return {k: (v if isinstance(v, (int, float, str, bool, type(None))) else repr(v)) for k, v in est.get_params().items()}


class FeatureTypeError(ValueError):
    pass


def split_columns(X: pd.DataFrame, contract: dict) -> tuple[list, list]:
    """Assign columns of a materialised feature table to the numeric or categorical branch."""
    num, cat = [], []
    contract_num = set(contract.get("numeric_features", []))
    contract_cat = set(contract.get("categorical_features", []))
    for c in X.columns:
        if c == "observation_id":
            continue
        if c in contract_cat:
            cat.append(c)
        elif pd.api.types.is_numeric_dtype(X[c]) and not pd.api.types.is_bool_dtype(X[c]):
            num.append(c)
        elif c in contract_num:
            bad = X[c].dropna().astype(str)
            ex = bad[~bad.str.match(r"^-?[0-9.eE+-]+$")].head(2).tolist()
            raise FeatureTypeError(f"numeric feature '{c}' has non-numeric values (examples: {ex}); "
                                   "convert it with parse_numeric before modeling")
        else:
            cat.append(c)
    return num, cat


def attach_labels(X: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, dict]:
    m = X.merge(labels[["observation_id", "target"]], on="observation_id", how="inner")
    info = {"feature_rows": int(len(X)), "labelled_rows": int(len(m)), "unmatched_rows": int(len(X) - len(m))}
    return m.drop(columns=["target"]), m["target"].to_numpy(), info


# --------------------------------------------------------------------------- metrics
def _metric(task_type: str, name: str, y, pred) -> tuple[float | None, str | None]:
    try:
        if task_type == "regression":
            if name == "rmse":
                return float(math.sqrt(mean_squared_error(y, pred))), None
            if name == "mae":
                return float(mean_absolute_error(y, pred)), None
        if task_type == "binary":
            p = pred
            if name == "average_precision":
                if len(set(y)) < 2:
                    return None, "only one class present"
                return float(average_precision_score(y, p)), None
            if name == "roc_auc":
                if len(set(y)) < 2:
                    return None, "only one class present"
                return float(roc_auc_score(y, p)), None
            if name == "macro_f1":
                return float(f1_score(y, (p >= 0.5).astype(int), average="macro", labels=[0, 1], zero_division=0)), None
        if task_type == "multiclass":
            labels, proba = pred
            yhat = np.asarray(labels)[np.argmax(proba, axis=1)]
            if name == "macro_f1":
                return float(f1_score(y, yhat, average="macro", labels=list(labels), zero_division=0)), None
            if name == "balanced_accuracy":
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    return float(balanced_accuracy_score(y, yhat)), None
    except Exception as e:  # pragma: no cover
        return None, f"{type(e).__name__}: {e}"
    return None, f"unknown metric {name}"


def predict_scores(model: Pipeline, X: pd.DataFrame, task_type: str):
    if task_type == "regression":
        return model.predict(X)
    proba = model.predict_proba(X)
    if task_type == "binary":
        classes = list(model.classes_)
        return proba[:, classes.index(1)] if 1 in classes else np.zeros(len(X))
    return (list(model.classes_), proba)


def selection_score(task_type: str, metric: str, y, pred):
    return _metric(task_type, metric, y, pred)


def full_metrics(task_type: str, y, pred) -> dict:
    out, reasons = {}, {}
    names = {"binary": ["average_precision", "macro_f1", "roc_auc"], "multiclass": ["macro_f1", "balanced_accuracy"],
             "regression": ["rmse", "mae"]}[task_type]
    for n in names:
        v, r = _metric(task_type, n, y, pred)
        out[n] = v
        if r:
            reasons[n] = r
    if task_type == "binary":
        out["prevalence"] = float(np.mean(np.asarray(y) == 1)) if len(y) else None
    if task_type == "multiclass":
        labels, proba = pred
        yhat = np.asarray(labels)[np.argmax(proba, axis=1)]
        out["confusion_matrix"] = {"labels": list(map(str, labels)),
                                   "matrix": confusion_matrix(y, yhat, labels=labels).tolist()}
    if reasons:
        out["undefined_reasons"] = reasons
    return out


def higher_is_better(metric: str) -> bool:
    return metric not in ("rmse", "mae")


# --------------------------------------------------------------------------- fit / evaluate
def fit_evaluate(cid: str, train_X: pd.DataFrame, val_X: pd.DataFrame, labels: pd.DataFrame, cv_folds: list,
                 contract: dict, seed: int) -> dict:
    """Fit one permitted candidate: three inner CV folds on training plus a validation score."""
    t0 = time.time()
    task_type = contract["task_type"]
    metric = contract["selection_metric"]
    if cid not in candidate_ids(task_type):
        raise ValueError(f"candidate {cid} is not permitted; choose one of {candidate_ids(task_type)}")
    tr_lab = labels[labels["partition"] == "train"]
    va_lab = labels[labels["partition"] == "validation"]
    Xtr, ytr, info_tr = attach_labels(train_X, tr_lab)
    Xva, yva, info_va = attach_labels(val_X, va_lab)
    if len(Xtr) == 0:
        raise ValueError("no training rows matched canonical labelled observation_ids")
    num, cat = split_columns(Xtr, contract)
    split_columns(Xva, contract)
    fits = 0
    folds = []
    ids = Xtr["observation_id"].to_numpy()
    for k, (a, b) in enumerate(cv_folds):
        ma, mb = np.isin(ids, a), np.isin(ids, b)
        if ma.sum() == 0 or mb.sum() == 0:
            folds.append({"fold": k, "score": None, "reason": "empty fold after label matching"})
            continue
        pipe = make_pipeline(cid, num, cat, seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pipe.fit(Xtr.loc[ma, num + cat], ytr[ma])
        fits += 1
        s, r = selection_score(task_type, metric, ytr[mb], predict_scores(pipe, Xtr.loc[mb, num + cat], task_type))
        folds.append({"fold": k, "score": s, "reason": r})
    pipe = make_pipeline(cid, num, cat, seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pipe.fit(Xtr[num + cat], ytr)
    fits += 1
    if len(Xva):
        vs, vr = selection_score(task_type, metric, yva, predict_scores(pipe, Xva[num + cat], task_type))
    else:
        vs, vr = None, "no validation rows matched labels"
    cv_scores = [f["score"] for f in folds if f["score"] is not None]
    return {
        "candidate": cid, "metric": metric,
        "cv_mean": float(np.mean(cv_scores)) if cv_scores else None, "cv_folds": folds,
        "validation": vs, "validation_reason": vr,
        "rows": {"train": info_tr, "validation": info_va,
                 "validation_coverage": (info_va["labelled_rows"] / max(1, len(va_lab)))},
        "features": {"numeric": num, "categorical": cat},
        "fits": fits, "seconds": round(time.time() - t0, 3),
    }


def refit(cid: str, train_X: pd.DataFrame, val_X: pd.DataFrame, labels: pd.DataFrame, contract: dict, seed: int):
    """Trusted final refit on training plus validation (the test partition is never used)."""
    X = pd.concat([train_X, val_X], ignore_index=True)
    lab = labels[labels["partition"].isin(["train", "validation"])]
    Xl, y, info = attach_labels(X, lab)
    num, cat = split_columns(Xl, contract)
    pipe = make_pipeline(cid, num, cat, seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pipe.fit(Xl[num + cat], y)
    return pipe, {"numeric": num, "categorical": cat, "rows": info, "fit_partitions": ["train", "validation"]}


def select_best(results: list, metric: str) -> str | None:
    """Best validation score; ties within 1e-12 broken by lexicographic candidate ID."""
    ok = [r for r in results if r.get("validation") is not None]
    if not ok:
        return None
    hib = higher_is_better(metric)
    best = max(r["validation"] for r in ok) if hib else min(r["validation"] for r in ok)
    tied = sorted(r["candidate"] for r in ok if abs(r["validation"] - best) <= 1e-12)
    return tied[0]


def dummy_model(task_type: str):
    if task_type == "regression":
        return DummyRegressor(strategy="mean")
    return DummyClassifier(strategy="prior")
