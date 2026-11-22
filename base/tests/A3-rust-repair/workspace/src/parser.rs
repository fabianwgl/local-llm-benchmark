//! Parser for logfmt lines such as `level=warn msg="disk at 91%" service=api`.
//!
//! The line format and the error conditions are specified in `README.md`.

use std::fmt;

/// The reason a line was rejected.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorKind {
    /// A field has no `=` between its key and its value.
    MissingEquals,
    /// A field starts with `=`.
    EmptyKey,
    /// A quoted value is not closed before the end of the line.
    UnterminatedQuote,
    /// A backslash in a quoted value is followed by an unsupported character.
    InvalidEscape,
    /// A closing quote is followed by something other than a space.
    TrailingCharacters,
}

/// A rejected line: what was wrong, and the byte offset in the line where it was found.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ParseError {
    pub kind: ErrorKind,
    pub offset: usize,
}

impl ParseError {
    fn new(kind: ErrorKind, offset: usize) -> Self {
        ParseError { kind, offset }
    }
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let what = match self.kind {
            ErrorKind::MissingEquals => "field without `=`",
            ErrorKind::EmptyKey => "empty key",
            ErrorKind::UnterminatedQuote => "unterminated quoted value",
            ErrorKind::InvalidEscape => "invalid escape sequence",
            ErrorKind::TrailingCharacters => "unexpected character after closing quote",
        };
        write!(f, "{} at byte {}", what, self.offset)
    }
}

impl std::error::Error for ParseError {}

/// The fields of one log line, in the order they were written.
///
/// A record borrows from the line it was parsed from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record<'a> {
    fields: Vec<(&'a str, &'a str)>,
}

impl Record<'_> {
    /// The value of the field named `key`, or `None` if the line has no such field.
    pub fn get(&self, key: &str) -> Option<&str> {
        self.fields.iter().find(|(k, _)| *k == key).map(|(_, v)| *v)
    }

    /// The number of fields. A key that is repeated counts every time.
    pub fn len(&self) -> usize {
        self.fields.len()
    }

    /// Returns `true` if the line had no fields.
    pub fn is_empty(&self) -> bool {
        self.fields.is_empty()
    }

    /// All `(key, value)` pairs in the order they appear in the line.
    pub fn iter(&self) -> impl Iterator<Item = (&str, &str)> + '_ {
        self.fields.iter().map(|&(k, v)| (k, v))
    }
}

/// Parses one log line (without its trailing newline).
pub fn parse_line(line: &str) -> Result<Record<'_>, ParseError> {
    let bytes = line.as_bytes();
    let mut fields = Vec::new();
    let mut pos = 0;
    loop {
        while bytes.get(pos) == Some(&b' ') {
            pos += 1;
        }
        if pos == bytes.len() {
            break;
        }

        let start = pos;
        while pos < bytes.len() && bytes[pos] != b'=' && bytes[pos] != b' ' {
            pos += 1;
        }
        if bytes.get(pos) != Some(&b'=') {
            return Err(ParseError::new(ErrorKind::MissingEquals, start));
        }
        if pos == start {
            return Err(ParseError::new(ErrorKind::EmptyKey, start));
        }
        let key = &line[start..pos];
        pos += 1;

        let value = if bytes.get(pos) == Some(&b'"') {
            let (value, next) = quoted_value(line, pos)?;
            if next < bytes.len() && bytes[next] != b' ' {
                return Err(ParseError::new(ErrorKind::TrailingCharacters, next));
            }
            pos = next;
            value
        } else {
            let from = pos;
            while pos < bytes.len() && bytes[pos] != b' ' {
                pos += 1;
            }
            &line[from..pos]
        };
        fields.push((key, value));
    }
    Ok(Record { fields })
}

/// Reads the quoted value whose opening quote is at byte `open`. Returns the value and the
/// offset of the byte that follows the closing quote.
fn quoted_value(line: &str, open: usize) -> Result<(&str, usize), ParseError> {
    let bytes = line.as_bytes();
    let mut close = open + 1;
    let mut has_escapes = false;
    loop {
        match bytes.get(close) {
            None => return Err(ParseError::new(ErrorKind::UnterminatedQuote, open)),
            Some(b'"') => break,
            Some(b'\\') => {
                has_escapes = true;
                close += 2;
            }
            Some(_) => close += 1,
        }
    }

    let raw = &line[open + 1..close];
    if !has_escapes {
        return Ok((raw, close + 1));
    }
    let unescaped = unescape(raw, open)?;
    Ok((unescaped.as_str(), close + 1))
}

/// Decodes the escape sequences in `raw`, the text between the quotes of a quoted value.
/// `base` is the byte offset of `raw` in the line and is only used to report errors.
fn unescape(raw: &str, base: usize) -> Result<String, ParseError> {
    let mut out = String::with_capacity(raw.len());
    let mut chars = raw.char_indices();
    while let Some((at, c)) = chars.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        match chars.next() {
            Some((_, '"')) => out.push('"'),
            Some((_, '\\')) => out.push('\\'),
            Some((_, 'n')) => out.push('\n'),
            Some((_, 't')) => out.push('\t'),
            _ => return Err(ParseError::new(ErrorKind::InvalidEscape, base + at)),
        }
    }
    Ok(out)
}
