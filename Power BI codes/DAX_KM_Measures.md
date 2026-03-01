# Power BI DAX: KM Measures (AtRisk, Events, KM Survival)

Copy these measure definitions into your Power BI model. Each measure respects filter context automatically.

---

## Measure 1: Events At Time

Counts the number of patients with an event at the current timepoint.

```dax
Events_AtTime = 
VAR t = MAX(TimePoints[Time])
RETURN
CALCULATE(
  COUNTROWS(Patients),
  Patients[FinalDay] = t,
  Patients[FinalEvent] = 1
)
```

**How it works:**
- Takes the maximum timepoint from the current visual context (e.g., column in a matrix).
- Counts rows where `FinalDay = t` AND `FinalEvent = 1`.
- Automatically filters by `groupVar` if it's in row context.

---

## Measure 2: At Risk At Time

Counts the number of patients at risk (alive and uncensored) at the current timepoint.

```dax
AtRisk_AtTime = 
VAR t = MAX(TimePoints[Time])
RETURN
CALCULATE(
  COUNTROWS(Patients),
  Patients[FinalDay] >= t
)
```

**How it works:**
- Counts all patients with follow-up time >= t (including those with events and censored).
- Used as the denominator in KM calculation and displayed in the risk table.

---

## Measure 3: KM Survival (Core Measure)

Computes Kaplan–Meier survival probability at the current timepoint.

```dax
KM_Survival = 
VAR t = MAX(TimePoints[Time])
VAR timesToUse = FILTER(ALL(TimePoints), TimePoints[Time] <= t)
RETURN
IF(
  t = 0,
  1,
  PRODUCTX(
    timesToUse,
    VAR tj = TimePoints[Time]
    VAR dj = CALCULATE(
        COUNTROWS(Patients),
        Patients[FinalDay] = tj,
        Patients[FinalEvent] = 1
      )
    VAR nj = CALCULATE(
        COUNTROWS(Patients),
        Patients[FinalDay] >= tj
      )
    RETURN IF(nj = 0, 1, 1 - DIVIDE(dj, nj))
  )
)
```

**How it works:**
1. Get current timepoint `t` from visual context (e.g., X-axis column).
2. Use `FILTER(ALL(TimePoints), ...)` to get all timepoints ≤ t, ignoring visual filters.
3. For each earlier timepoint `tj`:
   - Count events `dj` at time `tj` (respects group context).
   - Count at-risk `nj` at time `tj` (respects group context).
   - Compute survival factor: `1 - (dj / nj)`.
4. Multiply all factors using `PRODUCTX` to get cumulative survival.

**Key:**
- `ALL(TimePoints)` ensures we iterate over all historical times.
- Group context is preserved (the CALCULATE calls inside PRODUCTX still filter by current group).
- If no one is at risk, returns 1 (no change to survival).

---

## Measure 4: KM with 95% Confidence Interval (Lower)

Greenwood's variance formula for the lower CI bound.

```dax
KM_Lower_CI = 
VAR t = MAX(TimePoints[Time])
VAR timesToUse = FILTER(ALL(TimePoints), TimePoints[Time] <= t)
VAR z = 1.96  -- for 95% CI; use 2.576 for 99%
VAR km = [KM_Survival]
VAR var_km = SUMX(
    timesToUse,
    VAR tj = TimePoints[Time]
    VAR dj = CALCULATE(
        COUNTROWS(Patients),
        Patients[FinalDay] = tj,
        Patients[FinalEvent] = 1
      )
    VAR nj = CALCULATE(
        COUNTROWS(Patients),
        Patients[FinalDay] >= tj
      )
    RETURN
      IF(nj = 0 OR nj - dj = 0, 0, DIVIDE(dj, nj * (nj - dj)))
  )
VAR se = km * SQRT(var_km)
RETURN
MAX(0, km - z * se)  -- clip at 0
```

**Notes:**
- Uses Greenwood's standard error formula.
- `z = 1.96` for 95% CI (1 - 0.05/2 quantile of normal).
- Lower bound clipped at 0 to prevent negative survival.

---

## Measure 5: KM with 95% Confidence Interval (Upper)

```dax
KM_Upper_CI = 
VAR t = MAX(TimePoints[Time])
VAR timesToUse = FILTER(ALL(TimePoints), TimePoints[Time] <= t)
VAR z = 1.96
VAR km = [KM_Survival]
VAR var_km = SUMX(
    timesToUse,
    VAR tj = TimePoints[Time]
    VAR dj = CALCULATE(
        COUNTROWS(Patients),
        Patients[FinalDay] = tj,
        Patients[FinalEvent] = 1
      )
    VAR nj = CALCULATE(
        COUNTROWS(Patients),
        Patients[FinalDay] >= tj
      )
    RETURN
      IF(nj = 0 OR nj - dj = 0, 0, DIVIDE(dj, nj * (nj - dj)))
  )
VAR se = km * SQRT(var_km)
RETURN
MIN(1, km + z * se)  -- clip at 1
```

---

## Measure 6: Total Patients (for validation)

```dax
Total_Patients = COUNTROWS(Patients)
```

---

## Measure 7: Total Events (for validation)

```dax
Total_Events = 
CALCULATE(
  COUNTROWS(Patients),
  Patients[FinalEvent] = 1
)
```

---

## How to Use These Measures in Visuals

### Risk Table (Matrix Visual)

1. Create a new **Matrix** visual.
2. Configure:
   - **Rows**: `Patients[groupVar]` (or other grouping variable)
   - **Columns**: `TimePoints[Time]`
   - **Values**: Drag `AtRisk_AtTime` measure
3. Format:
   - Set column headers to show time values.
   - Right-click columns → Column headers → Text size, etc.

**Result:** A table showing "Number at Risk" per group and timepoint.

### KM Line Chart

1. Create a new **Line Chart** visual.
2. Configure:
   - **X-Axis**: `TimePoints[Time]` (set as Continuous, not Categorical)
   - **Y-Axis**: `KM_Survival` measure
   - **Legend**: `Patients[groupVar]`
3. Optional enhancements:
   - **Tooltips**: Add `Events_AtTime`, `AtRisk_AtTime` to tooltip values.
   - **Series formatting**: Assign colors to groups.

**Result:** Step-function KM curves per group with 0 at time=0, declining with events.

### KM with Confidence Intervals (Advanced)

1. Use a **Combo Chart** or **Line Chart**:
   - X-Axis: `TimePoints[Time]` (Continuous)
   - Y-Axis: `KM_Survival`, `KM_Lower_CI`, `KM_Upper_CI` (as separate lines or shaded area)
   - Legend: `Patients[groupVar]`
2. Format lines:
   - KM line: solid, bold
   - CI lines: dashed, lighter, same color as KM but reduced alpha/dimmed

**Result:** KM curves with confidence interval bands.

---

## Key Points

1. **Context Preservation**: These measures automatically respect:
   - Group filters (if `groupVar` is in visual rows/legend)
   - Page-level slicers on `groupVar` or other attributes
   - Report-level date slicers (if you add time-based filtering)

2. **Filter Removal**: `ALL(TimePoints)` is crucial in `KM_Survival` to ensure the product includes all historical times, not just visible ones.

3. **Performance**: For large datasets (>1M rows), consider:
   - Pre-aggregating `Patients` to patient-group-time triplets.
   - Reducing the number of timepoints.
   - Using `CACHE` functions (Power BI Premium) for repeated subqueries.

4. **Validation**:
   - Confirm `Total_Patients` count.
   - Check `Total_Events` ≤ `Total_Patients`.
   - Manually compute one group's KM at one timepoint and compare.

---

## Copy-Paste Checklist

- [ ] Create measure `Events_AtTime`
- [ ] Create measure `AtRisk_AtTime`
- [ ] Create measure `KM_Survival`
- [ ] (Optional) Create measures for CI bounds
- [ ] Create measures for validation (Total_Patients, Total_Events)
- [ ] Create Matrix for risk table using `AtRisk_AtTime`
- [ ] Create Line Chart for KM using `KM_Survival`
- [ ] Verify groupVar filter/legend works (select different groups and see curves update)
