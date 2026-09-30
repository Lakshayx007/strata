-- Delivery velocity per PM team, on-time release %, and KPI progress
-- SIMULATED DATA

SELECT
    pm_team,
    COUNT(*) as total_sprints,
    ROUND(AVG(planned_points), 1) as avg_planned,
    ROUND(AVG(delivered_points), 1) as avg_delivered,
    ROUND(1.0 * AVG(delivered_points) / AVG(planned_points), 3) as delivery_ratio,
    ROUND(1.0 * SUM(CASE WHEN on_time THEN 1 ELSE 0 END) / COUNT(*), 3) as on_time_pct,
    ROUND(AVG(julianday(actual_release_date) - julianday(planned_release_date)), 1) as avg_slip_days
FROM sim_releases
GROUP BY pm_team
ORDER BY delivery_ratio DESC;
