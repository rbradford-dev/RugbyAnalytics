# RugbyAnalytics — R dependencies
# Run once:  source("r/00_install.R")
pkgs <- c(
  "tidyverse",    # data wrangling + ggplot2
  "PlayerRatings",# Elo, Glicko, Glicko-2
  "rstan",        # Bayesian hierarchical models
  "rstanarm",     # convenient Stan GLMs
  "loo",          # model comparison (WAIC/LOO)
  "Metrics",      # Brier score, log-loss
  "zoo"           # rolling / time-series helpers
)
new <- pkgs[!(pkgs %in% installed.packages()[,"Package"])]
if (length(new)) install.packages(new, repos = "https://cloud.r-project.org")
invisible(lapply(pkgs, require, character.only = TRUE))
cat("R environment ready.\n")
