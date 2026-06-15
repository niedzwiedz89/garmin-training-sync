from datetime import datetime, timedelta

now = datetime.now() - timedelta(days=2)
print(now)
print(type(now))