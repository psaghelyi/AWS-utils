

with requestids as (
	select x_request_id, timediff
	from combined_logs
	--where timediff > 10
)
select t3.x_request_id, t1.timestamp as timestamp1, t2.timestamp as timestamp2,
	t2.request,
	t3.timediff, t1.request_time as proxy_time, t2.request_time as projects_time,
	t1.upstream_connect_time, t1.upstream_header_time, t1.upstream_response_time
from requestids as t3
join api_proxy_logs as t1 on t1.x_request_id = t3.x_request_id
join project_logs as t2 on t2.x_request_id = t3.x_request_id
where t1.request_time < t2.request_time
limit 100;


with requestids as (
	select x_request_id, timediff
	from combined_logs
	--where timediff < -10
)
select t3.x_request_id, t1.timestamp as timestamp1, t2.timestamp as timestamp2,
	t3.timediff, t1.upstream_response_time - t2.request_time as delay, t1.request_time, t2.request_time,
	t1.upstream_connect_time, t1.upstream_header_time, t1.upstream_response_time,
	t2.upstream_connect_time, t2.upstream_header_time, t2.upstream_response_time,
	t1.body_bytes_sent, t2.request
from requestids as t3
join api_proxy_logs as t1 on t1.x_request_id = t3.x_request_id
join project_logs as t2 on t2.x_request_id = t3.x_request_id
--where t1.upstream_response_time - t2.request_time > 10
-- where (t1.upstream_response_time - t2.request_time) - t3.timediff > 4
order by t1.body_bytes_sent DESC
limit 1000;