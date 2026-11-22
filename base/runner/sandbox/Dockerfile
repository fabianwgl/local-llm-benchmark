# Sandbox for the benchmark: every toolchain a fixture needs, usable with no network.
# Build: python3 base/runner/bench.py sandbox-build
FROM node:24-bookworm-slim AS node
RUN npm install -g typescript@5 && npm cache clean --force

FROM rust:1-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-pytest sqlite3 git ripgrep jq make shellcheck procps patch diffutils file util-linux \
 && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/typescript/bin/tsc /usr/local/bin/tsc \
 && ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && for b in /usr/local/cargo/bin/*; do ln -s "$b" /usr/local/bin/; done \
 && useradd -m -u 1000 -s /bin/bash bench \
 && mkdir -p /work /opt/bench /in /out /hidden /home/bench/.cargo \
 && chown -R bench:bench /work /home/bench
COPY tool.py /opt/bench/tool.py
ENV CARGO_HOME=/home/bench/.cargo \
    CARGO_NET_OFFLINE=true \
    PYTHONDONTWRITEBYTECODE=1 \
    NO_COLOR=1 \
    TZ=UTC \
    LANG=C.UTF-8
WORKDIR /work
CMD ["sleep", "infinity"]
