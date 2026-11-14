# Pilot numbers for the paper (computed from raw run records)

## E0: 336 runs; backbones {'none': 48, 'A': 288}; reps [0, 1]; tasks 12
- F: 48/48 = 1.0; terminal {'SUBMITTED': 48}; first failures {}; tokens median None; exceptions 0
- S0: 48/48 = 1.0; terminal {'SUBMITTED': 48}; first failures {}; tokens median 141049.5; exceptions 0
- M0: 47/48 = 0.9792; terminal {'SUBMITTED': 47, 'BUDGET_EXCEEDED': 1}; first failures {'BUDGET': 1}; tokens median 132563.5; exceptions 0
- MQ: 47/48 = 0.9792; terminal {'SUBMITTED': 47, 'EXECUTION_ERROR': 1}; first failures {'EXECUTION': 1}; tokens median 125389.5; exceptions 0
- MP: 48/48 = 1.0; terminal {'SUBMITTED': 48}; first failures {}; tokens median 135416.0; exceptions 0
- SQP: 48/48 = 1.0; terminal {'SUBMITTED': 48}; first failures {}; tokens median 127440.0; exceptions 0
- MQP: 46/48 = 0.9583; terminal {'SUBMITTED': 48}; first failures {'UNIT_MISMATCH': 2}; tokens median 122893.5; exceptions 0
- paired: {'MQP-M0': {'pairs': 48, 'diff_pp': -2.08, 'a_better': 1, 'b_better': 2}, 'MQP-SQP': {'pairs': 48, 'diff_pp': -4.17, 'a_better': 0, 'b_better': 2}, 'MQP-F': {'pairs': 48, 'diff_pp': -4.17, 'a_better': 0, 'b_better': 2}, 'SQP-S0': {'pairs': 48, 'diff_pp': 0, 'a_better': 0, 'b_better': 0}, 'M0-S0': {'pairs': 48, 'diff_pp': -2.08, 'a_better': 0, 'b_better': 1}, 'MQ-M0': {'pairs': 48, 'diff_pp': 0, 'a_better': 1, 'b_better': 1}, 'MP-M0': {'pairs': 48, 'diff_pp': 2.08, 'a_better': 1, 'b_better': 0}}

## E0S: 840 runs; backbones {'none': 120, 'A': 720}; reps [0, 1]; tasks 12
- F: 120/120 = 1.0; terminal {'SUBMITTED': 120}; first failures {}; tokens median None; exceptions 0
- S0: 117/120 = 0.975; terminal {'SUBMITTED': 119, 'BUDGET_EXCEEDED': 1}; first failures {'BUDGET': 1, 'WRONG_JOIN': 1, 'UNIT_MISMATCH': 1}; tokens median 139141.5; exceptions 0
- M0: 116/120 = 0.9667; terminal {'SUBMITTED': 120}; first failures {'WRONG_JOIN': 2, 'MISSING_RECORD': 2}; tokens median 115635.5; exceptions 0
- MQ: 114/120 = 0.95; terminal {'SUBMITTED': 119, 'ABSTAINED': 1}; first failures {'WRONG_JOIN': 5, 'ABSTAINED': 1}; tokens median 119864.0; exceptions 0
- MP: 116/120 = 0.9667; terminal {'SUBMITTED': 119, 'BUDGET_EXCEEDED': 1}; first failures {'MISSING_RECORD': 1, 'WRONG_JOIN': 1, 'UNIT_MISMATCH': 1, 'BUDGET': 1}; tokens median 126320.0; exceptions 0
- SQP: 117/120 = 0.975; terminal {'SUBMITTED': 117, 'BUDGET_EXCEEDED': 3}; first failures {'BUDGET': 3}; tokens median 132475.0; exceptions 0
- MQP: 116/120 = 0.9667; terminal {'SUBMITTED': 120}; first failures {'WRONG_JOIN': 3, 'UNIT_MISMATCH': 1}; tokens median 123279.0; exceptions 0
- paired: {'MQP-M0': {'pairs': 120, 'diff_pp': 0, 'a_better': 2, 'b_better': 2}, 'MQP-SQP': {'pairs': 120, 'diff_pp': -0.83, 'a_better': 2, 'b_better': 3}, 'MQP-F': {'pairs': 120, 'diff_pp': -3.33, 'a_better': 0, 'b_better': 4}, 'SQP-S0': {'pairs': 120, 'diff_pp': 0, 'a_better': 2, 'b_better': 2}, 'M0-S0': {'pairs': 120, 'diff_pp': -0.83, 'a_better': 2, 'b_better': 3}, 'MQ-M0': {'pairs': 120, 'diff_pp': -1.67, 'a_better': 1, 'b_better': 3}, 'MP-M0': {'pairs': 120, 'diff_pp': 0, 'a_better': 3, 'b_better': 3}}

## E0SB: 504 runs; backbones {'B': 504}; reps [0, 1]; tasks 12
- M0: 162/168 = 0.9643; terminal {'SUBMITTED': 167, 'EXECUTION_ERROR': 1}; first failures {'MISSING_RECORD': 1, 'BAD_AGGREGATE': 4, 'EXECUTION': 1}; tokens median 136928.5; exceptions 0
- SQP: 162/168 = 0.9643; terminal {'SUBMITTED': 162, 'ABSTAINED': 6}; first failures {'ABSTAINED': 6}; tokens median 72043.5; exceptions 0
- MQP: 164/168 = 0.9762; terminal {'SUBMITTED': 164, 'ABSTAINED': 3, 'EXECUTION_ERROR': 1}; first failures {'ABSTAINED': 3, 'EXECUTION': 1}; tokens median 132079.0; exceptions 0
- paired: {'MQP-M0': {'pairs': 168, 'diff_pp': 1.19, 'a_better': 4, 'b_better': 2}, 'MQP-SQP': {'pairs': 168, 'diff_pp': 1.19, 'a_better': 4, 'b_better': 2}, 'MQP-F': {'pairs': 0, 'diff_pp': None, 'a_better': 0, 'b_better': 0}, 'SQP-S0': {'pairs': 0, 'diff_pp': None, 'a_better': 0, 'b_better': 0}, 'M0-S0': {'pairs': 0, 'diff_pp': None, 'a_better': 0, 'b_better': 0}, 'MQ-M0': {'pairs': 0, 'diff_pp': None, 'a_better': 0, 'b_better': 0}, 'MP-M0': {'pairs': 0, 'diff_pp': None, 'a_better': 0, 'b_better': 0}}

## E0X: 741 runs; backbones {'none': 106, 'A': 635}; reps [0]; tasks 12
- F: 0/106 = 0.0; terminal {'ABSTAINED': 106}; first failures {'ABSTAINED': 106}; tokens median None; exceptions 0
- S0: 92/106 = 0.8679; terminal {'SUBMITTED': 99, 'BUDGET_EXCEEDED': 7}; first failures {'BUDGET': 7, 'UNIT_MISMATCH': 7}; tokens median 163776.0; exceptions 0
- M0: 92/106 = 0.8679; terminal {'SUBMITTED': 99, 'BUDGET_EXCEEDED': 7}; first failures {'BUDGET': 7, 'WRONG_JOIN': 1, 'UNIT_MISMATCH': 6}; tokens median 183244.0; exceptions 0
- MQ: 100/106 = 0.9434; terminal {'SUBMITTED': 100, 'BUDGET_EXCEEDED': 6}; first failures {'BUDGET': 6}; tokens median 187064.5; exceptions 0
- MP: 86/105 = 0.819; terminal {'SUBMITTED': 96, 'BUDGET_EXCEEDED': 8, 'EXECUTION_ERROR': 1}; first failures {'UNIT_MISMATCH': 8, 'BUDGET': 8, 'MISSING_RECORD': 2, 'EXECUTION': 1}; tokens median 172996.0; exceptions 0
- SQP: 95/106 = 0.8962; terminal {'SUBMITTED': 95, 'BUDGET_EXCEEDED': 8, 'EXECUTION_ERROR': 3}; first failures {'BUDGET': 8, 'EXECUTION': 3}; tokens median 180457.0; exceptions 0
- MQP: 95/106 = 0.8962; terminal {'SUBMITTED': 95, 'BUDGET_EXCEEDED': 10, 'EXECUTION_ERROR': 1}; first failures {'BUDGET': 10, 'EXECUTION': 1}; tokens median 191990.0; exceptions 0
- paired: {'MQP-M0': {'pairs': 106, 'diff_pp': 2.83, 'a_better': 9, 'b_better': 6}, 'MQP-SQP': {'pairs': 106, 'diff_pp': 0, 'a_better': 8, 'b_better': 8}, 'MQP-F': {'pairs': 106, 'diff_pp': 89.62, 'a_better': 95, 'b_better': 0}, 'SQP-S0': {'pairs': 106, 'diff_pp': 2.83, 'a_better': 7, 'b_better': 4}, 'M0-S0': {'pairs': 106, 'diff_pp': 0, 'a_better': 4, 'b_better': 4}, 'MQ-M0': {'pairs': 106, 'diff_pp': 7.55, 'a_better': 11, 'b_better': 3}, 'MP-M0': {'pairs': 105, 'diff_pp': -4.76, 'a_better': 3, 'b_better': 8}}

## E0X2: 1512 runs; backbones {'none': 216, 'A': 1296}; reps [1, 2]; tasks 12
- F: 0/216 = 0.0; terminal {'ABSTAINED': 216}; first failures {'ABSTAINED': 216}; tokens median None; exceptions 0
- S0: 121/216 = 0.5602; terminal {'SUBMITTED': 200, 'BUDGET_EXCEEDED': 15, 'EXECUTION_ERROR': 1}; first failures {'UNIT_MISMATCH': 9, 'SOURCE_VERSION': 69, 'BUDGET': 15, 'VALUE_MISMATCH': 1, 'EXECUTION': 1}; tokens median 168073.0; exceptions 0
- M0: 108/216 = 0.5; terminal {'BUDGET_EXCEEDED': 25, 'SUBMITTED': 189, 'ABSTAINED': 1, 'EXECUTION_ERROR': 1}; first failures {'BUDGET': 25, 'SOURCE_VERSION': 67, 'ABSTAINED': 1, 'UNIT_MISMATCH': 11, 'MISSING_RECORD': 1, 'VALUE_MISMATCH': 1, 'EXECUTION': 1, 'WRONG_JOIN': 1}; tokens median 193541.5; exceptions 0
- MQ: 139/216 = 0.6435; terminal {'SUBMITTED': 182, 'BUDGET_EXCEEDED': 27, 'EXECUTION_ERROR': 2, 'ABSTAINED': 5}; first failures {'BUDGET': 27, 'SOURCE_VERSION': 43, 'EXECUTION': 2, 'ABSTAINED': 5}; tokens median 209657.5; exceptions 0
- MP: 185/216 = 0.8565; terminal {'SUBMITTED': 199, 'BUDGET_EXCEEDED': 13, 'EXECUTION_ERROR': 3, 'ABSTAINED': 1}; first failures {'BUDGET': 13, 'MISSING_RECORD': 1, 'EXECUTION': 3, 'UNIT_MISMATCH': 11, 'VALUE_MISMATCH': 1, 'FORBIDDEN_FEATURE': 1, 'ABSTAINED': 1}; tokens median 193473.5; exceptions 0
- SQP: 185/216 = 0.8565; terminal {'SUBMITTED': 186, 'BUDGET_EXCEEDED': 28, 'EXECUTION_ERROR': 2}; first failures {'BUDGET': 28, 'EXECUTION': 2, 'SOURCE_VERSION': 1}; tokens median 186054.5; exceptions 0
- MQP: 187/216 = 0.8657; terminal {'SUBMITTED': 188, 'BUDGET_EXCEEDED': 28}; first failures {'BUDGET': 28, 'SOURCE_VERSION': 1}; tokens median 203920.0; exceptions 0
- paired: {'MQP-M0': {'pairs': 216, 'diff_pp': 36.57, 'a_better': 92, 'b_better': 13}, 'MQP-SQP': {'pairs': 216, 'diff_pp': 0.93, 'a_better': 18, 'b_better': 16}, 'MQP-F': {'pairs': 216, 'diff_pp': 86.57, 'a_better': 187, 'b_better': 0}, 'SQP-S0': {'pairs': 216, 'diff_pp': 29.63, 'a_better': 83, 'b_better': 19}, 'M0-S0': {'pairs': 216, 'diff_pp': -6.02, 'a_better': 17, 'b_better': 30}, 'MQ-M0': {'pairs': 216, 'diff_pp': 14.35, 'a_better': 49, 'b_better': 18}, 'MP-M0': {'pairs': 216, 'diff_pp': 35.65, 'a_better': 88, 'b_better': 11}}

## e0x2_calibration
```
{
 "X2a": {
  "n": 48,
  "vcr_S0_M0": 0.7708
 },
 "X2b": {
  "n": 48,
  "vcr_S0_M0": 0.75
 },
 "X2c": {
  "n": 48,
  "vcr_S0_M0": 0.75
 },
 "X3a": {
  "n": 48,
  "vcr_S0_M0": 0.7083
 },
 "X3b": {
  "n": 48,
  "vcr_S0_M0": 0.8125
 },
 "X3c": {
  "n": 48,
  "vcr_S0_M0": 0.8333
 },
 "X4a": {
  "n": 48,
  "vcr_S0_M0": 0.0417
 },
 "X4b": {
  "n": 48,
  "vcr_S0_M0": 0.0833
 },
 "X4c": {
  "n": 48,
  "vcr_S0_M0": 0.0208
 }
}
```

## e0x2_rep_agreement
```
{
 "1": 0.7269,
 "2": 0.7006
}
```

## e0x2_by_defect
```
{
 "X2": {
  "F": 0.0,
  "S0": 0.8333,
  "M0": 0.6806,
  "MQ": 0.7222,
  "MP": 0.8333,
  "SQP": 0.7361,
  "MQP": 0.7778
 },
 "X3": {
  "F": 0.0,
  "S0": 0.8194,
  "M0": 0.75,
  "MQ": 0.9167,
  "MP": 0.7639,
  "SQP": 0.8611,
  "MQP": 0.8472
 },
 "X4": {
  "F": 0.0,
  "S0": 0.0278,
  "M0": 0.0694,
  "MQ": 0.2917,
  "MP": 0.9722,
  "SQP": 0.9722,
  "MQP": 0.9722
 }
}
```

## e0x2_detail_by_defect
```
{
 "X2": {
  "F": {
   "n": 72,
   "verified": 0,
   "terminal": {
    "ABSTAINED": 72
   },
   "first_failure": {
    "ABSTAINED": 72
   },
   "mean_repairs": 0,
   "mean_gate_calls": 2,
   "tokens_mean": null
  },
  "S0": {
   "n": 72,
   "verified": 60,
   "terminal": {
    "SUBMITTED": 60,
    "BUDGET_EXCEEDED": 12
   },
   "first_failure": {
    "BUDGET": 12
   },
   "mean_repairs": 0,
   "mean_gate_calls": 0,
   "tokens_mean": 202474.9
  },
  "M0": {
   "n": 72,
   "verified": 49,
   "terminal": {
    "BUDGET_EXCEEDED": 19,
    "SUBMITTED": 51,
    "ABSTAINED": 1,
    "EXECUTION_ERROR": 1
   },
   "first_failure": {
    "BUDGET": 19,
    "ABSTAINED": 1,
    "MISSING_RECORD": 1,
    "EXECUTION": 1,
    "WRONG_JOIN": 1
   },
   "mean_repairs": 0,
   "mean_gate_calls": 0,
   "tokens_mean": 226763.8
  },
  "MQ": {
   "n": 72,
   "verified": 52,
   "terminal": {
    "SUBMITTED": 52,
    "BUDGET_EXCEEDED": 20
   },
   "first_failure": {
    "BUDGET": 20
   },
   "mean_repairs": 0.028,
   "mean_gate_calls": 6.47,
   "tokens_mean": 228679.0
  },
  "MP": {
   "n": 72,
   "verified": 60,
   "terminal": {
    "SUBMITTED": 61,
    "BUDGET_EXCEEDED": 10,
    "EXECUTION_ERROR": 1
   },
   "first_failure": {
    "BUDGET": 10,
    "MISSING_RECORD": 1,
    "EXECUTION": 1
   },
   "mean_repairs": 0.014,
   "mean_gate_calls": 7.29,
   "tokens_mean": 208943.5
  },
  "SQP": {
   "n": 72,
   "verified": 53,
   "terminal": {
    "SUBMITTED": 53,
    "BUDGET_EXCEEDED": 19
   },
   "first_failure": {
    "BUDGET": 19
   },
   "mean_repairs": 0,
   "mean_gate_calls": 12.47,
   "tokens_mean": 210776.0
  },
  "MQP": {
   "n": 72,
   "verified": 56,
   "terminal": {
    "SUBMITTED": 56,
    "BUDGET_EXCEEDED": 16
   },
   "first_failure": {
    "BUDGET": 16
   },
   "mean_repairs": 0.014,
   "mean_gate_calls": 14.06,
   "tokens_mean": 217704.9
  }
 },
 "X3": {
  "F": {
   "n": 72,
   "verified": 0,
   "terminal": {
    "ABSTAINED": 72
   },
   "first_failure": {
    "ABSTAINED": 72
   },
   "mean_repairs": 0,
   "mean_gate_calls": 2,
   "tokens_mean": null
  },
  "S0": {
   "n": 72,
   "verified": 59,
   "terminal": {
    "SUBMITTED": 69,
    "BUDGET_EXCEEDED": 2,
    "EXECUTION_ERROR": 1
   },
   "first_failure": {
    "UNIT_MISMATCH": 9,
    "BUDGET": 2,
    "VALUE_MISMATCH": 1,
    "EXECUTION": 1
   },
   "mean_repairs": 0,
   "mean_gate_calls": 0,
   "tokens_mean": 178054.7
  },
  "M0": {
   "n": 72,
   "verified": 54,
   "terminal": {
    "SUBMITTED": 66,
    "BUDGET_EXCEEDED": 6
   },
   "first_failure": {
    "BUDGET": 6,
    "UNIT_MISMATCH": 11,
    "VALUE_MISMATCH": 1
   },
   "mean_repairs": 0,
   "mean_gate_calls": 0,
   "tokens_mean": 205046.4
  },
  "MQ": {
   "n": 72,
   "verified": 66,
   "terminal": {
    "SUBMITTED": 66,
    "BUDGET_EXCEEDED": 4,
    "EXECUTION_ERROR": 2
   },
   "first_failure": {
    "BUDGET": 4,
    "EXECUTION": 2
   },
   "mean_repairs": 0.194,
   "mean_gate_calls": 7.62,
   "tokens_mean": 208500.9
  },
  "MP": {
   "n": 72,
   "verified": 55,
   "terminal": {
    "SUBMITTED": 68,
    "EXECUTION_ERROR": 2,
    "BUDGET_EXCEEDED": 2
   },
   "first_failure": {
    "EXECUTION": 2,
    "BUDGET": 2,
    "UNIT_MISMATCH": 11,
    "VALUE_MISMATCH": 1,
    "FORBIDDEN_FEATURE": 1
   },
   "mean_repairs": 0,
   "mean_gate_calls": 7.67,
   "tokens_mean": 196191.4
  },
  "SQP": {
   "n": 72,
   "verified": 62,
   "terminal": {
    "SUBMITTED": 62,
    "BUDGET_EXCEEDED": 8,
    "EXECUTION_ERROR": 2
   },
   "first_failure": {
    "BUDGET": 8,
    "EXECUTION": 2
   },
   "mean_repairs": 0.208,
   "mean_gate_calls": 14.53,
   "tokens_mean": 194457.4
  },
  "MQP": {
   "n": 72,
   "verified": 61,
   "terminal": {
    "SUBMITTED": 61,
    "BUDGET_EXCEEDED": 11
   },
   "first_failure": {
    "BUDGET": 11
   },
   "mean_repairs": 0.222,
   "mean_gate_calls": 14.75,
   "tokens_mean": 215920.8
  }
 },
 "X4": {
  "F": {
   "n": 72,
   "verified": 0,
   "terminal": {
    "ABSTAINED": 72
   },
   "first_failure": {
    "ABSTAINED": 72
   },
   "mean_repairs": 0,
   "mean_gate_calls": 2,
   "tokens_mean": null
  },
  "S0": {
   "n": 72,
   "verified": 2,
   "terminal": {
    "SUBMITTED": 71,
    "BUDGET_EXCEEDED": 1
   },
   "first_failure": {
    "SOURCE_VERSION": 69,
    "BUDGET": 1
   },
   "mean_repairs": 0.014,
   "mean_gate_calls": 0,
   "tokens_mean": 146503.3
  },
  "M0": {
   "n": 72,
   "verified": 5,
   "terminal": {
    "SUBMITTED": 72
   },
   "first_failure": {
    "SOURCE_VERSION": 67
   },
   "mean_repairs": 0,
   "mean_gate_calls": 0,
   "tokens_mean": 160248.7
  },
  "MQ": {
   "n": 72,
   "verified": 21,
   "terminal": {
    "SUBMITTED": 64,
    "ABSTAINED": 5,
    "BUDGET_EXCEEDED": 3
   },
   "first_failure": {
    "SOURCE_VERSION": 43,
    "ABSTAINED": 5,
    "BUDGET": 3
   },
   "mean_repairs": 0.222,
   "mean_gate_calls": 7.94,
   "tokens_mean": 186640.6
  },
  "MP": {
   "n": 72,
   "verified": 70,
   "terminal": {
    "SUBMITTED": 70,
    "BUDGET_EXCEEDED": 1,
    "ABSTAINED": 1
   },
   "first_failure": {
    "BUDGET": 1,
    "ABSTAINED": 1
   },
   "mean_repairs": 0.722,
   "mean_gate_calls": 8.68,
   "tokens_mean": 177505.9
  },
  "SQP": {
   "n": 72,
   "verified": 70,
   "terminal": {
    "SUBMITTED": 71,
    "BUDGET_EXCEEDED": 1
   },
   "first_failure": {
    "BUDGET": 1,
    "SOURCE_VERSION": 1
   },
   "mean_repairs": 0.972,
   "mean_gate_calls": 17.58,
   "tokens_mean": 171014.0
  },
  "MQP": {
   "n": 72,
   "verified": 70,
   "terminal": {
    "SUBMITTED": 71,
    "BUDGET_EXCEEDED": 1
   },
   "first_failure": {
    "SOURCE_VERSION": 1,
    "BUDGET": 1
   },
   "mean_repairs": 0.667,
   "mean_gate_calls": 17.08,
   "tokens_mean": 186412.4
  }
 }
}
```

## exception_runs
```
{
 "E0": {},
 "E0S": {},
 "E0SB": {},
 "E0X": {},
 "E0X2": {}
}
```

## agentic_runs_by_backbone
```
{
 "E0": {
  "A": 288
 },
 "E0S": {
  "A": 720
 },
 "E0SB": {
  "B": 504
 },
 "E0X": {
  "A": 635
 },
 "E0X2": {
  "A": 1296
 }
}
```

## limit_pool
```
{
 "n": 1377,
 "aggregate_tokens": {
  "p50": 141224.0,
  "p90": 228673.80000000002,
  "p95": 245961.60000000006,
  "max": 296303
 },
 "model_calls": {
  "p50": 20.0,
  "p90": 32.0,
  "p95": 33.0,
  "max": 38
 },
 "tool_calls": {
  "p50": 18.0,
  "p90": 28.0,
  "p95": 30.0,
  "max": 35
 },
 "active_seconds": {
  "p50": 144.38,
  "p90": 224.40040000000002,
  "p95": 249.0816,
  "max": 379.263
 }
}
```

## budget_exceeded_frozen_design
```
{
 "F": 0,
 "S0": 8,
 "M0": 9,
 "MQ": 9,
 "MP": 5,
 "SQP": 14,
 "MQP": 12
}
```

## tier2_op_usage
```
{
 "tier1_E0_E0S": {
  "M0": {
   "runs": 168,
   "normalize_key": 0,
   "infer_representation": 0,
   "authoritative_verified": 0,
   "dedupe_key": 18,
   "no_trace": 0
  },
  "MP": {
   "runs": 168,
   "normalize_key": 0,
   "infer_representation": 0,
   "authoritative_verified": 0,
   "dedupe_key": 26,
   "no_trace": 0
  },
  "MQ": {
   "runs": 168,
   "normalize_key": 0,
   "infer_representation": 0,
   "authoritative_verified": 0,
   "dedupe_key": 23,
   "no_trace": 0
  },
  "MQP": {
   "runs": 168,
   "normalize_key": 0,
   "infer_representation": 0,
   "authoritative_verified": 0,
   "dedupe_key": 27,
   "no_trace": 0
  },
  "S0": {
   "runs": 168,
   "normalize_key": 0,
   "infer_representation": 0,
   "authoritative_verified": 0,
   "dedupe_key": 41,
   "no_trace": 0
  },
  "SQP": {
   "runs": 168,
   "normalize_key": 0,
   "infer_representation": 0,
   "authoritative_verified": 0,
   "dedupe_key": 47,
   "no_trace": 0
  }
 },
 "tier2_E0X2_all_levels": {
  "M0": {
   "runs": 216,
   "normalize_key": 186,
   "infer_representation": 91,
   "authoritative_verified": 25,
   "dedupe_key": 39,
   "no_trace": 0
  },
  "MP": {
   "runs": 216,
   "normalize_key": 197,
   "infer_representation": 87,
   "authoritative_verified": 117,
   "dedupe_key": 38,
   "no_trace": 0
  },
  "MQ": {
   "runs": 216,
   "normalize_key": 188,
   "infer_representation": 109,
   "authoritative_verified": 57,
   "dedupe_key": 39,
   "no_trace": 0
  },
  "MQP": {
   "runs": 216,
   "normalize_key": 195,
   "infer_representation": 114,
   "authoritative_verified": 131,
   "dedupe_key": 40,
   "no_trace": 0
  },
  "S0": {
   "runs": 216,
   "normalize_key": 178,
   "infer_representation": 75,
   "authoritative_verified": 3,
   "dedupe_key": 61,
   "no_trace": 0
  },
  "SQP": {
   "runs": 216,
   "normalize_key": 187,
   "infer_representation": 83,
   "authoritative_verified": 73,
   "dedupe_key": 64,
   "no_trace": 0
  }
 }
}
```

## tier2_op_usage_by_defect
```
{
 "X2": {
  "M0": {
   "runs": 72,
   "normalize_key": 63,
   "infer_representation": 14,
   "authoritative_verified": 10,
   "dedupe_key": 14,
   "no_trace": 0
  },
  "MP": {
   "runs": 72,
   "normalize_key": 68,
   "infer_representation": 15,
   "authoritative_verified": 24,
   "dedupe_key": 14,
   "no_trace": 0
  },
  "MQ": {
   "runs": 72,
   "normalize_key": 63,
   "infer_representation": 17,
   "authoritative_verified": 16,
   "dedupe_key": 13,
   "no_trace": 0
  },
  "MQP": {
   "runs": 72,
   "normalize_key": 69,
   "infer_representation": 19,
   "authoritative_verified": 32,
   "dedupe_key": 17,
   "no_trace": 0
  },
  "S0": {
   "runs": 72,
   "normalize_key": 62,
   "infer_representation": 4,
   "authoritative_verified": 0,
   "dedupe_key": 20,
   "no_trace": 0
  },
  "SQP": {
   "runs": 72,
   "normalize_key": 59,
   "infer_representation": 4,
   "authoritative_verified": 0,
   "dedupe_key": 20,
   "no_trace": 0
  }
 },
 "X3": {
  "M0": {
   "runs": 72,
   "normalize_key": 60,
   "infer_representation": 58,
   "authoritative_verified": 10,
   "dedupe_key": 11,
   "no_trace": 0
  },
  "MP": {
   "runs": 72,
   "normalize_key": 62,
   "infer_representation": 58,
   "authoritative_verified": 21,
   "dedupe_key": 10,
   "no_trace": 0
  },
  "MQ": {
   "runs": 72,
   "normalize_key": 57,
   "infer_representation": 67,
   "authoritative_verified": 19,
   "dedupe_key": 9,
   "no_trace": 0
  },
  "MQP": {
   "runs": 72,
   "normalize_key": 64,
   "infer_representation": 69,
   "authoritative_verified": 28,
   "dedupe_key": 10,
   "no_trace": 0
  },
  "S0": {
   "runs": 72,
   "normalize_key": 62,
   "infer_representation": 59,
   "authoritative_verified": 1,
   "dedupe_key": 19,
   "no_trace": 0
  },
  "SQP": {
   "runs": 72,
   "normalize_key": 66,
   "infer_representation": 65,
   "authoritative_verified": 2,
   "dedupe_key": 24,
   "no_trace": 0
  }
 },
 "X4": {
  "M0": {
   "runs": 72,
   "normalize_key": 63,
   "infer_representation": 19,
   "authoritative_verified": 5,
   "dedupe_key": 14,
   "no_trace": 0
  },
  "MP": {
   "runs": 72,
   "normalize_key": 67,
   "infer_representation": 14,
   "authoritative_verified": 72,
   "dedupe_key": 14,
   "no_trace": 0
  },
  "MQ": {
   "runs": 72,
   "normalize_key": 68,
   "infer_representation": 25,
   "authoritative_verified": 22,
   "dedupe_key": 17,
   "no_trace": 0
  },
  "MQP": {
   "runs": 72,
   "normalize_key": 62,
   "infer_representation": 26,
   "authoritative_verified": 71,
   "dedupe_key": 13,
   "no_trace": 0
  },
  "S0": {
   "runs": 72,
   "normalize_key": 54,
   "infer_representation": 12,
   "authoritative_verified": 2,
   "dedupe_key": 22,
   "no_trace": 0
  },
  "SQP": {
   "runs": 72,
   "normalize_key": 62,
   "infer_representation": 14,
   "authoritative_verified": 71,
   "dedupe_key": 20,
   "no_trace": 0
  }
 }
}
```

## gpu_accounting
```
{
 "records": [
  {
   "time": "2026-11-11T05:15:36Z",
   "experiment": "E0",
   "backbone": "A",
   "gpu_seconds_total": 5253.762491941452
  },
  {
   "time": "2026-11-11T05:35:13Z",
   "experiment": "E0B",
   "backbone": "B",
   "gpu_seconds_total": 339.46819138526917
  },
  {
   "time": "2026-11-11T09:50:58Z",
   "experiment": "E0S",
   "backbone": "A",
   "gpu_seconds_total": 12977.225491285324
  },
  {
   "time": "2026-11-11T14:15:03Z",
   "experiment": "E0X",
   "backbone": "A",
   "gpu_seconds_total": 14198.767624378204
  },
  {
   "time": "2026-11-11T18:38:25Z",
   "experiment": "E0SB",
   "backbone": "B",
   "gpu_seconds_total": 9924.616151571274
  },
  {
   "time": "2026-11-12T03:22:51Z",
   "experiment": "E0X2",
   "backbone": "A",
   "gpu_seconds_total": 30538.741320610046
  },
  {
   "time": "2026-11-12T07:31:03Z",
   "experiment": "E0SB",
   "backbone": "B",
   "gpu_seconds_total": 10900.903288125992
  }
 ]
}
```

## frozen_design_preview (VCR)
- tier1: F 168/168=1.0, S0 165/168=0.9821, M0 163/168=0.9702, MQ 161/168=0.9583, MP 164/168=0.9762, SQP 165/168=0.9821, MQP 162/168=0.9643
- tier2: F 0/72=0.0, S0 37/72=0.5139, M0 37/72=0.5139, MQ 45/72=0.625, MP 61/72=0.8472, SQP 60/72=0.8333, MQP 60/72=0.8333
- tier2_without_X4: F 0/48=0.0, S0 36/48=0.75, M0 34/48=0.7083, MQ 38/48=0.7917, MP 38/48=0.7917, SQP 36/48=0.75, MQP 36/48=0.75
- pooled: F 168/240=0.7, S0 202/240=0.8417, M0 200/240=0.8333, MQ 206/240=0.8583, MP 225/240=0.9375, SQP 225/240=0.9375, MQP 222/240=0.925
- paired pooled {'MQP-M0': {'pairs': 240, 'diff_pp': 9.17, 'a_better': 31, 'b_better': 9}, 'MQP-SQP': {'pairs': 240, 'diff_pp': -1.25, 'a_better': 5, 'b_better': 8}, 'MQP-F': {'pairs': 240, 'diff_pp': 22.5, 'a_better': 60, 'b_better': 6}}
- paired tier1 {'MQP-M0': {'pairs': 168, 'diff_pp': -0.6, 'a_better': 3, 'b_better': 4}, 'MQP-SQP': {'pairs': 168, 'diff_pp': -1.79, 'a_better': 2, 'b_better': 5}, 'MQP-F': {'pairs': 168, 'diff_pp': -3.57, 'a_better': 0, 'b_better': 6}}
- paired tier2 {'MQP-M0': {'pairs': 72, 'diff_pp': 31.94, 'a_better': 28, 'b_better': 5}, 'MQP-SQP': {'pairs': 72, 'diff_pp': 0, 'a_better': 3, 'b_better': 3}, 'MQP-F': {'pairs': 72, 'diff_pp': 83.33, 'a_better': 60, 'b_better': 0}}

## e0sb_archived
- E0SB_partial_v20prompt_20261111_0945: 62 runs; M0 19/20=0.95 (exc 1), SQP 22/22=1.0 (exc 0), MQP 18/20=0.9 (exc 2)
- E0SB_policy_crash_bug_20261111_2223: 504 runs; M0 153/168=0.9107 (exc 9), SQP 162/168=0.9643 (exc 0), MQP 145/168=0.8631 (exc 19)
