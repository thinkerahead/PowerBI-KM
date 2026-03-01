# PowerBI-KM: Kaplan–Meier Survival Curves & Risk Tables

Flexible KM solution for Power BI with **Python**, **R**, or **DAX/Power Query** implementations.

## 🚀 Quick Start: Choose Your Path

### **Path 1: Power BI Native (Recommended for Service)**
Use DAX and Power Query only — no external code, works in Power BI Service and Desktop.

**START HERE:** [PowerBI_Native_KM_Complete_Guide.md](PowerBI_Native_KM_Complete_Guide.md)

**Includes:**
- Power Query transforms for both data structures
- 5 TimePoints table options
- All KM measures (survival, confidence intervals, validation)
- Step-by-step visual construction
- Performance & validation checklist

---

### **Path 2: Python Visual (Desktop Only)**
Place `PowerBI_KM.py` in Power BI's Python folder.

**Requirements**: numpy, pandas, scipy, matplotlib ✅ All Power BI supported

---

### **Path 3: R Visual (Desktop Only)**
Place `PowerBI_KM.R` in Power BI's R folder.

**Requirements**: survival, ggplot2, gridExtra ✅ All Power BI supported

---

## ✨ Features

- **Dual Data Structure Support**: Handles by-patient (Event/Day pairs) and by-patient-endpoint (pre-aggregated)
- **Manual Timepoint Selection**: User specifies exact timepoints
- **Confidence Intervals**: Greenwood's formula for ±95% CI bounds
- **Reference Lines**: Target survival rate lines (single or group-specific)
- **Risk Table Output**: Exposed as visual or DAX measure
- **Multiple Paths**: Python/R visuals or native DAX/Power Query

---

## 📊 Data Structures

### Structure 1: By Patient (Multiple Endpoints)
```
PT | group  | Event1 | Day1 | EventB | DayB
1  | GroupA | 0      | 30   | 1      | 35
2  | GroupB | 1      | 45   | 0      | 50
```

### Structure 2: By Patient & Endpoint (Pre-Aggregated)
```
PT | group  | Event | Day
1  | GroupA | 1     | 30
2  | GroupB | 0     | 45
```

---

## ⚙️ Configuration Parameters (Python/R)

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `structure_type` | str | `"auto"` | Auto-detect or specify "1" or "2" |
| `timepoints` | list | `[0, 30, 60, 90]` | Manual timepoints |
| `group_col` | str | `'group'` | Group column name |
| `time_cols` | str/list | `'Day'` or `['Day1', 'DayB']` | Time column(s) |
| `event_cols` | str/list | `'Event'` or `['Event1', 'EventB']` | Event column(s) |
| `max_day` | float | `365` | Optional max follow-up cutoff |
| `plot_title` | str | `'Survival Curves'` | Custom title |
| `xlabel` | str | `'Days'` | X-axis label |
| `ylabel` | str | `'Probability'` | Y-axis label |
| `group_label` | str | `'Treatment'` | Legend/group label |
| `target_surv_rates` | str | `'0.5'` or `'A:0.75,B:0.5'` | Target survival lines |
| `risk_table_title` | str | `'Number at Risk'` | Risk table header |

---

## 📁 File Reference

| File | Purpose | Best For |
|------|---------|----------|
| **PowerBI_Native_KM_Complete_Guide.md** | Complete DAX/Power Query with visuals | ✅ Power BI Service |
| DAX_TimePoints_Table.md | 5 TimePoints creation options | Reference |
| DAX_KM_Measures.md | 7 DAX measures (copy-paste ready) | Reference |
| PowerBI_KM.py | Python visual script | Power BI Desktop |
| PowerBI_KM.R | R visual script | Power BI Desktop |
| README.md | This file | Overview |

---

## 🎯 Example: Quick Validation

**Risk Table Output (Matrix Visual)**
```
Group     0    30    60    90
------- --- ----- ----- ----
Control 100   92   84   75
TrtA    100   94   86   79
TrtB    100   96   89   83
```

**KM Values (Partial)**
```
Time | GroupA_AtRisk | GroupA_KM | GroupB_KM
-----|---------------|-----------|----------
0    | 100           | 1.000     | 1.000
30   | 100           | 0.920     | 0.930
60   | 92            | 0.875     | 0.891
```

---

## ⚡ Performance Tips

1. **Large Datasets (>1M rows)**: Use DAX approach; pre-aggregate in Power Query
2. **Many Groups**: Limit TimePoints to 4–6 (Option A: manual)
3. **Premium Capacity**: Use DAX with CACHE function for subquery memoization
4. **Python/R**: Desktop only; Service requires DAX

---

## ✅ Validation Checklist

- [ ] `Total_Patients` matches source data
- [ ] `Total_Events` ≤ `Total_Patients`
- [ ] Risk table shows decreasing counts (left to right)
- [ ] KM survival starts at 1.0, monotonically decreasing
- [ ] Different groups show visually distinct curves
- [ ] CIs symmetric around point estimate
- [ ] No negative or >1.0 values
- [ ] Manual Excel spot-check matches measures

---

## 🐛 Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| KM stuck at 1.0 | Missing t=0 or FinalEvent all zeros | Add ROW("Time", 0); verify events=1 for occurrence |
| Risk table empty | groupVar not in Matrix Rows slot | Drag groupVar to **Rows** (not Values) |
| Curves identical across groups | Group context lost | Ensure groupVar in Legend/Rows; avoid ALL() |
| Slow (>100K patients) | Too many distinct timepoints | Use manual TimePoints (6 max) |
| Python/R risk table not showing | DataFrame not returned correctly | Ensure risk_table is final output object |

---

## 📦 Supported Packages

**Python**:
- numpy ✅
- pandas ✅
- scipy ✅
- matplotlib ✅

**R**:
- survival ✅
- ggplot2 ✅
- gridExtra ✅ (optional fallback)

---

## 📖 References

- [Kaplan–Meier Estimator](https://en.wikipedia.org/wiki/Kaplan–Meier_estimator)
- [Greenwood's Formula](https://en.wikipedia.org/wiki/Kaplan–Meier_estimator#Variance_of_the_Kaplan-Meier_estimator)
- [Power BI DAX](https://learn.microsoft.com/en-us/dax/)
- [Power Query M](https://learn.microsoft.com/en-us/powerquery-m/)

---

## 📝 License

MIT License – See LICENSE file for details.
