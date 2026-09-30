-- Win rate by competitor, segment and deployment mode
-- SIMULATED DATA: calibrated to phase-1 shares, not observed CRM data.

SELECT
    o.competitor,
    a.tier,
    a.deployment,
    COUNT(*) as total_opps,
    SUM(CASE WHEN o.outcome = 'Won' THEN 1 ELSE 0 END) as wins,
    ROUND(1.0 * SUM(CASE WHEN o.outcome = 'Won' THEN 1 ELSE 0 END) / COUNT(*), 3) as win_rate
FROM sim_opportunities o
JOIN sim_accounts a ON o.account_id = a.account_id
GROUP BY o.competitor, a.tier, a.deployment
ORDER BY o.competitor, win_rate DESC;
