use ringlog::Stats;

fn stats_of(samples: &[u64]) -> Stats {
    let mut stats = Stats::new();
    for &sample in samples {
        stats.record(sample);
    }
    stats
}

#[test]
fn starts_without_samples() {
    let stats = Stats::new();
    assert_eq!(stats.count(), 0);
    assert_eq!(stats.min(), None);
    assert_eq!(stats.max(), None);
    assert_eq!(stats.mean(), None);
}

#[test]
fn tracks_count_min_max_and_mean() {
    let stats = stats_of(&[12, 7, 30, 11]);
    assert_eq!(stats.count(), 4);
    assert_eq!(stats.min(), Some(7));
    assert_eq!(stats.max(), Some(30));
    assert_eq!(stats.mean(), Some(15.0));
}

#[test]
fn percentile_uses_the_nearest_rank() {
    let stats = stats_of(&[35, 20, 15, 50, 40]);
    assert_eq!(stats.percentile(30.0), Some(20));
    assert_eq!(stats.percentile(40.0), Some(20));
    assert_eq!(stats.percentile(50.0), Some(35));
    assert_eq!(stats.percentile(100.0), Some(50));
}

#[test]
fn merge_combines_two_sets_of_samples() {
    let mut a = stats_of(&[10, 20]);
    let b = stats_of(&[5, 45]);
    a.merge(&b);
    assert_eq!(a.count(), 4);
    assert_eq!(a.min(), Some(5));
    assert_eq!(a.max(), Some(45));
    assert_eq!(a.mean(), Some(20.0));
    assert_eq!(b.count(), 2);
}
