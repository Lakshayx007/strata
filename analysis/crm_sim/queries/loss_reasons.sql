-- Loss-reason mix by competitor
-- SIMULATED DATA: loss reasons calibrated to phase-1 stated-reason shares
-- (cost 20/63, operational simplicity 11/63, etc.)

SELECT
    competitor,
    loss_reason,
    COUNT(*) as count,
    ROUND(1.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY competitor), 3) as share
FROM sim_opportunities
WHERE outcome = 'Lost' AND loss_reason IS NOT NULL
GROUP BY competitor, loss_reason
ORDER BY competitor, count DESC;
