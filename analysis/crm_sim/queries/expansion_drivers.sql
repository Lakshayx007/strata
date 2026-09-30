-- Expansion drivers: accounts with expansion, by tier and industry
-- SIMULATED DATA

SELECT
    a.tier,
    a.industry,
    COUNT(*) as accounts,
    SUM(CASE WHEN r.expansion > 0 THEN 1 ELSE 0 END) as expanded,
    ROUND(1.0 * SUM(CASE WHEN r.expansion > 0 THEN 1 ELSE 0 END) / COUNT(*), 3) as expansion_rate,
    ROUND(AVG(CASE WHEN r.expansion > 0 THEN r.expansion ELSE NULL END), 2) as avg_expansion
FROM sim_renewals r
JOIN sim_accounts a ON r.account_id = a.account_id
WHERE r.churn = 0
GROUP BY a.tier, a.industry
ORDER BY expansion_rate DESC;
