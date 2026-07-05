# Chart timeline

BIST charts compress periods where the exchange is known to be closed. This keeps neighboring
trading candles visually adjacent without altering their timestamps or market values.

## Hidden periods

The range-break builder uses the same maintained BIST calendar as the scanner and freshness logic.
It hides:

- Saturdays and Sundays;
- full-day holidays listed in the calendar data;
- the regular intraday closure from 18:00 until 10:00 Istanbul time;
- the remainder of configured half days after their early data close.

Price and volume axes receive the same Plotly range breaks, so their candles and bars remain
aligned. The underlying OHLCV frame is unchanged: range breaks only change axis presentation.

## Missing data remains visible

An absent candle during a valid trading session is not treated as a closed-market break. The chart
does not infer closures from missing rows, because that could hide a provider or data-quality
failure. Only dates and hours explicitly closed by the session calendar are compressed.

## Other Yahoo symbols

Trading Vision currently has a maintained session calendar only for Borsa Istanbul. Generic Yahoo
symbols therefore keep their original continuous date axis. Applying BIST hours to a US equity,
cryptocurrency, currency pair, or another exchange would be misleading.

The pure range-break implementation is in `trading_vision/ui/range_breaks.py` and is tested for
weekends, full-day holidays, half days, intraday closures, and synchronized subplots.
