# PowerBI_KM.R
# Kaplan-Meier plot + risk table for Power BI (R script)
# Place this file in the folder used by your Power BI Python/R visual.

# ------------------------
# Configuration (modify via Power BI parameters)
# ------------------------
group_col <- "groupVar"        # grouping column name
pt_col <- "PT"                 # patient id column
structure_type <- "auto"       # "auto", "structure1", "structure2"
endpoint_suffixes <- ""        # for structure1: e.g. "1,B,C"
endpoint_col <- "Endpoint"     # for structure2 (if present)

# plotting labels
plot_title <- "Kaplan-Meier Survival Curve"
x_label <- "Time"
y_label <- "Survival Probability"
group_label <- "Group"
risk_table_title <- "Number at Risk"

# timepoints and cutoff
manual_timepoints <- ""   # e.g. "0,30,60,90,120" or empty for auto
max_day_cutoff <- NA        # numeric or NA

# reference line(s)
target_survival_rates <- ""  # e.g. "0.5" or "GroupA:0.75,GroupB:0.5"
show_reference_lines <- TRUE

# CI settings
ci <- TRUE
alpha <- 0.05

# ------------------------
# Dependencies
# ------------------------
# The script uses base R plus 'survival' and 'ggplot2'.
# If 'gridExtra' is available we use it to render the risk table.

if(!requireNamespace("survival", quietly = TRUE)) stop("Package 'survival' is required")
if(!requireNamespace("ggplot2", quietly = TRUE)) stop("Package 'ggplot2' is required")
has_gridExtra <- requireNamespace("gridExtra", quietly = TRUE)

library(survival)
library(ggplot2)
if(has_gridExtra) library(gridExtra)

# ------------------------
# Input dataset (Power BI provides a data.frame named 'dataset')
# ------------------------
if(!exists("dataset")) stop("Power BI must supply a data.frame named 'dataset'")
df <- dataset

# ------------------------
# Detect structure
# ------------------------
detect_structure <- function(df){
  # If explicit Endpoint column exists, assume structure2
  if(endpoint_col %in% names(df) || ("Endpoint" %in% names(df))) return("structure2")
  # otherwise structure1
  return("structure1")
}

if(structure_type == "auto") structure_type <- detect_structure(df)

# ------------------------
# STRUCTURE 1: By-patient with EventXX/DayXX pairs
# ------------------------
if(structure_type == "structure1"){
  if(nchar(endpoint_suffixes) == 0) stop("For structure1 provide endpoint_suffixes (e.g. '1,B')")
  suffixes <- unlist(strsplit(endpoint_suffixes, ","))
  suffixes <- trimws(suffixes)
  event_cols <- paste0("Event", suffixes)
  day_cols <- paste0("Day", suffixes)
  missing_cols <- setdiff(c(event_cols, day_cols), names(df))
  if(length(missing_cols)) stop(paste("Missing columns:", paste(missing_cols, collapse = ", ")))
  # compute final event/day per patient
  df$Final_Event <- do.call(pmax, c(df[event_cols], na.rm = TRUE))
  # for min, replace NA with Inf so pmin works
  df_tmp <- lapply(df[day_cols], function(x) ifelse(is.na(x), Inf, x))
  df$Final_Day <- do.call(pmin, df_tmp)
  df$Final_Day[is.infinite(df$Final_Day)] <- NA
  time_col <- "Final_Day"
  event_col <- "Final_Event"
}

# ------------------------
# STRUCTURE 2: One pair Event/Day (Power BI pre-aggregated)
# Supports Event/Day or columns ending with _Event/_Day
# ------------------------
if(structure_type == "structure2"){
  # find suffix pattern first
  ev_cols <- grep("_Event$", names(df), value = TRUE)
  dy_cols <- grep("_Day$", names(df), value = TRUE)
  if(length(ev_cols) > 0 && length(dy_cols) > 0){
    event_col <- ev_cols[1]
    time_col <- dy_cols[1]
  } else if(all(c("Event","Day") %in% names(df))){
    event_col <- "Event"
    time_col <- "Day"
  } else {
    stop("Structure2 requires either Event/Day or *_Event/*_Day columns. Pre-aggregate in Power BI.")
  }
}

# ------------------------
# Clean and prepare
# ------------------------
required_cols <- c(pt_col, group_col, time_col, event_col)
missing <- setdiff(required_cols, names(df))
if(length(missing)) stop(paste("Missing required columns:", paste(missing, collapse = ", ")))

# keep only needed columns
df <- df[, required_cols]
# coerce
df[[time_col]] <- as.numeric(df[[time_col]])
df[[event_col]] <- as.integer(df[[event_col]])
df[[group_col]] <- as.character(df[[group_col]])
# drop NA time/event
df <- df[!is.na(df[[time_col]]) & !is.na(df[[event_col]]), , drop = FALSE]

# apply max_day_cutoff
if(!is.na(max_day_cutoff)){
  df <- df[df[[time_col]] <= as.numeric(max_day_cutoff), , drop = FALSE]
}

# parse manual_timepoints
if(nchar(manual_timepoints) > 0){
  tps <- as.numeric(unlist(strsplit(manual_timepoints, ",")))
  timepoints <- sort(unique(na.omit(tps)))
} else {
  max_time <- max(df[[time_col]], na.rm = TRUE)
  timepoints <- unique(round(seq(0, max_time, length.out = 6), 8))
}

if(length(timepoints) == 0) stop("No timepoints available for risk table")

# sorted groups
groups_sorted <- sort(unique(df[[group_col]]))

# ------------------------
# Compute KM per group
# ------------------------
km_results <- list()
for(g in groups_sorted){
  sub <- df[df[[group_col]] == g, , drop = FALSE]
  if(nrow(sub) == 0){
    km_results[[g]] <- NULL
    next
  }
  fit <- survfit(Surv(sub[[time_col]], sub[[event_col]]) ~ 1)
  s <- summary(fit, times = sort(unique(sub[[time_col]])))
  # collect times, surv, lower, upper
  km_results[[g]] <- list(times = s$time, surv = s$surv, lower = s$lower, upper = s$upper)
}

# ------------------------
# Risk table counts
# ------------------------
risk_rows <- lapply(groups_sorted, function(g){
  sub <- df[df[[group_col]] == g, , drop = FALSE]
  sapply(timepoints, function(t) sum(sub[[time_col]] >= t, na.rm = TRUE))
})
risk_table <- data.frame(group = groups_sorted, do.call(rbind, risk_rows), stringsAsFactors = FALSE)
colnames(risk_table) <- c(group_col, as.character(timepoints))

# ------------------------
# Plotting using ggplot2
# ------------------------
plot_df <- do.call(rbind, lapply(groups_sorted, function(g){
  res <- km_results[[g]]
  if(is.null(res)) return(NULL)
  data.frame(group = g, time = c(0, res$times), surv = c(1, res$surv), lower = c(1, res$lower), upper = c(1, res$upper))
}))

p <- ggplot(plot_df, aes(x = time, y = surv, color = group, fill = group)) +
  geom_step(direction = "hv", size = 1) +
  theme_minimal() +
  labs(title = plot_title, x = x_label, y = y_label, color = group_label, fill = group_label)

if(ci){
  p <- p + geom_ribbon(aes(ymin = lower, ymax = upper), alpha = 0.15, colour = NA)
}

# reference lines
if(show_reference_lines && nchar(target_survival_rates) > 0){
  if(grepl(":", target_survival_rates)){
    items <- unlist(strsplit(target_survival_rates, ","))
    for(it in items){
      parts <- unlist(strsplit(it, ":"))
        if(length(parts) == 2){
        gname <- trimws(parts[1]); rate <- as.numeric(trimws(parts[2]))
        if(gname %in% groups_sorted){
          # Draw group-specific reference lines as gray dashed lines (avoid extra package deps)
          p <- p + geom_hline(yintercept = rate, linetype = "dashed", color = "gray", alpha = 0.6)
        }
      }
    }
  } else {
    rate <- as.numeric(target_survival_rates)
    if(!is.na(rate)) p <- p + geom_hline(yintercept = rate, linetype = "dashed", color = "gray", alpha = 0.6)
  }
}

# set x limit to max_day_cutoff or max timepoint
xmax <- if(!is.na(max_day_cutoff)) as.numeric(max_day_cutoff) else max(timepoints, na.rm = TRUE)
p <- p + xlim(0, xmax) + ylim(0,1)

# arrange plot + risk table (if gridExtra available)
if(has_gridExtra){
  tbl <- gridExtra::tableGrob(risk_table, rows = NULL)
  gridExtra::grid.arrange(p, tbl, ncol = 1, heights = c(3,1))
} else {
  # print plot only, and silently return risk_table as a variable
  print(p)
}

# Expose risk_table object (Power BI R visuals cannot export dataframes back to model,
# but having this object in the script helps debugging when running locally)
risk_table
