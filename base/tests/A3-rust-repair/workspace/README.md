# ringlog

In-memory log analysis for services that write [logfmt](https://brandur.org/logfmt) lines:
keep the most recent lines in a fixed-size window, parse them, and summarise numeric fields
such as request latencies.

The crate uses only the standard library and contains no `unsafe` code.

```rust
use ringlog::LogWindow;

let mut window = LogWindow::new(1000);
window.push(r#"ts=2026-03-14T09:26:53Z level=warn msg="disk \"sda\" at 91%" duration_ms=31"#);
window.push("ts=2026-03-14T09:26:54Z level=info path=/users duration_ms=12\n");

let latency = window.latency("duration_ms");
println!("p99 = {:?} ms over {} requests", latency.percentile(99.0), latency.count());
println!("{} warnings", window.count("level", "warn"));
```

Build and test with `cargo build --offline` and `cargo test --offline`.

## Public API

Everything below is exported from the crate root. This section is the contract; the
internal representation of every type is private and may change.

### `parse_line(line: &str) -> Result<Record<'_>, ParseError>`

Parses one log line. The line must not contain its line ending (see `LogWindow::push`).

**Fields.** A line is a sequence of fields separated by one or more spaces (U+0020 only).
Spaces before the first and after the last field are ignored. An empty line, or one made
only of spaces, is a record with no fields.

A field is `key=value`:

- The **key** is the text from the start of the field up to the first `=`. It cannot be
  empty and cannot contain a space.
- If the byte after the `=` is not `"`, the value is **unquoted**: it is the text up to the
  next space or the end of the line, taken as it is. It may be empty (`key=`) and may contain
  `=` and `"` (`url=/a?b=c` has the value `/a?b=c`).
- If the byte after the `=` is `"`, the value is **quoted**: it is the text up to the
  matching closing `"`, with the escape sequences below decoded. It may be empty (`key=""`)
  and may contain spaces and `=`. The closing quote must be followed by a space or by the
  end of the line.

**Escape sequences** inside quoted values. A backslash and the character after it are
always read together, so `\"` never closes the value.

| Sequence | Decodes to |
|---|---|
| `\"` | `"` |
| `\\` | `\` |
| `\n` | line feed (U+000A) |
| `\r` | carriage return (U+000D) |
| `\t` | tab (U+0009) |

Any other character after a backslash is an error. Unquoted values have no escape
sequences: a backslash in an unquoted value is an ordinary character.

**Errors.** `ParseError` has two public fields: `kind: ErrorKind` and `offset: usize`, the
byte offset (counting from 0, in bytes, not characters) in the line where the problem was
found. Fields are read from left to right and the first field with a problem decides the
error.

| `ErrorKind` | When | `offset` |
|---|---|---|
| `MissingEquals` | a field reaches a space or the end of the line before any `=` | first byte of the field |
| `EmptyKey` | a field starts with `=` | that `=` |
| `UnterminatedQuote` | a quoted value has no closing quote before the end of the line, including when the line ends right after a backslash | the opening quote |
| `InvalidEscape` | a backslash in a quoted value is followed by a character not listed above | the backslash |
| `TrailingCharacters` | a closing quote is followed by something other than a space | the byte after the closing quote |

Within one quoted value the checks run in this order: `UnterminatedQuote`, then
`InvalidEscape`, then `TrailingCharacters`. `ParseError` implements `Display`,
`std::error::Error`, `Debug`, `Clone`, `Copy`, `PartialEq` and `Eq`; so does `ErrorKind`
(except the two error traits).

Example: `parse_line(r#"a=1 msg="x\qy""#)` fails with `InvalidEscape` at offset 10.

### `Record<'a>`

The fields of one parsed line. A record may borrow from the line it was parsed from, so it
cannot outlive it. Strings returned by its methods borrow from the record.

- `get(&self, key: &str) -> Option<&str>`: the decoded value of the field named `key`, or
  `None`. **If the key appears more than once, the last occurrence wins**:
  `parse_line("a=1 a=2")` gives `get("a") == Some("2")`.
- `len(&self) -> usize`: the number of fields, counting every occurrence of a repeated key.
- `is_empty(&self) -> bool`: `true` if the line had no fields.
- `iter(&self) -> impl Iterator<Item = (&str, &str)>`: every `(key, decoded value)` pair in
  the order they appear in the line, repeated keys included.

`Record` implements `Debug` and `Clone`.

### `RingBuffer<T>`

A fixed-capacity buffer that keeps the most recent values.

- `new(capacity: usize) -> RingBuffer<T>`: an empty buffer. Panics if `capacity` is 0. A
  capacity of 1 is valid.
- `capacity(&self) -> usize`, `len(&self) -> usize`, `is_empty(&self) -> bool`.
- `is_full(&self) -> bool`: `true` when `len() == capacity()`.
- `push(&mut self, value: T) -> Option<T>`: adds `value` as the newest value. While the
  buffer is not full, returns `None`. When it is full, removes the oldest value and returns
  it, so `len()` never exceeds `capacity()`. This holds however many times the buffer has
  wrapped around.
- `iter(&self) -> impl Iterator<Item = &T>`: the stored values from **oldest to newest**,
  exactly `len()` of them. After any sequence of pushes, these are the last `len()` values
  pushed, in the order they were pushed.
- `clear(&mut self)`: removes every value. Afterwards the buffer behaves exactly like a new
  buffer of the same capacity.

`RingBuffer<T>` implements `Debug` and `Clone` when `T` does.

### `Stats`

An accumulator of latency samples in whole milliseconds (`u64`). `Stats` implements
`Debug`, `Clone` and `Default` (the same as `Stats::new()`).

- `new() -> Stats`: no samples.
- `record(&mut self, value: u64)`: adds one sample.
- `count(&self) -> usize`: the number of samples.
- `min(&self) -> Option<u64>`, `max(&self) -> Option<u64>`: the smallest and largest
  sample; `None` without samples.
- `mean(&self) -> Option<f64>`: the sum of the samples divided by their count, not rounded
  (the mean of 1 and 2 is 1.5); `None` without samples.
- `percentile(&self, p: f64) -> Option<u64>`: the nearest-rank percentile. Sort the `n`
  samples in ascending order (duplicates count separately); the result is the sample at
  rank `ceil(p * n / 100)`, counting from 1, where a rank of 0 (only `p = 0` gives one) is
  raised to 1. The rank is computed exactly, without floating-point rounding error.
  - `percentile(0.0)` is the smallest sample and `percentile(100.0)` the largest.
  - With a single sample, every valid `p` gives that sample.
  - The result is always one of the samples; nothing is interpolated.
  - Returns `None` if there are no samples, or if `p` is NaN, below 0 or above 100.
  - Examples: for 15, 20, 35, 40, 50: `percentile(30.0)` and `percentile(40.0)` are 20,
    `percentile(50.0)` is 35. For the samples 1 to 100, `percentile(p)` is `p` for every
    whole number `p` from 1 to 100.
- `merge(&mut self, other: &Stats)`: adds every sample of `other`. Afterwards `self`
  answers every query (`count`, `min`, `max`, `mean`, `percentile`) exactly as if all
  samples of both had been recorded into one `Stats`. `other` is unchanged. Either side,
  or both, may be without samples; merging an empty `Stats` changes nothing, and merging
  into an empty `Stats` makes it equivalent to `other`.

### `LogWindow`

The most recent lines of a service, stored as text and parsed on demand.

- `new(capacity: usize) -> LogWindow`: an empty window that keeps at most `capacity` lines.
  Panics if `capacity` is 0.
- `push(&mut self, line: &str)`: stores `line` as the newest line, dropping the oldest one
  if the window is full. `line` may include its line ending: one trailing `"\n"` or
  `"\r\n"` is removed before the line is stored. Nothing else is trimmed.
- `capacity(&self) -> usize`, `len(&self) -> usize`, `is_empty(&self) -> bool`.
- `lines(&self) -> impl Iterator<Item = &str>`: the stored lines, oldest to newest.
- `records(&self) -> impl Iterator<Item = Record<'_>>`: the stored lines parsed with
  `parse_line`, oldest to newest. Lines that fail to parse are skipped.
- `count(&self, key: &str, value: &str) -> usize`: the number of records for which
  `get(key) == Some(value)`.
- `latency(&self, key: &str) -> Stats`: a `Stats` with one sample per record whose
  `get(key)` value parses as a `u64` (`str::parse::<u64>`). Records without the field, or
  with a value that does not parse, are skipped.
- `clear(&mut self)`: removes every line; the capacity stays the same.

`LogWindow` implements `Debug` and `Clone`.
