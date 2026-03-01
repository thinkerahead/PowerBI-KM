# Power BI Native KM Implementation: Complete Guide

A step-by-step guide to building Kaplan–Meier survival curves and risk tables entirely within Power BI using Power Query and DAX—no Python/R needed.

---

## Table of Contents

1. [Data Preparation (Power Query M)](#data-preparation)
2. [TimePoints Table (DAX)](#timepoints-table)
3. [KM Measures (DAX)](#km-measures)
4. [Building Visuals](#building-visuals)
5. [Performance & Validation](#performance-validation)

---

## Data Preparation (Power Query M)

Transform your raw data into a lean `Patients` table with columns: `PT`, `groupVar`, `FinalEvent`, `FinalDay`.

### Structure 1: By Patient (Multiple EventXX/DayXX Pairs)

**Scenario**: Each patient has one row with columns like `Event1`, `Day1`, `EventB`, `DayB`, etc.

**Power Query Steps:**

1. Create a **Text** parameter `EndpointSuffixes` with value `1,B,C` (adjust to your endpoints).
2. Load your source table.
3. In the Power Query editor, go to **Advanced Editor** and paste:

```m
let
  Source = <YourTableName>,
  Suffixes = List.Transform(Text.Split(Parameter_EndpointSuffixes, ","), Text.Trim),
  EventCols = List.Transform(Suffixes, each "Event" & _),
  DayCols = List.Transform(Suffixes, each "Day" & _),
  
  -- Compute Final_Event = max of selected events (null treated as 0)
  AddFinalEvent = Table.AddColumn(Source, "Final_Event", 
    each List.Max(
      List.Transform(
        Record.ToList(Record.SelectFields(_, EventCols)), 
        each if _ = null then 0 else _
      )
    ), 
    Int64.Type),
  
  -- Compute Final_Day = min of selected days (null = missing, ignored)
  AddFinalDay = Table.AddColumn(AddFinalEvent, "Final_Day",
    each
      let days = List.RemoveNulls(
            List.Transform(
              Record.ToList(Record.SelectFields(_, DayCols)), 
              each try Number.From(_) otherwise null
            )
          )
      in if List.Count(days) = 0 then null else List.Min(days),
    type nullable number),
  
  -- Keep only needed columns
  KeepCols = Table.SelectColumns(AddFinalDay, {"PT", "groupVar", "Final_Event", "Final_Day"})
in
  KeepCols
```

**Output**: Table named `Patients` with 4 columns: `PT`, `groupVar`, `Final_Event`, `Final_Day`.

---

### Structure 2: By Patient & Endpoint (Power BI Pre-Aggregated)

**Scenario**: Each row is a patient-endpoint combination; you've already aggregated endpoints in Power BI.

**Power Query Steps:**

1. Load your source table (should have: `PT`, `groupVar`, `Event`, `Day`).
2. Go to **Advanced Editor** and paste:

```m
let
  Source = <YourTableName>,
  
  -- Group by patient and group, aggregate events/days
  Grouped = Table.Group(Source, {"PT", "groupVar"}, {
      {"Final_Event", each List.Max(List.Transform([Event], each if _ = null then 0 else _)), Int64.Type},
      {"Final_Day", each 
        let days = List.RemoveNulls(List.Transform([Day], each try Number.From(_) otherwise null))
        in if List.Count(days) = 0 then null else List.Min(days), 
        type nullable number}
  }),
  
  Reordered = Table.ReorderColumns(Grouped, {"PT", "groupVar", "Final_Event", "Final_Day"})
in
  Reordered
```

**Output**: Same as Structure 1 — a clean `Patients` table.

---

## TimePoints Table (DAX)

Create a calculated table of timepoints for the risk table and KM plot.

### Option A: Manual Timepoints (Recommended)

Use this if you want specific clinical timepoints (e.g., 30-day, 60-day, 90-day survival).

**DAX Code:**
```dax
TimePoints = 
UNION(
  ROW("Time", 0),
  ROW("Time", 30),
  ROW("Time", 60),
  ROW("Time", 90),
  ROW("Time", 120),
  ROW("Time", 150)
)
```

**Step-by-step in Power BI Desktop:**
1. Home → New → Blank Query → Advanced Editor.
2. Replace all with the DAX code above.
3. Rename the query to `TimePoints`.
4. Load it.

✅ **Pros**: Full control, consistent, aligns with clinical milestones.  
❌ **Cons**: Manual entry.

---

### Option B: Distinct Event Times (Data-Driven)

Use observed event times from the data plus 0.

**DAX Code:**
```dax
TimePoints = 
VAR eventTimes = DISTINCT(SELECTCOLUMNS(ALL(Patients), "Time", Patients[FinalDay]))
VAR withZero = UNION(ROW("Time", 0), eventTimes)
RETURN
SORT(withZero, [Time], ASC)
```

✅ **Pros**: Automatic, data-driven, uses actual event times.  
❌ **Cons**: May produce many timepoints if data is sparse.

---

### Option C: Evenly-Spaced (Auto-Generated)

Generate N equally-spaced timepoints.

**DAX Code:**
```dax
TimePoints = 
VAR maxTime = MAX(ALL(Patients[FinalDay]))
VAR numPoints = 6
VAR timeStep = DIVIDE(maxTime, numPoints - 1)
RETURN
FILTER(
  SELECTCOLUMNS(
    SEQUENCE(numPoints),
    "Time", INT(([Value] - 1) * timeStep)
  ),
  [Time] >= 0
)
```

✅ **Pros**: Fully automatic, clean spacing.  
❌ **Cons**: May produce non-intuitive timepoints (e.g., 0, 23.4, 46.8, ...).

---

## KM Measures (DAX)

Create these measures in Power BI. Each respects group context automatically.

### Core Measures

**Measure 1: AtRisk_AtTime**

Counts patients at risk at each timepoint.

```dax
AtRisk_AtTime = 
VAR t = MAX(TimePoints[Time])
RETURN
CALCULATE(
  COUNTROWS(Patients),
  Patients[FinalDay] >= t
)
```

**Measure 2: Events_AtTime**

Counts events at each timepoint.

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

**Measure 3: KM_Survival** (Core)

Computes Kaplan–Meier survival probability.

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
- For each timepoint ≤ t, compute survival factor: 1 - (events / at-risk).
- Multiply all factors cumulatively.
- Group context is preserved (measures filter by current group automatically).

---

### Confidence Intervals (Optional)

**Measure 4: KM_Lower_CI**

95% lower confidence bound (Greenwood's formula).

```dax
KM_Lower_CI = 
VAR t = MAX(TimePoints[Time])
VAR timesToUse = FILTER(ALL(TimePoints), TimePoints[Time] <= t)
VAR z = 1.96  -- 95% CI; use 2.576 for 99%
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
MAX(0, km - z * se)
```

**Measure 5: KM_Upper_CI**

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
MIN(1, km + z * se)
```

---

### Validation Measures

**Measure 6: Total_Patients**
```dax
Total_Patients = COUNTROWS(Patients)
```

**Measure 7: Total_Events**
```dax
Total_Events = 
CALCULATE(
  COUNTROWS(Patients),
  Patients[FinalEvent] = 1
)
```

---

## Building Visuals

### Visual 1: Risk Table (Matrix)

1. **Insert a Matrix visual**.
2. Configure:
   - **Rows**: Drag `Patients[groupVar]` to Rows.
   - **Columns**: Drag `TimePoints[Time]` to Columns.
   - **Values**: Drag `AtRisk_AtTime` measure to Values.
3. **Format**:
   - Right-click column headers → disable "Total" if unwanted.
   - Adjust column width for readability.
   - Set number format to whole number (no decimals).

**Result**: A table showing "Number at Risk" per group and timepoint.

| groupVar | 0 | 30 | 60 | 90 |
|----------|---|----|----|-----|
| GroupA   | 100 | 95 | 88 | 80 |
| GroupB   | 100 | 92 | 84 | 75 |

---

### Visual 2: KM Curve (Line Chart)

1. **Insert a Line Chart visual**.
2. Configure:
   - **X-Axis**: Drag `TimePoints[Time]`.
   - **Y-Axis**: Drag `KM_Survival` measure.
   - **Legend**: Drag `Patients[groupVar]`.
3. **Format**:
   - X-Axis: Set to **Continuous** (not Categorical).
   - Y-Axis: Set range to 0–1.
   - Add data labels if desired (show value at each point).

**Result**: Step-function KM curves per group, declining from 1.0 at time 0.

---

### Visual 3: KM with Confidence Intervals (Advanced)

1. **Insert a Combo Chart** (or use Ribbon chart if available).
2. Configure:
   - **X-Axis**: `TimePoints[Time]` (Continuous).
   - **Y-Axis (Line)**: `KM_Survival` (one per group).
   - **Y-Axis (Column, or secondary Line)**: `KM_Lower_CI` and `KM_Upper_CI`.
3. **Alternatively**, create three separate line charts and overlay (less ideal but works).

**Result**: KM curves with confidence interval bands.

---

### Visual 4: Validation Cards

Create simple **Card** visuals for quick checks:

1. Card 1: `Total_Patients`
2. Card 2: `Total_Events`
3. Card 3: `COUNT(TimePoints[Time])`

Verify these match expected values.

---

## Performance & Validation

### Performance Tips

1. **Pre-aggregate in Power Query**: Ensure `Patients` table is as lean as possible (only PT, groupVar, FinalEvent, FinalDay).
2. **Limit TimePoints**: Use Option A (manual) rather than Option B (distinct) to avoid generating hundreds of timepoints.
3. **Reduce Patients table size**: If dataset is >1M rows:
   - Pre-filter to relevant cohorts at data load time.
   - Aggregate to patient-level before loading (not in DAX).
4. **Use Measures, not Columns**: All computations should be measures, not calculated columns on Patients.
5. **Cache subqueries** (Power BI Premium): For large `KM_Survival` measure, consider using `CACHE` to avoid recalculating subsets.

### Validation Checklist

- [ ] Count of `Total_Patients` matches source data.
- [ ] `Total_Events` ≤ `Total_Patients`.
- [ ] Risk table shows decreasing counts down the columns as time progresses.
- [ ] KM survival starts at 1.0 and is non-increasing (monotonic descent).
- [ ] KM curves for different groups are visually distinct (not identical).
- [ ] Confidence intervals are symmetric around KM point estimate (roughly).
- [ ] No negative survival values or >1.0 values.
- [ ] Manually compute KM at one group-timepoint using Excel and compare (spot check).

### Manual Spot Check Example

**For GroupA at time=60:**
1. Count Events at t=60: `Events_AtTime` = e.g., 5
2. Count At-Risk at t=60: `AtRisk_AtTime` = e.g., 88
3. Compute factors:
   - At t=30: events=7, at-risk=100 → factor = 1 - 7/100 = 0.93
   - At t=60: events=5, at-risk=88 → factor = 1 - 5/88 = 0.9432
4. KM(t=60) = 0.93 × 0.9432 ≈ 0.877
5. Compare with `KM_Survival` measure showing for GroupA at t=60 → should match ~0.877.

---

## Summary: Step Order

1. **Load and transform data in Power Query** using Structure 1 or 2 template → output `Patients` table.
2. **Create `TimePoints` table** in DAX (choose Option A, B, or C).
3. **Create all measures** in Power BI (AtRisk, Events, KM, CI bounds, validation).
4. **Build visuals**:
   - Risk table (Matrix).
   - KM curve (Line Chart).
   - Optional: CI bands, validation cards.
5. **Test and validate** using the spot-check method above.
6. **Optimize** if model is slow (reduce timepoints, pre-aggregate further).

---

## Notes

- **Slicers integrate automatically**: If you add a slicer on `groupVar` or other patient attributes, visuals update instantly.
- **No external packages**: Everything runs natively in Power BI Desktop and Service.
- **No time-based columns needed**: If you don't have calendar tables, KM works fine with numeric time.
- **Supports both Desktop and Service**: All DAX is compatible with Power BI Service (no special enterprise features required).

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| KM curve doesn't start at 1.0 | Missing t=0 in TimePoints | Add ROW("Time", 0) to TimePoints table |
| KM values are all 1.0 | `FinalEvent` column is all 0s or misnamed | Check Patients table; ensure events are labeled 1 for occurrence, 0 for censored |
| Matrix risk table is empty | groupVar not in rows | Ensure groupVar is dragged to **Rows**, not Values |
| Curves are identical across groups | GROUP context lost in measure | Check that groupVar is in visual's Legend or Rows; avoid wrapping measure with `ALL(Patients)` |
| Slow rendering (large dataset) | Too many distinct timepoints | Use Option A (manual) TimePoints with ~6 timepoints max; pre-filter Patients to relevant cohort |

---

## Examples: Expected Output

### Example Risk Table (3 Groups, 5 Timepoints)

```
Group     0    30    60    90   120
-------- --- ----- ----- ----- ----
Control  100   92   84   75   68
TrtA     100   94   86   79   72
TrtB     100   96   89   83   78
```

### Example KM Values (GroupA)

```
Time  Events  AtRisk  KM_Surv  Lower_CI  Upper_CI
---   ------  ------  -------  --------  --------
0     0       100     1.000    1.000     1.000
30    8       100     0.920    0.885     0.949
60    5       92      0.875    0.835     0.910
90    9       87      0.800    0.755     0.841
120   7       78      0.725    0.672     0.774
```

---

## References

- **Kaplan–Meier Estimator**: https://en.wikipedia.org/wiki/Kaplan–Meier_estimator
- **Greenwood's Formula**: Standard variance estimation for survival curves (see any biostat textbook).
- **Power BI DAX**: https://learn.microsoft.com/en-us/dax/

