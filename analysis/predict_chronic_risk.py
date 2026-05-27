"""
Feature 10.3: Predictive Chronic Risk Scoring
==============================================
Uses the 10-year HRRP panel as a labeled training set to identify hospitals
headed toward chronic penalty status while the intervention window is still open.

Training labels:
  - Chronic (penalized all 10 years, n~1,368) = positive class
  - Escaper (penalized early, escaped recently, n~200) = negative class

Live scoring population:
  - Intermittent (penalized 5-9 years, n~672) = which ones are sliding toward chronic?

Prerequisites:
  - google-cloud-bigquery installed
  - BigQuery auth configured (gcloud auth application-default login)
  - scikit-learn, pandas, numpy installed

Usage:
  python predict_chronic_risk.py

Output:
  analysis/chronic_risk_scores.csv - all intermittent hospitals ranked by risk
  analysis/at_risk_hospitals.csv - top hospitals likely to become chronic

Author: Jay Callery | github.com/jcal-2/CMS-HRRP-Analysis
"""

import pandas as pd
import numpy as np
from google.cloud import bigquery
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, roc_auc_score
import warnings
import os

warnings.filterwarnings('ignore')

# ===========================================================================
# CONFIG - adapt these to your BigQuery schema
# ===========================================================================
PROJECT_ID = "data-viz-sandbox-495114"

# dbt target schema. Per the dbt profile in cms_penalty_analysis/profiles.yml,
# dbt materializes models into the same schema as the raw sources
# (cms_raw_historical), so all fct_/stg_ models live alongside raw_hrrp_*.
DBT_DATASET = "cms_raw_historical"

# Raw historical dataset (FY-specific HRRP tables: raw_hrrp_fy2016 ... fy2025)
RAW_DATASET = "cms_raw_historical"

# HCRIS financials dataset
COSTREPORTS_DATASET = "cms_raw_costreports"

# Output directory
OUTPUT_DIR = "analysis"

client = bigquery.Client(project=PROJECT_ID)


# ===========================================================================
# STEP 1: Query the 10-year panel from BigQuery
# ===========================================================================
def query_penalty_panel():
    """
    Pull year-by-year penalty data for all hospitals across FY2016-FY2025.

    Uses the dbt staging view stg_hrrp_penalties, which already unions the
    10 raw_hrrp_fy* tables and applies the FY2016/2017 zero-sentinel fix to
    the ERR columns. Aliased to the column names this script's downstream
    feature logic expects (penalty_pct, err_pn, err_tka).
    """
    sql = f"""
    SELECT
        facility_id,
        fiscal_year,
        penalty_percentage AS penalty_pct,
        err_ami,
        err_hf,
        err_pneumonia AS err_pn,
        err_copd,
        err_hip_knee  AS err_tka,
        err_cabg
    FROM `{PROJECT_ID}.{DBT_DATASET}.stg_hrrp_penalties`
    WHERE fiscal_year BETWEEN 2016 AND 2025
    ORDER BY facility_id, fiscal_year
    """

    print("Querying 10-year penalty panel from BigQuery...")
    df = client.query(sql).to_dataframe()
    print(f"  Retrieved {len(df)} rows ({df['facility_id'].nunique()} hospitals)")
    return df


def query_hospital_characteristics():
    """
    Pull current hospital characteristics (star rating, ownership, region, etc).
    Adapt to match your dbt dimension table.
    """
    # vbp_tps lives in stg_vbp_tps (single FY2026 snapshot, 2,455 hospitals);
    # avg_hac_score is the analogue of the script's "hac_score" feature.
    sql = f"""
    SELECT
        h.facility_id,
        h.facility_name,
        h.city,
        h.state,
        h.census_region,
        h.ownership_category,
        h.star_rating,
        h.mspb_ratio,
        h.avg_hac_score              AS hac_score,
        v.total_performance_score    AS vbp_tps
    FROM `{PROJECT_ID}.{DBT_DATASET}.fct_hospital_current_performance` h
    LEFT JOIN `{PROJECT_ID}.{DBT_DATASET}.stg_vbp_tps` v USING (facility_id)
    """

    print("Querying hospital characteristics...")
    df = client.query(sql).to_dataframe()
    print(f"  Retrieved {len(df)} hospitals")
    return df


def query_financials():
    """
    Pull hospital financials from the HCRIS mart table.
    """
    sql = f"""
    SELECT
        facility_id,
        bed_count,
        operating_margin,
        net_patient_revenue,
        total_operating_expenses AS total_expenses,
        fte_employees,
        total_discharges
    FROM `{PROJECT_ID}.{DBT_DATASET}.fct_hospital_financials`
    """
    
    print("Querying hospital financials...")
    df = client.query(sql).to_dataframe()
    print(f"  Retrieved {len(df)} hospitals")
    return df


# ===========================================================================
# STEP 2: Compute trajectory features
# ===========================================================================
def compute_trajectory_features(panel_df):
    """
    For each hospital, compute features that capture the trajectory of
    penalty severity and readmission performance over the first N years.
    
    Key insight from research: the escape window closes by year 3-4.
    So we compute features at the year-3 mark.
    
    NOTE: FY2016-2017 ERR values contain zero-coded sentinels for conditions
    not scored. These are excluded. FY2018 is the reliable baseline.
    """
    
    err_cols = ['err_ami', 'err_hf', 'err_pn', 'err_copd', 'err_tka', 'err_cabg']
    
    features = []
    
    for fid, group in panel_df.groupby('facility_id'):
        group = group.sort_values('fiscal_year')
        
        # --- Cohort label ---
        years_penalized = (group['penalty_pct'] > 0).sum()
        
        if years_penalized == 10:
            cohort = 'chronic'
        elif years_penalized == 0:
            cohort = 'never'
        else:
            # Check if escaper: penalized early, not penalized in last 2 years
            last_2 = group[group['fiscal_year'] >= 2024]
            early = group[group['fiscal_year'] <= 2019]
            if len(last_2) > 0 and (last_2['penalty_pct'] == 0).all() and (early['penalty_pct'] > 0).any():
                cohort = 'escaper'
            else:
                cohort = 'intermittent'
        
        # --- Penalty trajectory (years 1-3, using FY2018-2020 as baseline) ---
        early_years = group[group['fiscal_year'].between(2018, 2020)]
        
        if len(early_years) < 2:
            penalty_slope = 0
            penalty_year1 = 0
            penalty_year3 = 0
        else:
            penalties = early_years['penalty_pct'].values
            penalty_year1 = penalties[0] if len(penalties) > 0 else 0
            penalty_year3 = penalties[-1] if len(penalties) > 0 else 0
            # Linear slope over first 3 years
            x = np.arange(len(penalties))
            if len(penalties) >= 2:
                penalty_slope = np.polyfit(x, penalties, 1)[0]
            else:
                penalty_slope = 0
        
        # --- ERR trajectory (FY2018+, excluding zero-coded FY2016-2017) ---
        post_recal = group[group['fiscal_year'] >= 2018]
        
        # Average ERR across scored conditions per year (exclude zeros)
        err_by_year = []
        conditions_scored_by_year = []
        for _, row in post_recal.iterrows():
            errs = [row[c] for c in err_cols if pd.notna(row[c]) and row[c] > 0]
            if errs:
                err_by_year.append(np.mean(errs))
                conditions_scored_by_year.append(len(errs))
            else:
                err_by_year.append(np.nan)
                conditions_scored_by_year.append(0)
        
        err_by_year = np.array(err_by_year)
        valid_err = err_by_year[~np.isnan(err_by_year)]
        
        if len(valid_err) >= 2:
            err_slope = np.polyfit(np.arange(len(valid_err)), valid_err, 1)[0]
        else:
            err_slope = 0
        
        err_year1 = valid_err[0] if len(valid_err) > 0 else 1.0
        err_latest = valid_err[-1] if len(valid_err) > 0 else 1.0
        err_mean = np.mean(valid_err) if len(valid_err) > 0 else 1.0
        
        # --- Measures above expected at year 3 ---
        if len(post_recal) >= 3:
            yr3_row = post_recal.iloc[2]  # FY2020 (3rd year post-recalibration)
            measures_above = sum(1 for c in err_cols 
                               if pd.notna(yr3_row[c]) and yr3_row[c] > 1.0)
            conditions_scored_yr3 = sum(1 for c in err_cols 
                                       if pd.notna(yr3_row[c]) and yr3_row[c] > 0)
        else:
            measures_above = 0
            conditions_scored_yr3 = 0
        
        # --- Condition coverage (key escaper paradox variable) ---
        avg_conditions_scored = np.mean(conditions_scored_by_year) if conditions_scored_by_year else 0
        
        # --- Penalty persistence in first 3 years ---
        first_3 = group[group['fiscal_year'].between(2016, 2018)]
        penalty_persistence_3yr = (first_3['penalty_pct'] > 0).sum() / max(len(first_3), 1)
        
        features.append({
            'facility_id': fid,
            'cohort': cohort,
            'years_penalized': years_penalized,
            # Penalty trajectory
            'penalty_year1': penalty_year1,
            'penalty_year3': penalty_year3,
            'penalty_slope': penalty_slope,
            'penalty_persistence_3yr': penalty_persistence_3yr,
            # ERR trajectory
            'err_year1': err_year1,
            'err_latest': err_latest,
            'err_slope': err_slope,
            'err_mean': err_mean,
            # Condition coverage
            'measures_above_yr3': measures_above,
            'conditions_scored_yr3': conditions_scored_yr3,
            'avg_conditions_scored': avg_conditions_scored,
        })
    
    return pd.DataFrame(features)


# ===========================================================================
# STEP 3: Build feature matrix and train model
# ===========================================================================
def build_model(trajectory_df, characteristics_df, financials_df):
    """
    Merge all feature sources, train a gradient boosting classifier,
    and score the intermittent cohort.
    """
    
    # Merge datasets
    df = trajectory_df.merge(characteristics_df, on='facility_id', how='left')
    df = df.merge(financials_df, on='facility_id', how='left')
    
    # Derived features (from escape mechanism probe)
    df['revenue_per_bed'] = df['net_patient_revenue'] / df['bed_count'].clip(lower=1)
    df['fte_per_bed'] = df['fte_employees'] / df['bed_count'].clip(lower=1)
    df['discharges_per_bed'] = df['total_discharges'] / df['bed_count'].clip(lower=1)
    
    print(f"\nCohort distribution:")
    print(df['cohort'].value_counts().to_string())
    
    # --- Training set: chronic vs escaper ---
    train_mask = df['cohort'].isin(['chronic', 'escaper'])
    train_df = df[train_mask].copy()
    
    # --- Scoring set: intermittent ---
    score_mask = df['cohort'] == 'intermittent'
    score_df = df[score_mask].copy()
    
    print(f"\nTraining set: {len(train_df)} (chronic: {(train_df['cohort']=='chronic').sum()}, "
          f"escaper: {(train_df['cohort']=='escaper').sum()})")
    print(f"Scoring set:  {len(score_df)} intermittent hospitals")
    
    # --- Feature columns ---
    numeric_features = [
        'penalty_year1', 'penalty_year3', 'penalty_slope', 'penalty_persistence_3yr',
        'err_year1', 'err_latest', 'err_slope', 'err_mean',
        'measures_above_yr3', 'conditions_scored_yr3', 'avg_conditions_scored',
        'star_rating', 'mspb_ratio', 'hac_score', 'vbp_tps',
        'bed_count', 'operating_margin', 'net_patient_revenue', 'fte_employees',
        'revenue_per_bed', 'fte_per_bed', 'discharges_per_bed'
    ]
    
    categorical_features = ['census_region', 'ownership_category']
    
    # Encode categoricals
    encoders = {}
    for cat in categorical_features:
        le = LabelEncoder()
        df[f'{cat}_enc'] = le.fit_transform(df[cat].fillna('Unknown'))
        encoders[cat] = le
    
    all_features = numeric_features + [f'{c}_enc' for c in categorical_features]
    
    # Fill NaN
    for col in all_features:
        df[col] = df[col].fillna(0)
    
    # Rebuild train/score after encoding
    train_df = df[train_mask]
    score_df = df[score_mask]
    
    X_train = train_df[all_features].values
    y_train = (train_df['cohort'] == 'chronic').astype(int).values
    
    X_score = score_df[all_features].values
    
    # --- Train model ---
    clf = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        min_samples_leaf=15,
        subsample=0.8,
        random_state=42
    )
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    acc_scores = cross_val_score(clf, X_train, y_train, cv=cv, scoring='accuracy')
    auc_scores = cross_val_score(clf, X_train, y_train, cv=cv, scoring='roc_auc')
    
    print(f"\n{'='*60}")
    print(f"MODEL PERFORMANCE (5-fold CV)")
    print(f"{'='*60}")
    print(f"  Accuracy: {acc_scores.mean():.3f} (+/- {acc_scores.std():.3f})")
    print(f"  AUC:      {auc_scores.mean():.3f} (+/- {auc_scores.std():.3f})")
    
    # Train on full training set
    clf.fit(X_train, y_train)
    
    # Feature importance
    importances = clf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    
    print(f"\nFeature importance (top predictors of chronic status):")
    for i in sorted_idx[:15]:
        bar = '#' * int(importances[i] * 80)
        print(f"  {all_features[i]:<28} {importances[i]:.3f}  {bar}")
    
    # --- Score intermittent hospitals ---
    chronic_probs = clf.predict_proba(X_score)[:, 1]
    
    return clf, score_df, chronic_probs, all_features


# ===========================================================================
# STEP 4: Export results
# ===========================================================================
def export_results(score_df, chronic_probs):
    """
    Export ranked intermittent hospitals with chronic risk scores.
    """
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    results = score_df.copy()
    results['chronic_risk_score'] = chronic_probs
    
    # Risk tiers
    def risk_tier(prob):
        if prob >= 0.80: return 'Critical'
        elif prob >= 0.65: return 'High'
        elif prob >= 0.50: return 'Moderate'
        elif prob >= 0.35: return 'Watch'
        else: return 'Low'
    
    results['risk_tier'] = results['chronic_risk_score'].apply(risk_tier)
    
    # Sort by risk score
    results = results.sort_values('chronic_risk_score', ascending=False)
    
    # Full scored list
    export_cols = [
        'facility_id', 'facility_name', 'city', 'state', 'census_region',
        'ownership_category', 'star_rating', 'years_penalized',
        'chronic_risk_score', 'risk_tier',
        'penalty_year1', 'penalty_slope', 'err_year1', 'err_slope', 'err_mean',
        'conditions_scored_yr3', 'avg_conditions_scored',
        'bed_count', 'operating_margin', 'net_patient_revenue'
    ]
    
    available_cols = [c for c in export_cols if c in results.columns]
    
    full_path = os.path.join(OUTPUT_DIR, 'chronic_risk_scores.csv')
    results[available_cols].to_csv(full_path, index=False)
    print(f"\nExported full scored list: {full_path} ({len(results)} hospitals)")
    
    # At-risk subset (Critical + High + Moderate)
    at_risk = results[results['risk_tier'].isin(['Critical', 'High', 'Moderate'])]
    at_risk_path = os.path.join(OUTPUT_DIR, 'at_risk_hospitals.csv')
    at_risk[available_cols].to_csv(at_risk_path, index=False)
    print(f"Exported at-risk hospitals: {at_risk_path} ({len(at_risk)} hospitals)")
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"CHRONIC RISK SCORING RESULTS")
    print(f"{'='*70}")
    
    tier_counts = results['risk_tier'].value_counts()
    for tier in ['Critical', 'High', 'Moderate', 'Watch', 'Low']:
        count = tier_counts.get(tier, 0)
        pct = count / len(results) * 100
        print(f"  {tier:<12} {count:>4} hospitals ({pct:.0f}%)")
    
    print(f"\nTOP 30 AT-RISK HOSPITALS:")
    print(f"{'#':<3} {'Hospital':<40} {'City':<18} {'ST':<4} {'Risk':<6} "
          f"{'Tier':<10} {'Yrs':<4} {'ERR Slope':<10}")
    
    for i, (_, r) in enumerate(results.head(30).iterrows(), 1):
        name = str(r.get('facility_name', 'Unknown'))[:39]
        city = str(r.get('city', ''))[:17]
        state = str(r.get('state', ''))
        risk = r['chronic_risk_score']
        tier = r['risk_tier']
        yrs = r.get('years_penalized', '')
        slope = r.get('err_slope', 0)
        print(f"{i:<3} {name:<40} {city:<18} {state:<4} {risk:.3f} "
              f"{tier:<10} {yrs:<4} {slope:>+.4f}")
    
    return results


# ===========================================================================
# MAIN
# ===========================================================================
if __name__ == '__main__':
    print("Feature 10.3: Predictive Chronic Risk Scoring")
    print("=" * 60)
    print()
    
    # Step 1: Query data
    panel_df = query_penalty_panel()
    char_df = query_hospital_characteristics()
    fin_df = query_financials()
    
    # Step 2: Compute trajectory features
    trajectory_df = compute_trajectory_features(panel_df)
    
    # Step 3: Train model and score
    clf, score_df, chronic_probs, feature_names = build_model(
        trajectory_df, char_df, fin_df
    )
    
    # Step 4: Export results
    results = export_results(score_df, chronic_probs)
    
    print(f"\nDone. Files exported to {OUTPUT_DIR}/")
    print(f"  chronic_risk_scores.csv  - all {len(results)} intermittent hospitals ranked")
    print(f"  at_risk_hospitals.csv    - hospitals in Critical/High/Moderate tiers")
