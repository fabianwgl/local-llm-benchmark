//! Summary statistics over latency samples.

/// Collects latency samples, in whole milliseconds, and answers summary queries.
#[derive(Debug, Clone, Default)]
pub struct Stats {
    samples: Vec<u64>,
    sum: u64,
    min: u64,
    max: u64,
}

impl Stats {
    /// Creates a `Stats` without samples.
    pub fn new() -> Self {
        Stats::default()
    }

    /// Adds one sample.
    pub fn record(&mut self, value: u64) {
        if self.samples.is_empty() {
            self.min = value;
            self.max = value;
        } else {
            self.min = self.min.min(value);
            self.max = self.max.max(value);
        }
        self.sum += value;
        self.samples.push(value);
    }

    /// The number of samples.
    pub fn count(&self) -> usize {
        self.samples.len()
    }

    /// The smallest sample, or `None` if there are no samples.
    pub fn min(&self) -> Option<u64> {
        if self.samples.is_empty() {
            None
        } else {
            Some(self.min)
        }
    }

    /// The largest sample, or `None` if there are no samples.
    pub fn max(&self) -> Option<u64> {
        if self.samples.is_empty() {
            None
        } else {
            Some(self.max)
        }
    }

    /// The arithmetic mean of the samples, or `None` if there are no samples.
    pub fn mean(&self) -> Option<f64> {
        if self.samples.is_empty() {
            return None;
        }
        Some((self.sum / self.samples.len() as u64) as f64)
    }

    /// The `p`-th percentile of the samples, using the nearest-rank method.
    ///
    /// With the `n` samples sorted in ascending order, the result is the sample at rank
    /// `ceil(p * n / 100)`, counting from 1: the smallest rank at which at least `p`
    /// percent of the samples are at or below the result. A rank of 0, which only `p = 0`
    /// produces, is raised to 1. So `percentile(0.0)` is the smallest sample and
    /// `percentile(100.0)` the largest. The result is always one of the samples; nothing
    /// is interpolated. Duplicate samples count separately.
    ///
    /// Returns `None` if there are no samples, or if `p` is NaN, below 0 or above 100.
    ///
    /// For the samples 15, 20, 35, 40 and 50, `percentile(30.0)` and `percentile(40.0)`
    /// are both 20 (rank 2) and `percentile(50.0)` is 35 (rank 3). For the samples 1 to
    /// 100, `percentile(p)` is `p` for every whole number `p` from 1 to 100.
    pub fn percentile(&self, p: f64) -> Option<u64> {
        todo!()
    }

    /// Adds every sample of `other` to `self`.
    ///
    /// Afterwards `self` answers every query as if the samples of both had been recorded
    /// into one `Stats`. `other` is not modified. Either side, or both, may be without
    /// samples.
    pub fn merge(&mut self, other: &Stats) {
        todo!()
    }
}
