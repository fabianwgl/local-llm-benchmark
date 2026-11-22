//! A window over the most recent log lines of a service.

use crate::parser::{parse_line, Record};
use crate::ring::RingBuffer;
use crate::stats::Stats;

/// The most recent log lines of a service, kept as text and parsed on demand.
#[derive(Debug, Clone)]
pub struct LogWindow {
    lines: RingBuffer<String>,
}

impl LogWindow {
    /// Creates an empty window that keeps at most `capacity` lines.
    ///
    /// # Panics
    ///
    /// Panics if `capacity` is zero.
    pub fn new(capacity: usize) -> Self {
        LogWindow { lines: RingBuffer::new(capacity) }
    }

    /// Adds a line as the newest one. If the window is full, the oldest line is dropped.
    pub fn push(&mut self, line: &str) {
        self.lines.push(line.to_string());
    }

    /// The maximum number of lines the window keeps.
    pub fn capacity(&self) -> usize {
        self.lines.capacity()
    }

    /// The number of lines in the window.
    pub fn len(&self) -> usize {
        self.lines.len()
    }

    /// Returns `true` if the window holds no lines.
    pub fn is_empty(&self) -> bool {
        self.lines.is_empty()
    }

    /// The lines in the window, from oldest to newest.
    pub fn lines(&self) -> impl Iterator<Item = &str> + '_ {
        self.lines.iter().map(String::as_str)
    }

    /// Parses the lines in the window from oldest to newest. Lines that are not valid
    /// logfmt are skipped.
    pub fn records(&self) -> impl Iterator<Item = Record<'_>> + '_ {
        self.lines().filter_map(|line| parse_line(line).ok())
    }

    /// Counts the records whose field `key` has the value `value`.
    pub fn count(&self, key: &str, value: &str) -> usize {
        self.records().filter(|record| record.get(key) == Some(value)).count()
    }

    /// Collects the numeric field `key` (for example `duration_ms`) of every record in
    /// the window. Records that lack the field, or whose value is not an unsigned whole
    /// number, are skipped.
    pub fn latency(&self, key: &str) -> Stats {
        let mut stats = Stats::new();
        for record in self.records() {
            if let Some(value) = record.get(key).and_then(|v| v.parse().ok()) {
                stats.record(value);
            }
        }
        stats
    }

    /// Removes every line. The capacity stays the same.
    pub fn clear(&mut self) {
        self.lines.clear();
    }
}
