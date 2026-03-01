# Kaplan-Meier Survival Analysis for Power BI

A flexible Python script for generating Kaplan-Meier (KM) survival curves and risk tables directly in Microsoft Power BI.

## Features

- **Dual Data Structure Support**:
  - **Structure 1**: By patient (one row per patient with multiple Event/Day endpoint pairs)
  - **Structure 2**: By patient and endpoint (pre-aggregated by Power BI)
  
- **Interactive KM Plots** with confidence intervals
- **Risk Tables** showing number at risk at specified timepoints
- **Target Survival Reference Lines** (single value or group-specific)
- **Customizable Labels & Titles** via Power BI parameters
- **Optimized Performance** using vectorized pandas operations and scipy

## Usage in Power BI

### Configuration Parameters

Add these Power BI parameters to customize the script:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `pTitle` | Plot title | "Kaplan-Meier Survival Curve" |
| `pXLabel` | X-axis label | "Time (days)" |
| `pYLabel` | Y-axis label | "Survival Probability" |
| `pGroupLabel` | Legend title | "Treatment Group" |
| `pRiskTableTitle` | Risk table title | "Number at Risk" |
| `pTimepoints` | Manual risk table timepoints | "0,30,60,90,120,150" |
| `pMaxDay` | Maximum time cutoff | "365" |
| `pTargetSurvival` | Target survival rate(s) | "0.5" or "Group1:0.75,Group2:0.5" |

### Data Structure Requirements

**Structure 1: By Patient**
```
PT | groupVar | Event1 | Day1 | EventB | DayB | ... 
```
- Specify endpoint suffixes via `pEndpointSuffixes` parameter (e.g., "1,B")
- Script combines multiple events: Final Event = MAX, Final Day = MIN

**Structure 2: By Patient & Endpoint (Power BI Pre-Aggregated)**
- Power BI Power Query should aggregate multiple endpoints before sending to Python
- Dataset should have one of:
  - `PT | groupVar | Event | Day` (standard naming)
  - `PT | groupVar | Event_* | Day_*` (suffix naming)

## Required Python Packages

All packages are pre-installed in Power BI:
- `numpy` - Numerical computing
- `pandas` - Data manipulation
- `scipy` - Scientific computing (z-score calculation)
- `matplotlib` - Visualization

## Key Optimizations

1. **Vectorized operations** for fast risk table computation
2. **Single sort** of groups, reused throughout
3. **scipy.stats** for deterministic z-score calculation
4. **One-time group type conversion** to minimize redundancy

## Notes

- KM curves always start at (0, 1) for visual consistency
- Confidence intervals assume alpha = 0.05 (95% CI)
- Risk table vertical axis uses timepoints you specify
- Reference lines support group-specific colors or single gray line
