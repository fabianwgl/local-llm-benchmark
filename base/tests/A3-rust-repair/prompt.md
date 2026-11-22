# CI is red on `ringlog`

`ringlog`, the in-memory log analysis crate in `/work`, has been red in CI since last week's
refactor: the crate no longer builds, and two `Stats` methods were never finished.

Please get it back into shape:

- Make the crate build and make `cargo test` pass.
- Implement the unfinished functions as their documentation describes.
- Make sure the crate behaves as `README.md` documents; other teams code against that contract.
- Do not add dependencies or `unsafe` code, and do not change the existing tests or the README.

There is no network. Build with `cargo build --offline` and test with `cargo test --offline`.

When you are done, finish with a short summary of each problem you found and how you fixed it.
