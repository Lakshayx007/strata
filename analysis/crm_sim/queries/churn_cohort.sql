-- Churn and contraction by usage-decile cohort
-- SIMULATED DATA

SELECT
    usage_decile,
    accounts,
    churned,
    ROUND(1.0 * churned / accounts, 3) as churn_rate,
    ROUND(avg_contraction, 2) as avg_contraction
FROM (
    SELECT
        NTILE(10) OVER (ORDER BY total_usage) as usage_decile,
        COUNT(*) as accounts,
        SUM(churn) as churned,
        AVG(contraction) as avg_contraction
    FROM (
        SELECT
            u.account_id,
            SUM(u.consumption_units) as total_usage,
            r.churn,
            r.contraction
        FROM sim_usage_monthly u
        JOIN sim_renewals r ON u.account_id = r.account_id
        GROUP BY u.account_id
    )
    GROUP BY usage_decile
)
ORDER BY usage_decile;
