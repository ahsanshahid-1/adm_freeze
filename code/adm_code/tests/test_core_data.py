import numpy as np
import pandas as pd

from adm.core import SessionClock, derive_seed, df_hash, seed_string
from adm import datasets as D


def test_seed_vectors():
    assert seed_string("evaluation", "D5", "generator", "", "SYN-MACHINE-v1") == \
        "adm-kaggle-1.0|20261030|evaluation|D5|generator||SYN-MACHINE-v1"
    assert derive_seed("evaluation", "D5", "generator", "", "SYN-MACHINE-v1") == 16589070799177694325
    assert derive_seed("corruption", "D1", "D1-T2", 0, "C1:cell:train") == 13713059381983676020
    assert derive_seed("agent", "D3", "D3-T4", 2, "C6") == 2652557224513615479


def test_df_hash_order_invariant_and_value_sensitive():
    a = pd.DataFrame({"x": [1.0, 2.0, np.nan], "y": ["a", "b", None]})
    b = a.iloc[[2, 0, 1]][["y", "x"]]
    assert df_hash(a) == df_hash(b)
    c = a.copy()
    c.loc[0, "x"] = 1.0000001
    assert df_hash(a) != df_hash(c)
    assert df_hash(pd.concat([a, a.iloc[[0]]])) != df_hash(a)


def test_session_clock():
    t = [0.0]
    c = SessionClock(start=0.0, stop_new_h=1.0, hard_stop_h=1.5, now_fn=lambda: t[0])
    assert c.may_start_new(100)
    t[0] = 3550
    assert not c.may_start_new(100)
    assert not c.must_stop()
    t[0] = 5401
    assert c.must_stop()


def test_generators_deterministic_and_formula():
    a, _, _ = D.generate_d5(50, 20, "development", "D5X")
    b, _, _ = D.generate_d5(50, 20, "development", "D5X")
    assert df_hash(a) == df_hash(b)
    e, _, _ = D.generate_d5(50, 20, "evaluation", "D5")
    assert not set(a["observation_id"]) & set(e["observation_id"])
    big, _, parts = D.generate_d5(500, 20)
    s = big[[f"sensor_{j}" for j in range(1, 7)]]
    assert abs(s.to_numpy().std() - 1.0) < 0.05  # 0.4^2 + 0.84 = 1
    g, _, _ = D.generate_d6(300, 30)
    assert 45 < g["process_output"].mean() < 55


def test_splits(paths):
    for fam in ["D5", "D6"]:
        df, spec = D.load_canonical(paths, "development", fam)
        s = D.load_split(paths, "development", fam, 0)
        info = D.check_split(df, spec, s)
        assert sum(info["sizes"].values()) == len(df)
        assert (s.groupby("group")["partition"].nunique() == 1).all()
        folds = D.cv_splits(s, spec.split_rule)
        assert len(folds) == 3 and all(len(a) and len(b) for a, b in folds)
