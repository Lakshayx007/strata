-- Regional adoption patterns by service
-- SIMULATED DATA

SELECT
    a.region,
    u.service,
    COUNT(DISTINCT u.account_id) as accounts,
    ROUND(AVG(u.consumption_units), 1) as avg_monthly_units,
    ROUND(AVG(u.active_users), 1) as avg_active_users
FROM sim_usage_monthly u
JOIN sim_accounts a ON u.account_id = a.account_id
GROUP BY a.region, u.service
ORDER BY a.region, avg_monthly_units DESC;
