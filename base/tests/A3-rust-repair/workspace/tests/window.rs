use ringlog::LogWindow;

#[test]
fn keeps_the_most_recent_lines() {
    let mut window = LogWindow::new(2);
    assert!(window.is_empty());
    window.push("level=info msg=first");
    window.push("level=info msg=second");
    window.push("level=warn msg=third");
    assert_eq!(window.len(), 2);

    let messages: Vec<String> = window
        .records()
        .map(|record| record.get("msg").unwrap().to_string())
        .collect();
    assert_eq!(messages, ["second", "third"]);
}

#[test]
fn summarises_a_latency_field() {
    let mut window = LogWindow::new(8);
    for line in [
        "level=info path=/users duration_ms=12",
        "level=info path=/users duration_ms=48",
        "this line is not logfmt",
        r#"level=warn path=/orders duration_ms=31 msg="slow \"orders\" query""#,
        "level=info path=/health",
        "level=info path=/users duration_ms=9",
    ] {
        window.push(line);
    }

    let latency = window.latency("duration_ms");
    assert_eq!(latency.count(), 4);
    assert_eq!(latency.min(), Some(9));
    assert_eq!(latency.max(), Some(48));
    assert_eq!(latency.percentile(50.0), Some(12));
}
