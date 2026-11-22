use ringlog::{parse_line, ErrorKind};

#[test]
fn parses_bare_fields() {
    let record = parse_line("ts=2026-03-14T09:26:53Z level=info service=api").unwrap();
    assert_eq!(record.len(), 3);
    assert_eq!(record.get("ts"), Some("2026-03-14T09:26:53Z"));
    assert_eq!(record.get("level"), Some("info"));
    assert_eq!(record.get("service"), Some("api"));
    assert_eq!(record.get("host"), None);
}

#[test]
fn parses_quoted_values() {
    let record = parse_line(r#"level=warn msg="disk almost full" code=507"#).unwrap();
    assert_eq!(record.get("msg"), Some("disk almost full"));
    assert_eq!(record.get("code"), Some("507"));
}

#[test]
fn decodes_escape_sequences() {
    let record = parse_line(r#"level=warn msg="disk \"sda\" at 91%" service=api"#).unwrap();
    assert_eq!(record.get("msg"), Some(r#"disk "sda" at 91%"#));
    assert_eq!(record.get("service"), Some("api"));

    let record = parse_line(r#"trace="main.rs\n\tlib.rs""#).unwrap();
    assert_eq!(record.get("trace"), Some("main.rs\n\tlib.rs"));
}

#[test]
fn keeps_fields_in_line_order() {
    let record = parse_line("b=2 a=1 c=3").unwrap();
    let pairs: Vec<(&str, &str)> = record.iter().collect();
    assert_eq!(pairs, [("b", "2"), ("a", "1"), ("c", "3")]);
}

#[test]
fn a_line_without_fields_is_an_empty_record() {
    assert!(parse_line("").unwrap().is_empty());
    assert!(parse_line("   ").unwrap().is_empty());
}

#[test]
fn rejects_malformed_lines() {
    let err = parse_line("level=info oops").unwrap_err();
    assert_eq!(err.kind, ErrorKind::MissingEquals);
    assert_eq!(err.offset, 11);

    let err = parse_line(r#"msg="never closed"#).unwrap_err();
    assert_eq!(err.kind, ErrorKind::UnterminatedQuote);
    assert_eq!(err.offset, 4);

    let err = parse_line(r#"msg="50\% done""#).unwrap_err();
    assert_eq!(err.kind, ErrorKind::InvalidEscape);
}
