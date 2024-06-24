

-- combine the two logs
CREATE TABLE combined_logs AS
WITH unique_x_request_ids AS (
    SELECT t1.x_request_id
    FROM api_proxy_logs t1
    INNER JOIN project_logs t2 ON t1.x_request_id = t2.x_request_id
    GROUP BY t1.x_request_id
    HAVING COUNT(t2.x_request_id) = 1 -- only those count which can be paired
)
SELECT t1.x_request_id,
		-- because the timestamp is being created at the end of the request, 
		-- it must be corrected with the request_time to point to the start
		to_timestamp(EXTRACT(EPOCH FROM (t1.timestamp::timestamp)) - t1.request_time) as timestamp1,
		to_timestamp(EXTRACT(EPOCH FROM (t2.timestamp::timestamp)) - t2.request_time) as timestamp2,
	   (EXTRACT(EPOCH FROM (t2.timestamp::timestamp)) - t2.request_time) - (EXTRACT(EPOCH FROM (t1.timestamp::timestamp)) - t1.request_time) as timediff
FROM unique_x_request_ids as t3
JOIN api_proxy_logs t1 ON t1.x_request_id = t3.x_request_id
JOIN project_logs t2 ON t2.x_request_id = t3.x_request_id;


CREATE INDEX IF NOT EXISTS idx_combined_logs_timediff ON public.combined_logs (timediff);
