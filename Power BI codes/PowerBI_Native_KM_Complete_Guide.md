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

### Visual 1: Risk Table (Matrix) — Detailed Steps

The risk table shows "Number at Risk" at each timepoint per group — essential context for interpreting KM curves.

#### Step 1: Insert and Configure
1. **Home tab** → **New Visual** → Select **Matrix**.
2. Drag fields to zones:
   - **Rows**: `Patients[groupVar]`
   - **Columns**: `TimePoints[Time]`
   - **Values**: `AtRisk_AtTime` (measure)

#### Step 2: Basic Formatting
1. **Right-click the Matrix** → **Format visual**.
2. **Row headers**:
   - Text size: 11pt (readable but compact)
   - Font: Segoe UI or Arial
   - Alignment: Left
3. **Column headers**:
   - Text size: 10pt
   - Bold: Yes
4. **Values**:
   - Number format: Whole number, 0 decimals
   - Text size: 10pt
   - Alignment: Center

#### Step 3: Remove Totals (Optional)
1. **Format visual** → **Row headers** → Toggle **Subtotals** to **Off**.
2. **Column headers** → Toggle **Totals** to **Off**.

#### Step 4: Color Coding (Optional)
1. **Right-click Matrix** → **Conditional formatting** → **Background color scale**.
2. Select **Color scales** on Values (AtRisk_AtTime).
3. Choose: Minimum (light blue) → Maximum (dark blue).
4. This helps visualize at-risk counts at a glance.

#### Step 5: Sizing
1. Adjust column width: Drag between column headers in visual.
2. Recommend: 40px per timepoint column + 60px for group row.
3. For 6 timepoints: ~300px total width.

**Result**: Clean, readable risk table

```
groupVar   0   30   60   90  120
────────────────────────────────
GroupA   100  95   88   80   72
GroupB   100  92   84   75   65
GroupC   100  94   87   78   68
```

---

### Visual 2: KM Curve (Line Chart) — Detailed Steps

The main KM curve showing survival probability over time per group.

#### Step 1: Insert and Configure
1. **Home tab** → **New Visual** → Select **Line chart**.
2. Drag fields:
   - **X-Axis**: `TimePoints[Time]`
   - **Y-Axis**: `KM_Survival` (measure)
   - **Legend**: `Patients[groupVar]`

#### Step 2: Make X-Axis Continuous
1. **Right-click the X-Axis** (Time) → **Continuous** (not Categorical).
2. This creates a true time-scale (not evenly spaced categories).

#### Step 3: Axis Configuration
1. **Format visual** → **Y-Axis**:
   - Minimum: 0
   - Maximum: 1
   - Display units: None (or Percentage)
2. **X-Axis**:
   - Show title: Yes → "Time (days)" or your label
   - Title font size: 11pt

#### Step 4: Data Labels & Markers
1. **Format visual** → **Data labels**:
   - Toggle **On**.
   - Display units: (leave default).
   - Decimal places: 2 (e.g., 0.88).
   - Position: **Top** or **Right** (avoid crossing curves).
   - Font size: 9pt.
2. **Format visual** → **Data point**:
   - Show markers: **Yes** (circles at each timepoint).
   - Marker size: 5–8 (visible but not cluttered).

#### Step 5: Line Styles
1. **Format visual** → **Series** → Expand each group's line:
   - Line style: **Solid** (not dashed).
   - Line width: 2–3pt (thick enough to see).
   - Transparency: 0% (fully opaque).

#### Step 6: Legend Positioning
1. **Format visual** → **Legend**:
   - Position: **Right** (outside visual).
   - Legend name: "Treatment Group" (or your label).
   - Legend text size: 10pt.

#### Step 7: Color Assignment (Optional but Recommended)
1. **Right-click curve** → **Assign color**.
2. Assign distinct colors per group:
   - GroupA: Blue
   - GroupB: Red
   - GroupC: Green
   - (Use colorblind-friendly palette: https://coolors.co/palettes/trending)

**Result**: Professional KM curve with clear group distinction

```
Survival Probability
    1.0  ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         │         GroupA (0.95)
    0.8  │ ●●●●●●●●●●●●●●●●●●●●●●●●●●●●
         │         GroupB (0.88)
    0.6  │  ╲●●●●●●●●●●●●●●●●●●●●●●●●●
         │    ╲ GroupC (0.84)
    0.4  │     ╲●●●●●●●●●●●●●●●●●●●●●
         │
    0.2  │      ╲╲●●●●●●●●●●●●●●●●●●
         │
    0.0  └──────╱╱╱───────────────────
        0    30   60   90   120  Time (days)
```

---

### Visual 3: KM with Confidence Intervals (Combo/Area Chart)

For publication-quality visuals, add ±95% confidence bands.

#### Option A: Combo Chart (Best Visual)
1. **Insert Combo Chart**.
2. Configure:
   - **Shared axis (X)**: `TimePoints[Time]` (Continuous).
   - **Column values**: `KM_Lower_CI`, `KM_Upper_CI` (as columns/area).
   - **Line values**: `KM_Survival` (as line, one per group).
3. **Format**:
   - Column axis: **Stacked** (not clustered).
   - Column transparency: **80%** (allows KM line to show).
   - Column fill: Light gray or group-specific light shade.
   - Line: Bold, color per group.

**Result**: KM curve with shaded CI region

```
Survival with 95% CI
    1.0
         ╔═════════════════════════════════╗ CI band
         ║  ●─────────●                   ║ KM curve
    0.8  ║   │╭─────╯ ╲                   ║
         ║   ╰─╯       ╲──●               ║
    0.6  ║              ╲  ╲●──────●      ║
         ║               ╲  ╲     ╱╱      ║
    0.4  ║                ╰──●   ╱╱       ║
         ║                    ╰─╱╱        ║
    0.2  └──────────────────────────────────
        0    30   60   90   120  Time
```

#### Option B: Three Separate Line Charts (Simple Alternative)
1. Create **3 line charts**:
   - Chart 1: KM_Survival only (main).
   - Chart 2: KM_Lower_CI (dashed, thin, faint).
   - Chart 3: KM_Upper_CI (dashed, thin, faint).
2. Overlay on same visual area (if Power BI supports layering).

**Recommendation**: Option A (Combo) is cleaner for publication.

---

### Visual 4: Validation Dashboard

Create a summary card set to verify calculations.

#### Step 1: Add Card Visuals
1. **Insert Card** visual (4 cards total).
2. Assign measures:
   - Card 1: `Total_Patients`
   - Card 2: `Total_Events`
   - Card 3: Calculated measure (Events / Patients) as event rate
   - Card 4: `COUNT(TimePoints[Time])` as number of timepoints

#### Card Configuration
1. **Format each card**:
   - Background: Light gray (#F5F5F5).
   - Text size: 12pt (title), 18pt (value).
   - Title: Identify measure (e.g., "Total Patients").
   - Category labels: Bold.

#### Step 2: Validation Display Format
```
┌──────────────────┬──────────────────┐
│ Total Patients   │  Total Events     │
│      247         │       83          │
└──────────────────┴──────────────────┘
┌──────────────────┬──────────────────┐
│ Event Rate       │  Timepoints      │
│     33.6%        │        6         │
└──────────────────┴──────────────────┘
```

**Expected values**:
- Total_Patients: Match your cohort size.
- Total_Events: ≤ Total_Patients.
- Event Rate: 10–50% typically.
- Timepoints: 4–10 (adjust based on choice).

---

### Visual 5: Interactive Page Layout (Recommended)

Combine all visuals for a complete survival analysis dashboard.

#### Layout Template

```
┌─────────────────── KM SURVIVAL ANALYSIS DASHBOARD ──────────────────┐
│                                                                      │
│  [Slicer: Treatment Group] [Slicer: Cohort] [Slicer: Max Days]   │
│                                                                      │
│  ┌───────────────────────────────┬────────────────────────────┐   │
│  │                               │   Validation Cards         │   │
│  │   KM Survival Curve           │  ┌──────────┬──────────┐   │   │
│  │   (Line Chart)                │  │ Patients │ Events   │   │   │
│  │                               │  │   247    │    83    │   │   │
│  │   [with data labels]          │  └──────────┴──────────┘   │   │
│  │   and CI bands                │  ┌──────────┬──────────┐   │   │
│  │                               │  │Rate (%)  │ TP Count │   │   │
│  │   GroupA ───                  │  │  33.6%   │    6     │   │   │
│  │   GroupB ───                  │  └──────────┴──────────┘   │   │
│  │   GroupC ───                  │                            │   │
│  │                               │                            │   │
│  └───────────────────────────────┴────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Risk Table (Matrix)                                         │  │
│  │  ShowNumber at Risk by Group and Timepoint                   │  │
│  │                                                              │  │
│  │  groupVar │  0  │ 30 │ 60 │ 90 │ 120 │ 150 │               │  │
│  │  ───────────────────────────────────────────                │  │
│  │  GroupA   │ 100 │ 95 │ 88 │ 80 │  72 │  64 │               │  │
│  │  GroupB   │ 100 │ 92 │ 84 │ 75 │  68 │  58 │               │  │
│  │  GroupC   │ 100 │ 94 │ 87 │ 78 │  70 │  62 │               │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

#### Step-by-Step Assembly

1. **Add Slicers** (top row):
   - **Slicer 1**: `Patients[groupVar]` (dropdown or buttons).
   - **Slicer 2**: Cohort column (if applicable).
   - **Slicer 3**: Text input for max days (synced to `max_day` parameter if available).

2. **Left Column** (60% width):
   - **KM Curve** (Line Chart).
   - Takes up ~3/4 of page height.

3. **Right Column** (40% width):
   - **Validation Cards** (4 cards stacked).
   - Takes up ~1/4 of page height.
   - Provides quick sanity checks.

4. **Bottom Row** (100% width):
   - **Risk Table** (Matrix) spanning full width.
   - Height: ~25% of page.

#### Slicer Configuration
1. **Right-click Slicer** → **Format visual**:
   - Style: **Dropdown** (compact) or **Buttons** (visual selection).
   - Search enabled: **Yes** (for many groups).
   - Multi-select: **Yes** (compare specific subsets).

2. **Sync Slicers**:
   - View tab → **Sync slicers** → Enable for all related pages.

---

### Visual 6: Advanced - Multi-Page Report

For comprehensive analysis, create 3 pages:

#### Page 1: Executive Summary (Current Layout)
- KM curves + risk table + validation cards.
- Intended for leadership/presentations.

#### Page 2: Detailed Analysis
- Separate line chart per group (not overlaid).
- Risk table for each group.
- CI bounds visible per group.

#### Page 3: Subgroup Analysis
- Slicers for demographic breakdowns (e.g., age, gender, stage).
- KM curves by subgroup.
- Useful for regulatory submissions.

---

### Common Visual Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| KM curve is jagged/blocky | X-axis is **Categorical** not **Continuous** | Right-click X-axis → **Continuous** |
| Risk table rows in wrong order | groupVar not sorted | Pre-sort groupVar in Patients table or use DAX SORT |
| Colors not matching legend | Color assignment not applied or cached | Refresh visual, reassign color, Ctrl+Shift+R |
| Data labels overlapping | Too many timepoints or font too large | Reduce font size (8pt), use **Right** position |
| Matrix too wide for page | Too many timepoints | Limit to 6 timepoints or use horizontal scrolling |
| Line chart legend shows "Value" | Measure not properly named | Rename measure in fields list or formatting |

---

### Formatting Best Practices

**Color Palette** (colorblind-friendly):
- Blue: #4472C4 (GroupA)
- Red: #ED7D31 (GroupB)
- Green: #70AD47 (GroupC)
- Gray: #A5A5A5 (CI bands)

**Font Guidance**:
- Title: 14pt, Bold
- Axis labels: 11pt
- Data labels: 9pt
- Legend: 10pt

**Spacing**:
- Margin around visuals: 10px
- Gap between sections: 20px
- Top slicer area: 60px height

---

### Result: Production-Ready Dashboard

Your final dashboard exports cleanly to PDF for regulatory submissions, presentations, or publications.

---

## Performance & Validation

### Performance Optimization Strategies

#### Strategy 1: Pre-Aggregation in Power Query (Highest Impact)

**Problem**: Large datasets (>1M rows) slow down DAX calculations.

**Solution**: Aggregate to patient-level in Power Query *before* loading to Power BI.

1. **In Power Query**, after creating the `Patients` table, add a grouping step:
```m
// Structure 2: Pre-aggregate all endpoints
GroupedPatients = Table.Group(
  Patients, 
  {"PT", "groupVar"}, 
  {
    {"Final_Event", each List.Max(List.ReplaceMatchingValues([Event], {null, 0}))},
    {"Final_Day", each List.Min([Day])}
  }
)
```

2. **Load only this aggregated table** into Power BI. Size shrinks significantly:
   - Before: 1M × ~20 columns = 20M cells
   - After: 100K × 4 columns = 400K cells
   - **Reduction: 50x**

**Impact**: DAX measures compute 50× faster.

---

#### Strategy 2: Limit TimePoints (High Impact)

**Problem**: 100 distinct timepoints require 100 iterations in PRODUCTX.

**Solution**: Use Option A (manual) TimePoints with 4–6 points.

**Comparison**:

| Option | Timepoints | Performance | Use Case |
|--------|-----------|-------------|----------|
| Manual (A) | 4–6 | ⚡⚡⚡ Instant | Recommended; clinical milestones |
| Distinct (B) | 10–100 | ⚡ ~1s | Exploratory; many events |
| Auto-spaced (C) | 10–50 | ⚡ ~1s | Evenly-spaced required |

**Recommendation**: Always use Option A for production dashboards.

---

#### Strategy 3: Reduce Patients Table Further (Medium Impact)

If dataset still large after pre-aggregation:

1. **Filter cohort at load time**:
```m
FilteredPatients = Table.SelectRows(Patients, 
  each [FinalDay] <= 365 and [Age] >= 18)
```

2. **Exclude unnecessary columns**:
```m
SelectColumns = Table.SelectColumns(FilteredPatients, 
  {"PT", "groupVar", "Final_Event", "Final_Day"})
```

3. **Result**: Only essential data in Power BI model.

---

#### Strategy 4: Use DAX Measures, Not Calculated Columns (Medium Impact)

❌ **Bad** (slow):
```dax
PatientCount = CALCULATE(COUNTROWS(Patients), Patients[groupVar] = "GroupA")
// Creates overhead if applied as calculated column on every row
```

✅ **Good** (fast):
```dax
[AtRisk_AtTime] = CALCULATE(COUNTROWS(Patients), Patients[FinalDay] >= MAX(TimePoints[Time]))
// Measure computes on-demand per cell context
```

**Rule**: All KM computations must be **measures**, not columns.

---

#### Strategy 5: Enable DirectQuery (If On-Premises Database)

For very large datasets in SQL Server / Azure SQL:

1. In Power BI: **Get Data** → **SQL Server** → **DirectQuery mode**.
2. Push aggregation to database:
```sql
SELECT PT, groupVar, MAX(Event) as Final_Event, MIN(Day) as Final_Day
FROM PatientData
GROUP BY PT, groupVar
```
3. Load minimal result set.

**Trade-off**: Slightly slower than Import; much smaller Power BI file.

---

#### Strategy 6: Power BI Premium CACHE Function (If Available)

For Premium capacity, cache expensive computations:

```dax
KM_Survival_Cached = 
CACHE(
  VAR t = MAX(TimePoints[Time])
  VAR timesToUse = FILTER(ALL(TimePoints), TimePoints[Time] <= t)
  RETURN
  IF(t = 0, 1,
    PRODUCTX(timesToUse,
      VAR tj = TimePoints[Time]
      VAR dj = CALCULATE(COUNTROWS(Patients), Patients[FinalDay] = tj, Patients[FinalEvent] = 1)
      VAR nj = CALCULATE(COUNTROWS(Patients), Patients[FinalDay] >= tj)
      RETURN IF(nj = 0, 1, 1 - DIVIDE(dj, nj))
    )
  )
)
```

**Benefit**: Reuses cached result across page refreshes (same time value).

---

### Validation Checklist (Comprehensive)

#### Data Quality Checks

- [ ] **No nulls in Final_Day**: COUNTA(Patients[FinalDay]) = COUNTROWS(Patients)
- [ ] **No negative days**: MIN(Patients[FinalDay]) ≥ 0
- [ ] **Event is binary**: DISTINCT(Patients[FinalEvent]) = {0, 1}
- [ ] **No reversed times**: Final_Day ≥ 0 for all rows
- [ ] **No duplicate patients**: COUNTROWS(Patients) = DISTINCTCOUNT(Patients[PT])

#### Aggregation Verification

- [ ] **Total_Patients count**: Matches source data record count
- [ ] **Total_Events**: T = COUNTROWS(Patients, FinalEvent=1) ≤ Total_Patients
- [ ] **Event rate**: Total_Events / Total_Patients between 5–70% (typical)
- [ ] **Timepoint coverage**: All timepoints in range [0, MAX(Final_Day)]

#### KM Curve Validation

- [ ] **Starts at 1.0**: KM at time=0 is exactly 1.0
- [ ] **Monotonic**: S(t) is non-increasing (never goes up)
- [ ] **No negative values**: S(t) ≥ 0 for all t
- [ ] **No >1.0 values**: S(t) ≤ 1.0 for all t
- [ ] **Sensible step size**: Survival drops ~1–5% per timepoint (group-dependent)

#### Confidence Interval Validation

- [ ] **Lower CI ≤ Point Estimate**: KM_Lower_CI ≤ KM_Survival
- [ ] **Upper CI ≥ Point Estimate**: KM_Upper_CI ≥ KM_Survival
- [ ] **Both clipped [0,1]**: 0 ≤ KM_Lower_CI ≤ KM_Upper_CI ≤ 1
- [ ] **Symmetric roughly**: |Upper − KM| ≈ |KM − Lower| (Greenwood approximation)

#### Risk Table Validation

- [ ] **At-risk decreasing**: Count decreases or stays same as time progresses
- [ ] **At-risk at t=0 = Total_Patients**: AtRisk_AtTime(t=0) = Total_Patients
- [ ] **Events ≤ At-risk**: Events_AtTime(t) ≤ AtRisk_AtTime(t) for all t
- [ ] **No jumps**: No sudden gaps in at-risk counts (indicates data error)

#### Visual Validation

- [ ] **Curves distinct**: Different groups show visually different survival patterns
- [ ] **Legend matches data**: Legend labels match groupVar values exactly
- [ ] **Axes labeled**: X = "Time (days)", Y = "Probability" or "Survival"
- [ ] **Timepoints evenly spaced**: Or rational intervals (0, 30, 60, 90, ...)

---

### Manual Spot-Check Procedure

Validate one group-timepoint combination using Excel.

**Example: GroupA at Time=60**

#### Step 1: Extract Raw Data
```
Patient | groupVar | FinalDay | FinalEvent
--------|----------|----------|----------
1       | GroupA   | 15       | 0
2       | GroupA   | 30       | 1
3       | GroupA   | 30       | 0
4       | GroupA   | 45       | 1
5       | GroupA   | 60       | 1
6       | GroupA   | 60       | 0
7       | GroupA   | 75       | 0
...
100     | GroupA   | 365      | 0
```

#### Step 2: Calculate At-Risk and Events at Each Timepoint

```
Timepoint | At-Risk | Events | Survival_Factor
----------|---------|--------|------------------
0         | 100     | 0      | 1.0000
30        | 100     | 2      | 0.9800
60        | 98      | 1      | 0.9898
```

**Formulas**:
- **At-Risk(t)**: Count of patients with FinalDay ≥ t
- **Events(t)**: Count of patients with FinalDay = t AND FinalEvent = 1
- **Survival_Factor(t)**: 1 - (Events(t) / At-Risk(t))

#### Step 3: Compute Cumulative KM

$$KM(t) = \prod_{s \leq t} \left(1 - \frac{d_s}{n_s}\right)$$

```
KM(0) = 1.0
KM(30) = 1.0 × 0.9800 = 0.9800
KM(60) = 0.9800 × 0.9898 = 0.9700
```

#### Step 4: Compare with Power BI Measure

1. In Power BI, create a **Table** visual:
   - Rows: `Patients[groupVar]` filtered to "GroupA"
   - Columns: `TimePoints[Time]`
   - Values: `KM_Survival` measure
2. Look up the cell for GroupA × Time=60.
3. **Expected**: KM_Survival ≈ 0.9700 (±0.0001 for rounding).

**If match**: ✅ Calculation correct.  
**If mismatch**: ❌ Debug the DAX measure or data.

---

### Debugging Checklist

| Symptom | Test | Solution |
|---------|------|----------|
| All KM = 1.0 | Check if FinalDay column exists | Verify Power Query step created FinalDay |
| All KM = 0.0 | Check if FinalEvent all 1s | Should be mix of 0s and 1s |
| KM increases | Check monotonicity | Verify final events computed correctly |
| Risk table empty | Check groupVar in Rows | Move to Rows, not Values |
| Different from Python/R | Check timepoint rounding | Ensure manual timepoints match Python list |
| Slow rendering | Check timepoint count | Reduce to ≤6 timepoints |

---

### Expected Output Examples

#### Small Cohort (N=100, 3 groups)

```
TimePoint | GroupA_Risk | GroupA_KM | GroupB_Risk | GroupB_KM | GroupC_Risk | GroupC_KM
----------|-------------|-----------|-------------|-----------|-------------|----------
0         | 33          | 1.000     | 34          | 1.000     | 33          | 1.000
30        | 32          | 0.970     | 33          | 0.970     | 32          | 0.970
60        | 30          | 0.909     | 32          | 0.909     | 31          | 0.936
90        | 28          | 0.864     | 30          | 0.848     | 29          | 0.901
End       | 15          | 0.621     | 18          | 0.606     | 20          | 0.723
```

#### Large Cohort (N=1000, 2 groups)

```
TimePoint | Control_Risk | Control_KM | Treatment_Risk | Treatment_KM
----------|--------------|-----------|----------------|---------------
0         | 500          | 1.000     | 500            | 1.000
30        | 485          | 0.970     | 490            | 0.980
60        | 465          | 0.931     | 475            | 0.960
90        | 445          | 0.878     | 455            | 0.929
120       | 420          | 0.817     | 430            | 0.894
180       | 380          | 0.706     | 395            | 0.821
365       | 250          | 0.445     | 310            | 0.598
```

---

### Publication Checklist

Before sharing results (presentations, regulatory submissions, publications):

- [ ] Validation checks all passed
- [ ] Spot-check matches manual computation
- [ ] N (total patients) clearly labeled in report
- [ ] Follow-up time clearly labeled (median days shown)
- [ ] Event rate clearly stated (X% of cohort experienced event)
- [ ] Number at risk visible in risk table at each timepoint
- [ ] Confidence intervals shown (95% specified)
- [ ] Legend distinguishes all groups clearly
- [ ] Axes properly labeled with units
- [ ] Any censoring assumptions stated in footnote
- [ ] Methods section specifies: "Kaplan–Meier product-limit estimator; Greenwood variance; 95% CI"

---

## Summary: Validation & Performance Reference

**For Speed**:
1. Aggregate to patient-level in Power Query
2. Use ≤6 manual timepoints (Option A)
3. Verify all calculations are measures (not columns)

**For Accuracy**:
1. Pass all validation checks (data quality, aggregation, KM, CI, risk table)
2. Conduct manual spot-check (Excel or calculator)
3. Compare with Python/R reference implementation if available

**For Publication**:
1. Complete all validation checklist items
2. Clearly label N, event rate, follow-up time
3. Ensure footnote specifies KM methodology (product-limit, Greenwood, CI level)

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

