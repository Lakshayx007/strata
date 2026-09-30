-- Stage-to-stage conversion and median days in stage (cycle bottlenecks)
-- SIMULATED DATA

SELECT
    stage,
    COUNT(*) as entries,
    ROUND(AVG(julianday(exited_at) - julianday(entered_at)), 1) as avg_days_in_stage,
    COUNT(DISTINCT opp_id) as unique_opps
FROM sim_stage_history
GROUP BY stage
ORDER BY entries DESC;
