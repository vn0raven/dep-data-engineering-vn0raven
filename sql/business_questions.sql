-- ============================================================
-- M3 — Business Questions
-- Davao Commute Router
-- ============================================================


-- ------------------------------------------------------------
-- QUESTION 1
-- Which transit routes have the most explicitly mapped stops,
-- and which routes currently have no explicit stop mapping?
-- ------------------------------------------------------------

SELECT
    r.route_id,
    r.route_ref,
    r.route_name,
    r.route_mode,
    r.operator,
    COUNT(rs.stop_sequence) AS mapped_stop_occurrences
FROM routes AS r
LEFT JOIN route_stops AS rs
    ON r.route_id = rs.route_id
GROUP BY
    r.route_id,
    r.route_ref,
    r.route_name,
    r.route_mode,
    r.operator
ORDER BY
    mapped_stop_occurrences DESC,
    r.route_id;


-- ------------------------------------------------------------
-- QUESTION 2
-- Which stops are shared by multiple routes and may therefore
-- represent possible transfer locations?
-- ------------------------------------------------------------

SELECT
    s.stop_id,
    s.name,
    s.stop_type,
    s.latitude,
    s.longitude,
    COUNT(DISTINCT rs.route_id) AS route_count
FROM stops AS s
JOIN route_stops AS rs
    ON s.stop_id = rs.stop_id
GROUP BY
    s.stop_id,
    s.name,
    s.stop_type,
    s.latitude,
    s.longitude
HAVING
    COUNT(DISTINCT rs.route_id) >= 2
ORDER BY
    route_count DESC,
    s.stop_id;


-- ------------------------------------------------------------
-- QUESTION 3
-- What direct stop-to-stop connections can currently be derived
-- from the ordered route-stop data?
-- ------------------------------------------------------------

WITH ordered_stops AS (
    SELECT
        route_id,
        stop_sequence,
        stop_id AS from_stop_id,

        LEAD(stop_id) OVER (
            PARTITION BY route_id
            ORDER BY stop_sequence
        ) AS to_stop_id

    FROM route_stops
)

SELECT
    o.route_id,
    r.route_ref,
    r.route_name,
    o.stop_sequence AS from_sequence,

    o.from_stop_id,
    from_stop.name AS from_stop_name,

    o.to_stop_id,
    to_stop.name AS to_stop_name

FROM ordered_stops AS o

JOIN routes AS r
    ON o.route_id = r.route_id

LEFT JOIN stops AS from_stop
    ON o.from_stop_id = from_stop.stop_id

LEFT JOIN stops AS to_stop
    ON o.to_stop_id = to_stop.stop_id

WHERE
    o.to_stop_id IS NOT NULL

ORDER BY
    o.route_id,
    o.stop_sequence;