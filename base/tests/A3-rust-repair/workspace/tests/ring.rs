use ringlog::RingBuffer;

#[test]
fn fills_up_to_its_capacity() {
    let mut ring = RingBuffer::new(3);
    assert!(ring.is_empty());
    assert_eq!(ring.capacity(), 3);

    assert_eq!(ring.push(1), None);
    assert_eq!(ring.push(2), None);
    assert_eq!(ring.len(), 2);
    assert!(!ring.is_full());

    assert_eq!(ring.push(3), None);
    assert_eq!(ring.len(), 3);
    assert!(ring.is_full());
}

#[test]
fn push_returns_the_value_it_replaces() {
    let mut ring = RingBuffer::new(2);
    ring.push("a");
    ring.push("b");
    assert_eq!(ring.push("c"), Some("a"));
    assert_eq!(ring.push("d"), Some("b"));
    assert_eq!(ring.len(), 2);
}

#[test]
fn iterates_in_push_order() {
    let mut ring = RingBuffer::new(4);
    for n in [10, 20, 30] {
        ring.push(n);
    }
    assert_eq!(ring.iter().copied().collect::<Vec<_>>(), [10, 20, 30]);
}

#[test]
fn iterates_oldest_to_newest_after_wrapping() {
    let mut ring = RingBuffer::new(3);
    for n in 1..=5 {
        ring.push(n);
    }
    assert_eq!(ring.iter().copied().collect::<Vec<_>>(), [3, 4, 5]);
}

#[test]
fn clear_removes_everything() {
    let mut ring = RingBuffer::new(2);
    ring.push('x');
    ring.push('y');
    ring.clear();
    assert!(ring.is_empty());
    assert_eq!(ring.capacity(), 2);
    assert_eq!(ring.iter().count(), 0);
}
