# Power BI DAX: TimePoints Table for Kaplan–Meier

This guide provides multiple methods to create the `TimePoints` table in Power BI Desktop.
Copy the DAX code into your Power BI model as a **Calculated Table**.

---

## Option 1: Manual Timepoints (Recommended for Control)

Use this when you want to specify exact timepoints (e.g., 0, 30, 60, 90, 120, 150 days).

### DAX Code
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

**Pros:**
- Full control over timepoints
- Consistent across reports
- Aligns with Power BI parameter-based approach

**Cons:**
- Manual entry required
- Must update if timepoint strategy changes

---

## Option 2: Parameterized Timepoints (Best for Flexibility)

Use a Power BI parameter with comma-separated values.

### Setup Steps

1. **Create a Parameter** in Power BI Desktop:
   - Home → New Parameter → Numeric (or Text)
   - Name: `pTimePoints`
   - Suggested values: `0,30,60,90,120,150` (as text)

2. **Create the TimePoints Table:**

```dax
TimePoints = 
VAR timeString = GENERATESERIES(0, MAX(Patients[FinalDay]), 30)
RETURN
SELECTCOLUMNS(
  timeString,
  "Time", [Value]
)
```

**Alternative** (if using a Text parameter with comma-separated values):

```dax
TimePoints = 
VAR timeText = "0,30,60,90,120,150"  -- or reference your parameter
VAR timeList = TEXTSPLIT(timeText, ",")
RETURN
ADDCOLUMNS(
  FILTER(
    SELECTCOLUMNS(SEQUENCE(LEN(timeList)), "Index", [Value]),
    [Index] <= LEN(timeList)
  ),
  "Time", VALUE(TRIM(INDEX(timeList, [Index])))
)
```

**Pros:**
- Parameterized; easy to change across all reports
- Flexible

**Cons:**
- Requires parameter setup
- More complex DAX for parsing

---

## Option 3: Distinct Event Times from Data

Use observed event times in the dataset (no manual configuration).

### DAX Code

```dax
TimePoints = 
VAR eventTimes = DISTINCT(SELECTCOLUMNS(Patients, "Time", Patients[FinalDay]))
VAR withZero = UNION(ROW("Time", 0), eventTimes)
RETURN
SORT(withZero, [Time], ASC)
```

**Pros:**
- Data-driven; no manual maintenance
- Always includes all observed event times

**Cons:**
- May produce many timepoints if data is sparse by time
- Risk table becomes wide if many distinct times

---

## Option 4: Evenly-Spaced Timepoints (Auto-Generated)

Generate N equally-spaced timepoints from 0 to max follow-up time.

### DAX Code

```dax
TimePoints = 
VAR maxTime = MAX(Patients[FinalDay])
VAR numPoints = 6  -- change to desired number
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

**Pros:**
- Automatic, no configuration
- Clean spacing

**Cons:**
- Less intuitive timepoints (e.g., 0, 23.4, 46.8,...)
- Best paired with rounding for display

---

## Option 5: Quartile/Decile Timepoints

Use percentiles of event times.

### DAX Code

```dax
TimePoints = 
VAR quartiles = UNION(
  ROW("Time", PERCENTILE.INC(ALL(Patients[FinalDay]), 0.00)),
  ROW("Time", PERCENTILE.INC(ALL(Patients[FinalDay]), 0.25)),
  ROW("Time", PERCENTILE.INC(ALL(Patients[FinalDay]), 0.50)),
  ROW("Time", PERCENTILE.INC(ALL(Patients[FinalDay]), 0.75)),
  ROW("Time", MAX(ALL(Patients[FinalDay])))
)
RETURN
SORT(DISTINCT(SELECTCOLUMNS(quartiles, "Time", INT([Time]))), [Time], ASC)
```

**Pros:**
- Statistically meaningful
- Ensures coverage across entire follow-up range
- Auto-adjusts to data

**Cons:**
- Less intuitive for clinicians/stakeholders
- May require explanation

---

## Recommended Approach for Power BI KM

**Use Option 1 (Manual) or Option 2 (Parameterized)** because:

1. **Consistency**: Same timepoints across all users and reports
2. **Align with clinical markers**: E.g., 1-month, 3-month, 6-month, etc.
3. **Control**: No surprises from data-driven changes
4. **Simplicity**: Easy to understand and modify

---

## After Creating TimePoints Table

### Validation (in Power BI):
1. Create a simple card visual showing `COUNT(TimePoints[Time])` — should match your count (e.g., 6 for Option 1).
2. Create another card showing `MIN(TimePoints[Time])` and `MAX(TimePoints[Time])` — verify the range.

### Usage in Visuals:
- **Risk Table**: Place `TimePoints[Time]` in Columns, `Patients[groupVar]` in Rows, and `AtRiskAtTime` measure as Values.
- **KM Line Chart**: Place `TimePoints[Time]` on X-axis (set as continuous), `KM_Survival` measure on Y-axis, `Patients[groupVar]` as Legend.

---

## Example: Copy-Paste Ready for Option 1

Paste this into a new Calculated Table in Power BI:

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

Then press Enter. The table will appear in your model and be available for visuals.

---

## Notes

- **Data Type**: Ensure `TimePoints[Time]` is numeric (whole number).
- **Sorting**: Use the column for sort order if needed in visuals.
- **Blanks**: If data has gaps (no events on certain days), the DAX measures still compute correctly — they count "at risk" cumulatively.
- **Performance**: For large datasets, prefer Option 1 (manual) over Option 3 (distinct) to avoid generating hundreds of timepoints.
