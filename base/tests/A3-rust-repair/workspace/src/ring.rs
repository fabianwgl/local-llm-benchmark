//! A fixed-capacity ring buffer.

/// Keeps the most recent `capacity` values. Once the buffer is full, every push replaces
/// the oldest value.
#[derive(Debug, Clone)]
pub struct RingBuffer<T> {
    items: Vec<T>,
    capacity: usize,
    /// Once the buffer is full: the slot that holds the oldest value, which is the slot
    /// the next push writes to. Zero until then.
    head: usize,
}

impl<T> RingBuffer<T> {
    /// Creates an empty buffer that holds at most `capacity` values.
    ///
    /// # Panics
    ///
    /// Panics if `capacity` is zero.
    pub fn new(capacity: usize) -> Self {
        assert!(capacity > 0, "capacity must be greater than zero");
        RingBuffer { items: Vec::with_capacity(capacity), capacity, head: 0 }
    }

    /// The maximum number of values the buffer holds.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// The number of values currently stored.
    pub fn len(&self) -> usize {
        self.items.len()
    }

    /// Returns `true` if nothing is stored.
    pub fn is_empty(&self) -> bool {
        self.items.is_empty()
    }

    /// Returns `true` if the next push will replace the oldest value.
    pub fn is_full(&self) -> bool {
        self.items.len() == self.capacity
    }

    /// Adds `value` as the newest value. If the buffer is full, the oldest value is
    /// removed to make room and returned.
    pub fn push(&mut self, value: T) -> Option<T> {
        if !self.is_full() {
            self.items.push(value);
            return None;
        }
        let evicted = std::mem::replace(&mut self.items[self.head], value);
        self.head = (self.head + 1) % self.capacity;
        Some(evicted)
    }

    /// Visits the stored values from oldest to newest.
    pub fn iter(&self) -> impl Iterator<Item = &T> + '_ {
        self.items.iter()
    }

    /// Removes every value. The capacity stays the same.
    pub fn clear(&mut self) {
        self.items.clear();
    }
}
