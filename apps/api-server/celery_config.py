"""Worker transport policy; task/repository integration is Phase 1 work."""

import os

broker_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
result_backend = None  # PostgreSQL is authoritative; no portrait bytes/results in Redis.
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
task_ignore_result = True
task_acks_late = True
task_reject_on_worker_lost = True
worker_prefetch_multiplier = 1
worker_concurrency = 1  # One execution slot per GPU worker; tune only after profiling.
task_track_started = False
broker_transport_options = {"visibility_timeout": 60}
task_soft_time_limit = 40
task_time_limit = 45
# Queue payload: opaque job_id + fence only. Do not pass images, paths, tokens or URLs.
# Hard timeout means worker death and cleanup, not CUDA kernel preemption.
# Redelivery requires a DB lease/fence/idempotent settlement; this config alone is insufficient.
