# BIST candle completion

Pattern detection uses closed candles by default. Trading Vision therefore decides completion from
the BIST session calendar and configured provider delay rather than from a candle's age alone.

## Daily candles

A daily candle becomes complete after the session's final close plus provider delay. Before that
moment, the current trading date remains forming. Weekends and holidays continue to use the latest
completed trading session, and configured half days use their early close.

## Intraday candles

For `5m`, `15m`, and `1h`, only bars whose full interval boundary has passed plus provider delay are
complete. Before the first eligible boundary of a new session, the previous session's last bar is
the newest completed candle.

## UI and detector behavior

A forming candle remains on the chart because it is useful live price context. The chart heading
adds `forming candle`, while every detector filters it out through the shared `is_complete` flag.
Once the boundary becomes eligible, the next load updates the flag and the bar may participate in
pattern evaluation.

The same pure function is used by normal chart fetches, cached BIST fallback frames, and the
background scanner. This prevents the UI and scanner from disagreeing about whether a signal was
knowable.

Generic Yahoo symbols retain provider-time completion because Trading Vision does not yet maintain
their exchange calendars.
