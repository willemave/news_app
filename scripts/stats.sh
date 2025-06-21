#!/bin/bash
# Show queue statistics

python -c "
from app.services.queue import get_queue_service
from app.core.db import init_db
import json

init_db()
stats = get_queue_service().get_queue_stats()
print('Queue Statistics:')
print(json.dumps(stats, indent=2))
"