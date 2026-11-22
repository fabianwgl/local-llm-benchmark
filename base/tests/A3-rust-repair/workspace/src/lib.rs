//! In-memory log analysis: keep the most recent log lines in a fixed-size window, parse
//! them as logfmt, and summarise numeric fields such as request latencies.
//!
//! `README.md` describes the public API in full.

#![forbid(unsafe_code)]

mod parser;
mod ring;
mod stats;
mod window;

pub use parser::{parse_line, ErrorKind, ParseError, Record};
pub use ring::RingBuffer;
pub use stats::Stats;
pub use window::LogWindow;
