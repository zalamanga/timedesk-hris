from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

JAKARTA = ZoneInfo("Asia/Jakarta")


def iso(value):
    return value.isoformat() if value else None


def window(from_date: date, to_date: date):
    if not 2000 <= from_date.year <= 2200 or not 2000 <= to_date.year <= 2200:
        raise ValueError("Tanggal harus berada dalam tahun 2000 sampai 2200")
    if to_date < from_date or (to_date - from_date).days >= 31:
        raise ValueError("Pilih rentang 1 sampai 31 hari")
    start = datetime.combine(from_date, time.min, JAKARTA).astimezone(timezone.utc)
    end = datetime.combine(to_date + timedelta(days=1), time.min, JAKARTA).astimezone(timezone.utc)
    return start, end


def clip_seconds(start, end, low, high):
    return max(0, int((min(end, high) - max(start, low)).total_seconds()))


def hhmm(seconds):
    minutes = seconds // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
