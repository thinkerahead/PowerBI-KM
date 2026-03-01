import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt

# ============================================================================
# FLEXIBLE KM PLOT FOR POWER BI - Handles two data structures:
# Structure 1: By patient (one row per patient with Event1, Day1, EventB, DayB, etc)
# Structure 2: By patient and endpoint (one row per patient-endpoint with Endpoint column)
# ============================================================================

# === CONFIGURATION ===
group_col = "groupVar"      # Column name for grouping variable
ci = True                   # Confidence intervals
alpha = 0.05
n_timepoints_risk = 6       # Number of columns in risk table

# Plot labels and titles
plot_title = "Kaplan-Meier Survival Curve"     # Title of the plot - MODIFY IN POWER BI PARAMETER
x_label = "Time"                               # X-axis label - MODIFY IN POWER BI PARAMETER
y_label = "Survival Probability"               # Y-axis label - MODIFY IN POWER BI PARAMETER
group_label = "Group"                          # Legend title for grouping variable - MODIFY IN POWER BI PARAMETER
risk_table_title = "Number at Risk"            # Risk table title - MODIFY IN POWER BI PARAMETER

# Target survival rate(s) for reference lines
# Format: single value (e.g., "0.5") applies to all groups, or group-specific (e.g., "Group1:0.75,Group2:0.5")
target_survival_rates = ""                     # Comma-separated values - MODIFY IN POWER BI PARAMETER
show_reference_lines = True                    # Whether to show target survival lines

# For Structure 1: User selects endpoint suffixes via parameter (e.g., "1,B,C")
# For Structure 2: Slicer filters the dataset, script uses all Endpoint values
structure_type = "auto"     # "auto" = detect, "structure1" = by patient, "structure2" = by patient-endpoint
endpoint_suffixes = ""      # For Structure 1: comma-separated list (e.g., "1,B,C") - MODIFY IN POWER BI PARAMETER
endpoint_col = "Endpoint"   # For Structure 2: column name for endpoint
pt_col = "PT"               # Patient ID column

# Risk table timepoints: manually selected via parameter (e.g., "0,30,60,90,120,150")
manual_timepoints = ""      # Comma-separated list of timepoints - MODIFY IN POWER BI PARAMETER
max_day_cutoff = None       # Optional: cutoff time for plot and risk table (e.g., 365) - MODIFY IN POWER BI PARAMETER if needed

# ============================================================================
# Detect and prepare data
df = dataset.copy()

# Detect structure
def detect_structure(df):
    """Returns 'structure1' or 'structure2' based on columns"""
    if endpoint_col in df.columns and "Endpoint" in df.columns:
        return "structure2"
    else:
        return "structure1"

if structure_type == "auto":
    structure_type = detect_structure(df)

# Validate required columns
if group_col not in df.columns:
    raise RuntimeError(f"Required column '{group_col}' not found in dataset.")
if pt_col not in df.columns:
    raise RuntimeError(f"Required column '{pt_col}' not found in dataset.")

# ============================================================================
# STRUCTURE 1: By patient (multiple Event/Day column pairs)
# ============================================================================
if structure_type == "structure1":
    if not endpoint_suffixes:
        raise RuntimeError("For Structure 1, specify endpoint_suffixes parameter (e.g., '1,B,C')")
    
    # Parse endpoint suffixes
    suffixes = [s.strip() for s in endpoint_suffixes.split(",") if s.strip()]
    
    # Find Event and Day columns for each suffix
    event_cols = [f"Event{s}" for s in suffixes]
    day_cols = [f"Day{s}" for s in suffixes]
    
    # Verify columns exist
    for col in event_cols + day_cols:
        if col not in df.columns:
            raise RuntimeError(f"Column '{col}' not found in dataset for suffix selection '{endpoint_suffixes}'")
    
    # Create combined final event and day
    # Final Event = max of selected events, Final Day = min of selected days
    df["Final_Event"] = df[event_cols].fillna(0).astype(int).max(axis=1)
    df["Final_Day"] = df[day_cols].fillna(np.inf).min(axis=1)
    df["Final_Day"] = df["Final_Day"].replace(np.inf, np.nan)
    
    time_col = "Final_Day"
    event_col = "Final_Event"

# ============================================================================
# STRUCTURE 2: By patient and endpoint (Power BI pre-aggregates endpoints)
# Assumes Power BI has already combined multiple endpoints into single Event/Day columns
# Optional naming: Event/Day or _Event/_Day with a suffix (e.g., Event_combined/Day_combined)
# ============================================================================
elif structure_type == "structure2":
    # Find Event and Day columns - support both Event/Day and suffix naming
    # Check for _Event/_Day pattern first (e.g., _Event, _Day)
    potential_event_cols = [col for col in df.columns if col.endswith("_Event")]
    potential_day_cols = [col for col in df.columns if col.endswith("_Day")]
    
    if potential_event_cols and potential_day_cols:
        # Use the _Event/_Day suffix naming (assume single pair)
        event_col = potential_event_cols[0]
        time_col = potential_day_cols[0]
    elif "Event" in df.columns and "Day" in df.columns:
        # Use standard Event/Day naming
        event_col = "Event"
        time_col = "Day"
    else:
        raise RuntimeError("For Structure 2, dataset must contain either (Event, Day) or (_Event, _Day) columns. Power BI should pre-aggregate endpoints.")
    
    # Verify columns exist
    if event_col not in df.columns:
        raise RuntimeError(f"Column '{event_col}' not found in dataset.")
    if time_col not in df.columns:
        raise RuntimeError(f"Column '{time_col}' not found in dataset.")
else:
    raise RuntimeError(f"Unknown structure_type: {structure_type}")

# ============================================================================
# Clean and prepare data
df = df[[pt_col, group_col, time_col, event_col]].dropna()
df[time_col] = pd.to_numeric(df[time_col], errors="coerce")
df[event_col] = pd.to_numeric(df[event_col], errors="coerce").astype(int)
df = df.dropna(subset=[time_col, event_col])

# Convert group column to string once for all downstream operations
df[group_col] = df[group_col].astype(str)

# Apply max_day cutoff if specified
if max_day_cutoff is not None:
    max_day_cutoff = float(max_day_cutoff)
    df = df[df[time_col] <= max_day_cutoff].copy()
    if df.empty:
        raise RuntimeError(f"No data remaining after applying max_day_cutoff={max_day_cutoff}")

# Parse manual timepoints
if manual_timepoints and manual_timepoints.strip():
    try:
        timepoints = np.array([float(t.strip()) for t in manual_timepoints.split(",") if t.strip()])
        timepoints = np.sort(timepoints)
    except ValueError:
        raise RuntimeError(f"Invalid manual_timepoints format: '{manual_timepoints}'. Use comma-separated numbers (e.g., '0,30,60,90').")
else:
    # Fallback: auto-generate timepoints if not specified
    max_time = df[time_col].max() if not df.empty else 0.0
    timepoints = np.linspace(0.0, max_time, n_timepoints_risk)
    timepoints = np.unique(np.round(timepoints, 8))

# Get unique groups from filtered data (responsive to Power BI filters)
# STORE SORTED GROUPS ONCE - reuse throughout
groups_sorted = sorted(df[group_col].unique())

if len(groups_sorted) == 0:
    raise RuntimeError("No data available after filtering.")

# Compute z value for confidence intervals using scipy (deterministic, fast)
z = stats.norm.ppf(1 - alpha / 2)

def km_by_group(times, events):
    """Compute Kaplan-Meier survival estimates"""
    order = np.argsort(times)
    times = times[order]
    events = events[order]
    unique_times = np.unique(times[events == 1])  # event times only
    n = len(times)
    S = []
    tvals = []
    var_terms = []
    cum_var = 0.0
    surv = 1.0
    at_risk = n
    idx = 0
    for t in unique_times:
        d = int(((times == t) & (events == 1)).sum())
        # compute number at risk just before time t
        at_risk = int((times >= t).sum())
        if at_risk <= 0:
            continue
        # update survival
        surv = surv * (1.0 - d / at_risk)
        # Greenwood variance term for this time
        if at_risk - d > 0:
            var_term = d / (at_risk * (at_risk - d))
        else:
            var_term = 0.0
        cum_var += var_term
        S.append(surv)
        tvals.append(t)
        var_terms.append(cum_var)
    S = np.array(S) if len(S) else np.array([1.0])
    tvals = np.array(tvals) if len(tvals) else np.array([0.0])
    var_terms = np.array(var_terms) if len(var_terms) else np.array([0.0])
    se = S * np.sqrt(var_terms)
    lower = np.clip(S - z * se, 0, 1)
    upper = np.clip(S + z * se, 0, 1)
    return {"times": tvals, "surv": S, "se": se, "lower": lower, "upper": upper}

# Compute KM per group
km_results = {}
for g in groups_sorted:
    sub = df[df[group_col] == g]
    res = km_by_group(sub[time_col].values, sub[event_col].values)
    km_results[g] = res

# VECTORIZED RISK TABLE COMPUTATION
# For each timepoint, count how many patients are at risk in each group
risk_data = []
for g in groups_sorted:
    sub = df[df[group_col] == g]
    risks = [(sub[time_col] >= t).sum() for t in timepoints]
    risk_data.append([g] + risks)

risk_table = pd.DataFrame(risk_data, columns=["group"] + [float(t) for t in timepoints]).set_index("group")

# Plotting
plt.style.use("seaborn-v0_8-whitegrid")
fig = plt.figure(figsize=(10, 7))
ax_km = fig.add_axes([0.1, 0.35, 0.85, 0.6])  # main KM plot
colors = plt.cm.tab10.colors

# Determine x-axis limit
x_max = max_day_cutoff if max_day_cutoff is not None else max(timepoints) if len(timepoints) > 0 else 1

for i, g in enumerate(groups_sorted):
    res = km_results[g]
    # step plot: prepend time 0 and survival 1 (always starts at (0, 1))
    x = np.concatenate(([0.0], res["times"]))
    y = np.concatenate(([1.0], res["surv"]))
    ax_km.step(x, y, where="post", label=str(g), color=colors[i % len(colors)], linewidth=2)
    if ci and len(res["times"]) > 0:
        # create step arrays for ci
        lower = np.concatenate(([1.0], res["lower"]))
        upper = np.concatenate(([1.0], res["upper"]))
        ax_km.fill_between(x, lower, upper, step='post', alpha=0.2, color=colors[i % len(colors)])

# Parse and add target survival rate reference lines
if show_reference_lines and target_survival_rates and target_survival_rates.strip():
    try:
        # Check if format is group-specific (e.g., "Group1:0.75,Group2:0.5") or single value (e.g., "0.5")
        if ":" in target_survival_rates:
            # Group-specific format
            group_rates = {}
            for item in target_survival_rates.split(","):
                parts = item.strip().split(":")
                if len(parts) == 2:
                    group_rates[parts[0].strip()] = float(parts[1].strip())
            # Draw lines for each group with specified rate
            for g, rate in group_rates.items():
                if g in groups_sorted:
                    ax_km.axhline(y=rate, color=colors[groups_sorted.index(g) % len(colors)], 
                                  linestyle='--', alpha=0.5, linewidth=1.5)
        else:
            # Single value applies to all groups
            rate = float(target_survival_rates.strip())
            ax_km.axhline(y=rate, color='gray', linestyle='--', alpha=0.5, linewidth=1.5, label=f'Target: {rate}')
    except (ValueError, IndexError) as e:
        pass  # Silently skip if target rates are invalid

ax_km.set_ylim(-0.05, 1.05)
ax_km.set_xlim(0, x_max)
ax_km.set_xlabel(x_label, fontsize=11)
ax_km.set_ylabel(y_label, fontsize=11)
ax_km.set_title(plot_title, fontsize=12, fontweight='bold')
ax_km.legend(title=group_label, loc="best", fontsize="small")
ax_km.grid(True, alpha=0.3)

# risk table subplot
ax_table = fig.add_axes([0.1, 0.05, 0.85, 0.25])
ax_table.axis('off')

# prepare table data: rows=groups, cols=timepoints
cell_text = []
for g in groups_sorted:
    row = [str(int(risk_table.loc[g, t])) for t in risk_table.columns]
    cell_text.append(row)

col_labels = [f"{float(t):.1f}" for t in risk_table.columns]
table = ax_table.table(cellText=cell_text, rowLabels=groups_sorted, colLabels=col_labels,
                       cellLoc='center', rowLoc='center', loc='center',
                       colWidths=[0.08] * len(col_labels))
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 1.5)
ax_table.text(0.05, 0.9, risk_table_title, fontsize=10, fontweight='bold', transform=ax_table.transAxes)

plt.tight_layout(rect=[0, 0.02, 1, 0.98])
plt.show()

# ============================================================================
# Expose risk_table for Power BI
# Reset index to make group a regular column for better Power BI integration
risk_table_output = risk_table.reset_index().rename(columns={"group": group_col})
risk_table_output